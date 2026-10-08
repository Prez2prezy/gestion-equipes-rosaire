import sqlite3
import os
import time
import hashlib
import secrets
import logging

# Configuration du logging pour éviter d'utiliser st.error dans la base de données
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# --- Connexion DB ---
def create_connection():
    try:
        try:
            from libsql import connect as turso_connect
        except ImportError:
            from libsql_experimental import connect as turso_connect
        import streamlit as st
        url = st.secrets.get("TURSO_URL")
        token = st.secrets.get("TURSO_AUTH_TOKEN")
        if url and token:
            # On fait 2 tentatives en cas de micro-coupure réseau
            for attempt in range(2):
                try:
                    return turso_connect(url, auth_token=token), True
                except Exception as e:
                    if attempt == 0:
                        import time
                        time.sleep(1) # On attend 1 seconde et on réessaie
                    else:
                        raise e # Si ça rate 2 fois, on laisse planter l'app pour forcer un redémarrage propre
    except Exception as e:
        # Vérification de sécurité : Les clés Turso sont-elles dans les paramètres ?
        url = None
        token = None
        try:
            import streamlit as st
            url = st.secrets.get("TURSO_URL")
            token = st.secrets.get("TURSO_AUTH_TOKEN")
        except Exception:
            pass
        
        # SI les clés Turso existent mais la connexion échoue, ON NE FAIT PAS DE FALLBACK.
        # On lève une erreur pour forcer Streamlit Cloud à redémarrer l'app proprement.
        if url and token:
            raise Exception(f"Connexion à Turso perdue. Redémarrage en cours... ({e})")
            
    # Si Turso n'est pas configuré du tout, on utilise bien le fichier local
    return sqlite3.connect('gestion_religieuse.db', check_same_thread=False), False

def init_db():
    import streamlit as st
    @st.cache_resource
    def get_conn():
        conn, is_turso = create_connection()
        return conn, is_turso
    return get_conn()

conn, USE_TURSO = init_db()

class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        last_err = None
        for attempt in range(3):
            try:
                return self.cursor.execute(query, tuple(params) if params else ())
            except Exception as e:
                msg = str(e).lower()
                if "stream not found" in msg or "connection reset" in msg:
                    time.sleep(1)
                    global conn
                    try:
                        conn, _ = create_connection()
                        self.cursor = conn.cursor()
                        last_err = e
                        continue
                    except Exception as e2:
                        last_err = e2
                        continue
                if "duplicate column" not in msg:
                    logger.error(f"Erreur SQL : {e}")
                raise
        raise Exception(f"Connexion Turso instable : 3 tentatives échouées ({last_err})")

    def __getattr__(self, name):
        return getattr(self.cursor, name)

c = CursorWrapper(conn.cursor()) if USE_TURSO else conn.cursor()

def commit_and_sync():
    try:
        conn.commit()
    except Exception as e:
        logger.error(f"Erreur lors du commit : {e}")

# --- Fonction de migration sécurisée ---
def safe_migrate(query, error_ignore_phrases=["duplicate column", "duplicate column name"]):
    """Exécute une requête de migration en ignorant silencieusement les erreurs de doublon.
    v7.6.2 : s'exécute sur une CONNEXION JETABLE — une migration qui échoue
    ne peut plus contaminer le curseur partagé utilisé par l'application."""
    try:
        conn_tmp, _ = create_connection()
        cur_tmp = conn_tmp.cursor()
        cur_tmp.execute(query)
        conn_tmp.commit()
        try:
            conn_tmp.close()
        except Exception:
            pass
    except Exception as e:
        error_msg = str(e).lower()
        if not any(phrase in error_msg for phrase in error_ignore_phrases):
            logger.warning(f"Migration ignorée ou échouée: {e}")

# --- Création des tables et Migrations (Exécuté UNE SEULE FOIS) ---
def _definir_mdp(p):
    """PBKDF2 local (services.py ne peut pas être importé ici : dépendance circulaire)."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000)
    return f"pbkdf2${salt}${dk.hex()}"

def init_tables_and_migrations():
    # --- 1. CRÉATION DES TABLES ---
    c.execute("""CREATE TABLE IF NOT EXISTS diocese (id INTEGER PRIMARY KEY, nom TEXT, responsable TEXT, bureau TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS paroisses (id INTEGER PRIMARY KEY, nom TEXT, commune TEXT, ville TEXT, responsable TEXT, bureau TEXT, diocese_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS equipes (id INTEGER PRIMARY KEY, nom_equipe TEXT, responsable TEXT, bureau TEXT, paroisse_id INTEGER, max_membres INTEGER DEFAULT 10)""")
    c.execute("""CREATE TABLE IF NOT EXISTS membres (id INTEGER PRIMARY KEY, matloc TEXT UNIQUE, nom TEXT, prenom TEXT, date_naissance DATE, whatsapp TEXT, date_adhesion DATE, photo_path TEXT, paroisse_id INTEGER, equipe_id INTEGER, statut TEXT DEFAULT 'actif', numero_meditation TEXT, matricule TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS utilisateurs (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, diocese_id INTEGER, paroisse_id INTEGER, equipe_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS abonnements (id INTEGER PRIMARY KEY, membre_id INTEGER, annee_debut INTEGER, date_paiement DATE, montant REAL DEFAULT 0, type_abonnement TEXT DEFAULT 'abonnement', statut TEXT DEFAULT 'non_paye')""")
    c.execute("""CREATE TABLE IF NOT EXISTS archives (id INTEGER PRIMARY KEY, membre_id INTEGER, situation TEXT, date_debut DATE, date_fin DATE, commentaire TEXT, auteur_id INTEGER, auteur_nom TEXT, auteur_role TEXT, paroisse_id INTEGER, equipe_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS evenements (id INTEGER PRIMARY KEY, equipe_id INTEGER, paroisse_id INTEGER, diocese_id INTEGER, type_evenement TEXT, date_evenement DATE, lieu TEXT, auteur_nom TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS evenement_equipes (id INTEGER PRIMARY KEY, evenement_id INTEGER, equipe_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS suivi_presences (id INTEGER PRIMARY KEY, membre_id INTEGER, evenement_id INTEGER, statut TEXT DEFAULT 'a_contacter')""")
    c.execute("""CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY, equipe_id INTEGER, paroisse_id INTEGER, diocese_id INTEGER, date_event DATE, type_event TEXT, lieu TEXT, description TEXT, auteur_nom TEXT, a_faire_suivre INTEGER DEFAULT 0, evenement_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS periodes_cloturees (id INTEGER PRIMARY KEY AUTOINCREMENT, entite_type TEXT, entite_id INTEGER, annee_debut INTEGER, date_cloture TEXT, auteur_nom TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS espace_spirituel (id INTEGER PRIMARY KEY, type_contenu TEXT, titre TEXT, contenu_texte TEXT, fichier_url TEXT, date_publication DATE, auteur_nom TEXT, image_url TEXT)""")
    # Soumissions Communication — schéma COMPLET dès la création
    c.execute("""CREATE TABLE IF NOT EXISTS soumissions_comm (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auteur_id INTEGER, type_contenu TEXT, titre TEXT,
                    contenu_texte TEXT, image_url TEXT, fichier_url TEXT,
                    video_url TEXT, date_evenement TEXT, lieu TEXT,
                    statut TEXT DEFAULT 'attente', motif_refus TEXT,
                    date_soumission TEXT, paroisse_cible INTEGER)""")
    # Statistiques & traçabilité
    c.execute("""CREATE TABLE IF NOT EXISTS visites_paroisse (id INTEGER PRIMARY KEY AUTOINCREMENT, paroisse_id INTEGER, date_visite TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS stats_visites (id INTEGER PRIMARY KEY AUTOINCREMENT, page TEXT, date_visite DATE)""")
    # Sessions persistantes (rester connecté malgré le rafraîchissement)
    c.execute("""CREATE TABLE IF NOT EXISTS sessions_persistantes (
                    token TEXT PRIMARY KEY, user_id INTEGER, date_creation DATE,
                    menu_courant TEXT)""")
    # Thème pastoral (3 tables requises par mysteres.py + components.py)
    c.execute("""CREATE TABLE IF NOT EXISTS themes_pastoraux (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER UNIQUE, texte_theme TEXT,
                    mystere_principal INTEGER, actif INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sous_themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER, mois INTEGER,
                    titre TEXT, contenu TEXT, feuillet_pdf TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS theme_mystere (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER, mystere_id INTEGER, texte_lien TEXT,
                    UNIQUE(annee_debut, mystere_id))""")
    commit_and_sync()

    # --- 2. DONNÉES PAR DÉFAUT ---
    if c.execute("SELECT COUNT(*) FROM diocese").fetchone()[0] == 0:
        c.execute("INSERT INTO diocese (nom, responsable, bureau) VALUES (?, ?, ?)", ("GRAND-BASSAM", "À définir", "À définir"))
    if c.execute("SELECT COUNT(*) FROM utilisateurs WHERE role='diocese'").fetchone()[0] == 0:
        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?, ?, ?, ?)",
                  ("diocese", _definir_mdp("admin123"), "diocese", 1))
    commit_and_sync()

    # --- 3. MIGRATIONS STRUCTURELLES (idempotentes) ---
    safe_migrate("ALTER TABLE membres RENAME COLUMN matricule TO matloc")
    # v7.6.2 — migration « mle_sup » RETIRÉE : la colonne n'existe pas dans
    # la base actuelle ; cette requête échouait à chaque démarrage et
    # contaminait les requêtes suivantes (erreurs « tuple index out of range »).
    # safe_migrate("ALTER TABLE membres RENAME COLUMN mle_sup TO matricule")
    safe_migrate("ALTER TABLE membres ADD COLUMN matricule TEXT")
    safe_migrate("ALTER TABLE agenda ADD COLUMN a_faire_suivre INTEGER DEFAULT 0")
    safe_migrate("ALTER TABLE evenements ADD COLUMN paroisse_id INTEGER")
    safe_migrate("ALTER TABLE evenements ADD COLUMN diocese_id INTEGER")
    safe_migrate("ALTER TABLE evenements ADD COLUMN auteur_nom TEXT")
    safe_migrate("ALTER TABLE agenda ADD COLUMN evenement_id INTEGER")
    safe_migrate("ALTER TABLE espace_spirituel ADD COLUMN image_url TEXT")
    # Visuels d'évènements + ciblage paroissial
    safe_migrate("ALTER TABLE evenements ADD COLUMN affiche_url TEXT")
    safe_migrate("ALTER TABLE evenements ADD COLUMN video_url TEXT")
    safe_migrate("ALTER TABLE evenements ADD COLUMN paroisse_cible INTEGER")
    safe_migrate("ALTER TABLE espace_spirituel ADD COLUMN paroisse_cible INTEGER")
    # WhatsApp responsables
    safe_migrate("ALTER TABLE paroisses ADD COLUMN whatsapp_responsable TEXT")
    safe_migrate("ALTER TABLE diocese ADD COLUMN whatsapp_responsable TEXT")
    # Base ancienne : colonne ajoutée rétroactivement
    safe_migrate("ALTER TABLE soumissions_comm ADD COLUMN paroisse_cible INTEGER")
    # Affiches du thème pastoral et des sous-thèmes mensuels
    safe_migrate("ALTER TABLE themes_pastoraux ADD COLUMN affiche_url TEXT")
    safe_migrate("ALTER TABLE sous_themes ADD COLUMN affiche_url TEXT")
    # Rubrique courante mémorisée dans le jeton de session
    safe_migrate("ALTER TABLE sessions_persistantes ADD COLUMN menu_courant TEXT")

    # --- 4. MIGRATION DE DONNÉES (évènements anciens) ---
    try:
        anciens_evts = c.execute("SELECT id, equipe_id FROM evenements WHERE equipe_id IS NOT NULL AND paroisse_id IS NULL AND diocese_id IS NULL").fetchall()
        for evt_id, eq_id in anciens_evts:
            existe = c.execute("SELECT id FROM evenement_equipes WHERE evenement_id=? AND equipe_id=?", (evt_id, eq_id)).fetchone()
            if not existe:
                c.execute("INSERT INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (evt_id, eq_id))
        commit_and_sync()
    except Exception as e:
        logger.warning(f"Erreur migration événements: {e}")

    # ATTENTION : Les UPDATE de renommage de statut sont retirés d'ici.
    # Les exécuter à chaque chargement fige la DB. Ils doivent être lancés MANUELLEMENT 
    # UNE SEULE FOIS dans un outil de gestion SQLite (comme DB Browser) si la base est ancienne.

# --- INITIALISATION AUTOMATIQUE ---
# On utilise un flag dans session_state pour s'assurer que ça ne tourne qu'UNE SEULE FOIS par session utilisateur
def setup_database():
    import streamlit as st
    if "db_initialized" not in st.session_state:
        init_tables_and_migrations()
        st.session_state.db_initialized = True

# Lancement au chargement du module
try:
    setup_database()
except Exception as e:
    logger.error(f"Erreur critique lors de l'initialisation de la DB: {e}")
