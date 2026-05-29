import streamlit as st
import sqlite3
from datetime import date, timedelta
import os
import hashlib
import random
import string
from PIL import Image
import shutil
import pandas as pd
import io
import urllib.parse

# --- Configuration de la page ---
st.set_page_config(page_title="Gestionnaire des Équipes du Rosaire - Diocèse de Grand-Bassam", layout="wide")

# --- CSS personnalisé ---
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF !important; }
    .main > div { background-color: #FFFFFF !important; }
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #1A237E !important; }
    .streamlit-expanderHeader span:last-child { display: none !important; }
    .stMetric label, .stMetric .stMarkdown { color: #1A237E !important; }
    .stSidebar { background-color: #FFFFFF !important; }
    .stSidebar .stMarkdown, .stSidebar label { color: #1A237E !important; }
    .stTextInput input, .stTextArea textarea, .stSelectbox select { background-color: #FFFFFF !important; color: #1A237E !important; }
    .whatsapp-link {
        display: inline-block;
        background-color: #25D366;
        color: white !important;
        padding: 5px 12px;
        border-radius: 30px;
        text-decoration: none;
        font-size: 13px;
        margin-top: 5px;
    }
    .whatsapp-link:hover {
        background-color: #128C7E;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Connexion à la base de données ---
conn = sqlite3.connect('gestion_religieuse.db', check_same_thread=False)
c = conn.cursor()

# --- Fonctions utilitaires générales ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generer_matricule_unique():
    while True:
        suffixe = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        matricule = f"BN-{suffixe}"
        existe = c.execute("SELECT COUNT(*) FROM membres WHERE matricule=?", (matricule,)).fetchone()[0]
        if existe == 0:
            return matricule

def generer_mot_de_passe(longueur=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=longueur))

def sans_accents(texte):
    texte = texte.lower()
    accents = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'î': 'i', 'ï': 'i',
        'ô': 'o', 'ö': 'o',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c'
    }
    for accent, lettre in accents.items():
        texte = texte.replace(accent, lettre)
    return texte

def sauvegarder_photo(photo_fichier, matricule):
    if photo_fichier is not None:
        if not os.path.exists("photos"):
            os.makedirs("photos")
        chemin = f"photos/{matricule}.jpg"
        img = Image.open(photo_fichier)
        img = img.resize((300, 300))
        img.save(chemin, "JPEG", quality=60)
        return chemin
    return None

def supprimer_photo(photo_path):
    if photo_path and os.path.exists(photo_path):
        os.remove(photo_path)

def archiver_membre(membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id):
    """Archive un membre : met à jour son statut et ajoute une entrée dans archives"""
    c.execute("UPDATE membres SET statut='archive' WHERE id=?", (membre_id,))
    c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id))
    conn.commit()

# --- Fonctions pour les abonnements ---
def enregistrer_abonnement(membre_id, annee_debut, montant=0, type_abonnement='abonnement'):
    date_paiement = date.today()
    existant = c.execute("SELECT id FROM abonnements WHERE membre_id=? AND annee_debut=?", (membre_id, annee_debut)).fetchone()
    if existant:
        c.execute("UPDATE abonnements SET date_paiement=?, montant=?, type_abonnement=?, statut='paye' WHERE id=?",
                  (date_paiement, montant, type_abonnement, existant[0]))
    else:
        c.execute('''INSERT INTO abonnements (membre_id, annee_debut, date_paiement, montant, type_abonnement, statut)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (membre_id, annee_debut, date_paiement, montant, type_abonnement, 'paye'))
    conn.commit()

def verifier_abonnement(membre_id, annee_debut):
    result = c.execute('''SELECT id FROM abonnements 
                          WHERE membre_id = ? AND annee_debut = ? AND statut = 'paye' ''',
                       (membre_id, annee_debut)).fetchone()
    return result is not None

def periode_affichage(annee_debut):
    return f"Sept {annee_debut} – Sept {annee_debut+1}"

def afficher_situation(situation):
    mapping = {
        "Déplacé": "a déménagé",
        "Radié": "indisponible",
        "Défunt": "est décédé(e)"
    }
    return mapping.get(situation, situation)

def convertir_en_date(valeur):
    """Convertit une chaîne ISO ou un objet date en objet date."""
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str):
        try:
            return date.fromisoformat(valeur)
        except:
            return None
    return None

# --- Fonctions WhatsApp ---
def lien_whatsapp(numero, message):
    if not numero:
        return None
    numero_propre = ''.join(c for c in numero if c.isdigit() or c == '+')
    if not numero_propre.startswith('+'):
        if len(numero_propre) == 10:
            numero_propre = '225' + numero_propre
    message_encode = urllib.parse.quote(message)
    return f"https://wa.me/{numero_propre}?text={message_encode}"

def afficher_anniversaires_whatsapp():
    aujourdhui = date.today()
    anniversaires = c.execute('''
        SELECT m.id, m.nom, m.prenom, m.whatsapp, e.nom_equipe, p.nom as paroisse, m.date_naissance
        FROM membres m
        JOIN equipes e ON m.equipe_id = e.id
        JOIN paroisses p ON m.paroisse_id = p.id
        WHERE m.statut='actif' AND strftime('%m-%d', m.date_naissance) = ?
        ORDER BY m.nom
    ''', (aujourdhui.strftime('%m-%d'),)).fetchall()
    if anniversaires:
        for a in anniversaires:
            st.markdown(f"**🎂 {a[1]} {a[2]}**")
            st.write(f"📅 Né(e) le : {a[6]}")
            st.write(f"📍 {a[5]} / {a[4]}")
            if a[3]:
                message = f"Joyeux anniversaire {a[1]} {a[2]} ! 🎉\\n\\nToute l'équipe du Rosaire vous souhaite une journée bénie."
                lien = lien_whatsapp(a[3], message)
                if lien:
                    st.markdown(f'<a href="{lien}" target="_blank" class="whatsapp-link">📱 Souhaiter par WhatsApp</a>', unsafe_allow_html=True)
            st.markdown("---")
    else:
        st.info("🎉 Aucun anniversaire aujourd'hui")

def afficher_rappels_reabonnement_whatsapp(annee_debut, equipe_id=None):
    if equipe_id:
        membres_retard = c.execute('''
            SELECT m.id, m.nom, m.prenom, m.whatsapp, e.nom_equipe
            FROM membres m
            JOIN equipes e ON m.equipe_id = e.id
            WHERE m.equipe_id = ? AND m.statut='actif' AND m.id NOT IN (
                SELECT a.membre_id FROM abonnements a 
                WHERE a.annee_debut = ? AND a.statut = 'paye'
            )
            ORDER BY m.nom
        ''', (equipe_id, annee_debut)).fetchall()
    else:
        membres_retard = c.execute('''
            SELECT m.id, m.nom, m.prenom, m.whatsapp, e.nom_equipe, p.nom as paroisse
            FROM membres m
            JOIN equipes e ON m.equipe_id = e.id
            JOIN paroisses p ON m.paroisse_id = p.id
            WHERE m.statut='actif' AND m.id NOT IN (
                SELECT a.membre_id FROM abonnements a 
                WHERE a.annee_debut = ? AND a.statut = 'paye'
            )
            ORDER BY p.nom, e.nom_equipe, m.nom
        ''', (annee_debut,)).fetchall()
    if membres_retard:
        for m in membres_retard:
            st.markdown(f"**❌ {m[1]} {m[2]}**")
            if len(m) > 5:
                st.write(f"📍 {m[5]} / {m[4]}")
            else:
                st.write(f"📍 {m[4]}")
            if m[3]:
                message = f"Bonjour {m[1]} {m[2]},\\n\\nVotre réabonnement pour la période {periode_affichage(annee_debut)} n'a pas été enregistré. Merci de régulariser."
                lien = lien_whatsapp(m[3], message)
                if lien:
                    st.markdown(f'<a href="{lien}" target="_blank" class="whatsapp-link">📱 Envoyer rappel</a>', unsafe_allow_html=True)
            st.markdown("---")
    else:
        st.success(f"🎉 Tous les membres sont à jour pour la période {periode_affichage(annee_debut)} !")

def transferer_membre(membre_id, nouvelle_paroisse_id, nouvelle_equipe_id, motif, auteur_id, auteur_nom, auteur_role):
    ancien = c.execute("SELECT paroisse_id, equipe_id FROM membres WHERE id=?", (membre_id,)).fetchone()
    if not ancien:
        return False, "Membre introuvable"
    ancienne_paroisse, ancienne_equipe = ancien
    # Vérification que l'équipe destination appartient bien à la paroisse destination
    verif = c.execute("SELECT id FROM equipes WHERE id=? AND paroisse_id=?", (nouvelle_equipe_id, nouvelle_paroisse_id)).fetchone()
    if not verif:
        return False, "L'équipe sélectionnée n'appartient pas à la paroisse de destination"
    # Mise à jour du membre
    c.execute("UPDATE membres SET paroisse_id=?, equipe_id=? WHERE id=?", (nouvelle_paroisse_id, nouvelle_equipe_id, membre_id))
    # Enregistrement du mouvement
    c.execute('''INSERT INTO mouvements (membre_id, date_mouvement, ancienne_paroisse_id, nouvelle_paroisse_id,
                                         ancienne_equipe_id, nouvelle_equipe_id, motif, auteur_id, auteur_nom, auteur_role)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (membre_id, date.today(), ancienne_paroisse, nouvelle_paroisse_id,
               ancienne_equipe, nouvelle_equipe_id, motif, auteur_id, auteur_nom, auteur_role))
    conn.commit()
    return True, "Transfert effectué avec succès"

# --- Export Excel (avec gestion d'erreur du moteur) ---
def exporter_excel_diocese():
    output = io.BytesIO()
    try:
        # On tente d'abord openpyxl, sinon xlsxwriter, sinon excel
        with pd.ExcelWriter(output, engine=None) as writer:
            paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau FROM paroisses").fetchall()
            if paroisses:
                df = pd.DataFrame(paroisses, columns=["ID", "Nom", "Commune", "Ville", "Responsable", "Bureau"])
                df.to_excel(writer, sheet_name="Paroisses", index=False)
            equipes = c.execute('''SELECT e.id, e.nom_equipe, e.responsable, e.bureau, p.nom as paroisse, e.max_membres
                                   FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id''').fetchall()
            if equipes:
                df = pd.DataFrame(equipes, columns=["ID", "Nom équipe", "Responsable", "Bureau", "Paroisse", "Max membres"])
                df.to_excel(writer, sheet_name="Equipes", index=False)
            membres = c.execute('''SELECT m.matricule, m.nom, m.prenom, m.date_naissance, m.whatsapp, m.date_adhesion,
                                          p.nom as paroisse, e.nom_equipe as equipe
                                   FROM membres m
                                   JOIN paroisses p ON m.paroisse_id = p.id
                                   JOIN equipes e ON m.equipe_id = e.id
                                   WHERE m.statut = 'actif'
                                   ORDER BY p.nom, e.nom_equipe, m.nom''').fetchall()
            if membres:
                df = pd.DataFrame(membres, columns=["Matricule", "Nom", "Prénom", "Date naissance", "WhatsApp", "Date adhésion", "Paroisse", "Équipe"])
                df.to_excel(writer, sheet_name="Membres actifs", index=False)
            abonnements = c.execute('''SELECT a.id, m.matricule, m.nom, m.prenom, a.annee_debut, a.date_paiement, a.montant, a.type_abonnement
                                       FROM abonnements a
                                       JOIN membres m ON a.membre_id = m.id
                                       ORDER BY a.annee_debut DESC, m.nom''').fetchall()
            if abonnements:
                df = pd.DataFrame(abonnements, columns=["ID", "Matricule", "Nom", "Prénom", "Année début", "Date paiement", "Montant", "Type"])
                df["Période"] = df["Année début"].apply(lambda x: f"Sept {x} – Sept {x+1}")
                df.to_excel(writer, sheet_name="Abonnements", index=False)
            archives = c.execute('''SELECT m.matricule, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire,
                                           p.nom as paroisse, e.nom_equipe as equipe
                                    FROM archives a
                                    JOIN membres m ON a.membre_id = m.id
                                    LEFT JOIN equipes e ON a.equipe_id = e.id
                                    LEFT JOIN paroisses p ON e.paroisse_id = p.id
                                    ORDER BY a.date_fin DESC''').fetchall()
            if archives:
                df = pd.DataFrame(archives, columns=["Matricule", "Nom", "Prénom", "Situation", "Début", "Fin", "Commentaire", "Paroisse", "Équipe"])
                df.to_excel(writer, sheet_name="Archives", index=False)
        output.seek(0)
        return output
    except Exception as e:
        st.error(f"Erreur lors de la création de l'Excel : {e}. Assurez-vous d'avoir installé 'openpyxl' ou 'xlsxwriter'.")
        return None

# --- Création des tables ---
c.execute('''CREATE TABLE IF NOT EXISTS diocese (id INTEGER PRIMARY KEY, nom TEXT, responsable TEXT, bureau TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS paroisses (id INTEGER PRIMARY KEY, nom TEXT, commune TEXT, ville TEXT, responsable TEXT, bureau TEXT, diocese_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS equipes (id INTEGER PRIMARY KEY, nom_equipe TEXT, responsable TEXT, bureau TEXT, paroisse_id INTEGER, max_membres INTEGER DEFAULT 10)''')
c.execute('''CREATE TABLE IF NOT EXISTS membres (id INTEGER PRIMARY KEY, matricule TEXT UNIQUE, nom TEXT, prenom TEXT, date_naissance DATE, whatsapp TEXT, date_adhesion DATE, photo_path TEXT, paroisse_id INTEGER, equipe_id INTEGER, statut TEXT DEFAULT 'actif')''')
c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, diocese_id INTEGER, paroisse_id INTEGER, equipe_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS abonnements (id INTEGER PRIMARY KEY, membre_id INTEGER, annee_debut INTEGER, date_paiement DATE, montant REAL DEFAULT 0, type_abonnement TEXT DEFAULT 'abonnement', statut TEXT DEFAULT 'non_paye')''')
c.execute('''CREATE TABLE IF NOT EXISTS archives (id INTEGER PRIMARY KEY, membre_id INTEGER, situation TEXT, date_debut DATE, date_fin DATE, commentaire TEXT, auteur_id INTEGER, auteur_nom TEXT, auteur_role TEXT, paroisse_id INTEGER, equipe_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS mouvements (id INTEGER PRIMARY KEY, membre_id INTEGER, date_mouvement DATE, ancienne_paroisse_id INTEGER, nouvelle_paroisse_id INTEGER, ancienne_equipe_id INTEGER, nouvelle_equipe_id INTEGER, motif TEXT, auteur_id INTEGER, auteur_nom TEXT, auteur_role TEXT)''')
conn.commit()

# --- Migrations : ajout des colonnes manquantes ---
# --- for col in ['statut', 'annee_debut', 'situation', 'date_debut', 'date_fin']: ---
try: c.execute("ALTER TABLE membres ADD COLUMN statut TEXT DEFAULT 'actif'"); conn.commit()
except: pass

try: c.execute("ALTER TABLE abonnements ADD COLUMN annee_debut INTEGER"); conn.commit()
except: pass

try: c.execute("ALTER TABLE archives ADD COLUMN situation TEXT"); conn.commit()
except: pass

try: c.execute("ALTER TABLE archives ADD COLUMN date_debut DATE"); conn.commit()
except: pass

try: c.execute("ALTER TABLE archives ADD COLUMN date_fin DATE"); conn.commit()
except: pass

# --- Initialisation ---
c.execute("SELECT COUNT(*) FROM diocese")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO diocese (nom, responsable, bureau) VALUES (?, ?, ?)", ("GRAND-BASSAM", "À définir", "À définir"))
    conn.commit()

c.execute("SELECT COUNT(*) FROM utilisateurs WHERE role='diocese'")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?, ?, ?, ?)", ("diocese", hash_password("admin123"), "diocese", 1))
    conn.commit()

# Vérifier si le mot de passe diocèse est encore le défaut
if st.session_state.get('logged_in') and st.session_state.get('username') == 'diocese':
    user = c.execute("SELECT password FROM utilisateurs WHERE username='diocese'").fetchone()
    if user and user[0] == hash_password("admin123"):
        st.sidebar.warning("⚠️ Mot de passe par défaut. Veuillez le changer dans 'Gérer les accès'.")

if 'form_counter' not in st.session_state:
    st.session_state['form_counter'] = 0

# --- Logo ---
def afficher_logo():
    if not os.path.exists("images"):
        os.makedirs("images")
    if os.path.exists("images/logo.png"):
        try:
            st.sidebar.image(Image.open("images/logo.png"), use_container_width=True)
        except:
            st.sidebar.markdown("### 📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE")
    else:
        st.sidebar.markdown("### 📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE")
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🏛️ DIOCÈSE DE GRAND-BASSAM")
    st.sidebar.markdown("---")

# --- Authentification ---
if 'logged_in' not in st.session_state:
    afficher_logo()
    st.sidebar.title("🔐 Connexion")
    username = st.sidebar.text_input("Nom d'utilisateur")
    password = st.sidebar.text_input("Mot de passe", type="password")
    if st.sidebar.button("Se connecter"):
        user = c.execute("SELECT * FROM utilisateurs WHERE username=? AND password=?", (username, hash_password(password))).fetchone()
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_id'] = user[0]
            st.session_state['username'] = user[1]
            st.session_state['role'] = user[3]
            st.session_state['diocese_id'] = user[4]
            st.session_state['paroisse_id'] = user[5]
            st.session_state['equipe_id'] = user[6]
            st.success(f"Bienvenue {username}")
            st.rerun()
        else:
            st.sidebar.error("Nom ou mot de passe incorrect")
    st.stop()

# --- Déconnexion ---
afficher_logo()
st.sidebar.success(f"Connecté : {st.session_state['username']}")
if st.sidebar.button("Déconnexion"):
    for key in ['logged_in', 'user_id', 'username', 'role', 'diocese_id', 'paroisse_id', 'equipe_id']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# --- Titre principal ---
st.markdown('<h1 style="color:#1A237E; white-space: nowrap;">📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE</h1>', unsafe_allow_html=True)
st.markdown("---")

# ==================== DIOCÈSE ====================
if st.session_state['role'] == 'diocese':
    menu = st.sidebar.radio("Navigation", ["Voir diocèse", "Créer paroisses", "Gérer paroisses", "Rechercher par matricule", "Gérer les accès", "Statistiques", "📅 Abonnements", "💬 WhatsApp", "📊 Export Excel", "📦 Archives", "🗑️ Réinitialiser tout"])
    
    # Voir diocèse
    if menu == "Voir diocèse":
        st.markdown('<h2 style="color:#1A237E;">🏛️ DIOCÈSE DE GRAND-BASSAM</h2>', unsafe_allow_html=True)
        d = c.execute("SELECT responsable, bureau FROM diocese WHERE id=?", (1,)).fetchone()
        if d:
            st.write(f"**Responsable diocésain :** {d[0]}")
            st.write(f"**Bureau diocésain :** {d[1]}")
            with st.expander("✏️ Modifier"):
                nouveau_resp = st.text_input("Nouveau responsable", value=d[0])
                nouveau_bureau = st.text_area("Nouveau bureau", value=d[1])
                if st.button("Enregistrer"):
                    c.execute("UPDATE diocese SET responsable=?, bureau=? WHERE id=?", (nouveau_resp, nouveau_bureau, 1))
                    conn.commit()
                    st.success("Mis à jour !")
                    st.rerun()
    
    # Créer paroisses
    elif menu == "Créer paroisses":
        st.markdown('<h2 style="color:#1A237E;">🏘️ Créer paroisses</h2>', unsafe_allow_html=True)
        with st.form("creer_paroisse"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nom de la paroisse")
                commune = st.text_input("Commune")
                responsable = st.text_input("Responsable")
            with col2:
                ville = st.text_input("Ville")
                bureau = st.text_area("Bureau")
            if st.form_submit_button("🏘️ Créer paroisses"):
                if nom and commune and ville and responsable:
                    existe = c.execute("SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=? AND diocese_id=?", (nom, commune, ville, 1)).fetchone()
                    if existe:
                        st.error("❌ Cette paroisse existe déjà !")
                    else:
                        c.execute("INSERT INTO paroisses (nom, commune, ville, responsable, bureau, diocese_id) VALUES (?,?,?,?,?,?)", (nom, commune, ville, responsable, bureau, 1))
                        pid = c.lastrowid
                        username = f"paroisse_{pid}"
                        mdp = generer_mot_de_passe()
                        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id, paroisse_id) VALUES (?,?,?,?,?)", (username, hash_password(mdp), "paroisse", 1, pid))
                        conn.commit()
                        st.success(f"✅ Paroisse '{nom}' créée")
                        st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px'>🔑 Identifiant : <code>{username}</code><br>🔒 Mot de passe : <code>{mdp}</code></div>", unsafe_allow_html=True)
                else:
                    st.error("Tous les champs sont requis")
    
    # Gérer paroisses
    elif menu == "Gérer paroisses":
        st.markdown('<h2 style="color:#1A237E;">📋 Consultation des paroisses</h2>', unsafe_allow_html=True)
        paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau FROM paroisses").fetchall()
        for p in paroisses:
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (p[0],)).fetchone()[0]
            with st.expander(f"🏛️ {p[1]} ({p[2]} / {p[3]}) - {nb_equipes} équipe(s)"):
                st.write(f"**Responsable :** {p[4]}")
                st.write(f"**Bureau :** {p[5]}")
                equipes = c.execute("SELECT nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (p[0],)).fetchall()
                if equipes:
                    for eq in equipes:
                        st.write(f"- {eq[0]} (Resp: {eq[1]})")
    
    # Rechercher par matricule
    elif menu == "Rechercher par matricule":
        st.markdown('<h2 style="color:#1A237E;">🔍 Recherche par matricule</h2>', unsafe_allow_html=True)
        matricule = st.text_input("Matricule (ex: BN-ABCDE)")
        if matricule:
            m = c.execute('''SELECT m.matricule, m.nom, m.prenom, m.whatsapp, p.nom, e.nom_equipe, m.photo_path
                             FROM membres m
                             JOIN paroisses p ON m.paroisse_id = p.id
                             JOIN equipes e ON m.equipe_id = e.id
                             WHERE m.matricule = ? AND m.statut = 'actif' ''', (matricule.upper(),)).fetchone()
            if m:
                st.success("Membre trouvé")
                col1, col2 = st.columns([2,1])
                col1.write(f"**{m[1]} {m[2]}** - {m[0]}")
                col1.write(f"💬 WhatsApp: {m[3]} - Paroisse: {m[4]} - Équipe: {m[5]}")
                if m[6] and os.path.exists(m[6]):
                    col2.image(m[6], width=100)
            else:
                st.error("Non trouvé ou membre archivé")
    
    # Gérer les accès
    elif menu == "Gérer les accès":
        st.markdown('<h2 style="color:#1A237E;">🔐 Gestion des accès</h2>', unsafe_allow_html=True)
        st.markdown("### 🏘️ Paroisses")
        paroisses = c.execute("SELECT id, nom, responsable FROM paroisses").fetchall()
        for p in paroisses:
            user = c.execute("SELECT id, username FROM utilisateurs WHERE paroisse_id=? AND role='paroisse'", (p[0],)).fetchone()
            if user:
                with st.expander(f"🏛️ {p[1]} - {p[2]}"):
                    st.write(f"**Identifiant :** `{user[1]}`")
                    if st.button(f"🔄 Réinitialiser le mot de passe", key=f"reset_par_{p[0]}"):
                        nouveau = generer_mot_de_passe()
                        c.execute("UPDATE utilisateurs SET password=? WHERE id=?", (hash_password(nouveau), user[0]))
                        conn.commit()
                        st.success("Mot de passe réinitialisé !")
                        st.code(f"Nouveau mot de passe : {nouveau}", language="text")
                        st.rerun()
    
    # Statistiques
    elif menu == "Statistiques":
        st.markdown('<h2 style="color:#1A237E;">📊 Statistiques</h2>', unsafe_allow_html=True)
        nb_p = c.execute("SELECT COUNT(*) FROM paroisses").fetchone()[0]
        nb_e = c.execute("SELECT COUNT(*) FROM equipes").fetchone()[0]
        nb_m = c.execute("SELECT COUNT(*) FROM membres WHERE statut='actif'").fetchone()[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("🏘️ Paroisses", nb_p)
        col2.metric("👥 Équipes", nb_e)
        col3.metric("👤 Membres actifs", nb_m)
    
    # Abonnements (consultation)
    elif menu == "📅 Abonnements":
        st.markdown('<h2 style="color:#1A237E;">📅 Suivi des abonnements (Diocèse)</h2>', unsafe_allow_html=True)
        annee_debut = st.number_input("Année de début de la période", min_value=2020, max_value=date.today().year, value=date.today().year-1, step=1)
        st.write(f"**Période :** {periode_affichage(annee_debut)}")
        total_membres = c.execute("SELECT COUNT(*) FROM membres WHERE statut='actif'").fetchone()[0]
        payes = c.execute("SELECT COUNT(*) FROM abonnements WHERE annee_debut=? AND statut='paye'", (annee_debut,)).fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("Total membres actifs", total_membres)
        col2.metric("Abonnements enregistrés", payes, delta=f"{payes/total_membres*100:.0f}%" if total_membres else "0%")
        st.markdown("---")
        paroisses = c.execute("SELECT id, nom FROM paroisses").fetchall()
        for p in paroisses:
            with st.expander(f"🏛️ {p[1]}"):
                stats = c.execute('''SELECT COUNT(m.id) as total, 
                            SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes
                     FROM membres m
                     LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=?
                     WHERE m.paroisse_id=? AND m.statut=?''', (annee_debut, annee_debut, p[0], 'actif')).fetchone()
                st.write(f"Total membres : {stats[0]} – À jour : {stats[1]}")
                equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (p[0],)).fetchall()
                for eq in equipes:
                    membres_eq = c.execute('''SELECT m.nom, m.prenom, m.matricule, a.type_abonnement
                                              FROM membres m
                                              LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=? AND a.statut='paye'
                                              WHERE m.equipe_id=? AND m.statut='actif'
                                              ORDER BY m.nom''', (annee_debut, eq[0])).fetchall()
                    if membres_eq:
                        st.markdown(f"**👥 {eq[1]}**")
                        for m in membres_eq:
                            statut = m[3] if m[3] else "Non enregistré"
                            st.write(f"- {m[0]} {m[1]} ({m[2]}) – {statut}")
    
    # WhatsApp
    elif menu == "💬 WhatsApp":
        st.markdown('<h2 style="color:#1A237E;">💬 Communications WhatsApp</h2>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🎂 Anniversaires", "📢 Rappels réabonnement"])
        with tab1:
            afficher_anniversaires_whatsapp()
        with tab2:
            annee_rappel = st.number_input("Année de début", min_value=2020, max_value=date.today().year+1, value=date.today().year, step=1, key="rappel_diocese")
            afficher_rappels_reabonnement_whatsapp(annee_rappel)
    
    # Export Excel
    elif menu == "📊 Export Excel":
        st.markdown('<h2 style="color:#1A237E;">📊 Export des données</h2>', unsafe_allow_html=True)
        nb_membres = c.execute("SELECT COUNT(*) FROM membres").fetchone()[0]
        if nb_membres == 0:
            st.warning("Aucune donnée à exporter.")
        else:
            excel_file = exporter_excel_diocese()
            if excel_file:
                st.download_button("📥 Télécharger l'export Excel", data=excel_file, file_name=f"export_rosaire_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    # Archives (consultation seule)
    elif menu == "📦 Archives":
        st.markdown('<h2 style="color:#1A237E;">📦 Archives du diocèse</h2>', unsafe_allow_html=True)
        archives = c.execute('''
            SELECT m.matricule, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire,
                   p.nom as paroisse, e.nom_equipe as equipe, a.auteur_nom
            FROM archives a
            JOIN membres m ON a.membre_id = m.id
            LEFT JOIN equipes e ON a.equipe_id = e.id
            LEFT JOIN paroisses p ON e.paroisse_id = p.id
            ORDER BY a.date_fin DESC
        ''').fetchall()
        if not archives:
            st.info("Aucune archive")
        else:
            for a in archives:
                situation_affichee = afficher_situation(a[3])
                icone = {"Déplacé":"📤","Radié":"🚫","Défunt":"🕊️"}.get(a[3],"📌")
                # Conversion sécurisée des dates
                date_debut_obj = convertir_en_date(a[4])
                date_fin_obj = convertir_en_date(a[5])
                duree = (date_fin_obj - date_debut_obj).days // 365 if (date_debut_obj and date_fin_obj) else 0
                with st.expander(f"{icone} {a[1]} {a[2]} ({a[0]}) – {situation_affichee} – a médité {duree} an(s) avec nous - de sept {date_debut_obj.year} à sept {date_fin_obj.year}"):
                    st.write(f"Ajouté par : {a[8]}")
                    st.write(f"Paroisse : {a[7]}")
                    if date_debut_obj and date_fin_obj:
                        st.write(f"Période : Sept {date_debut_obj.year} – Sept {date_fin_obj.year} ({duree} an(s))")
                    if a[6]:
                        st.write(f"Commentaire : {a[6]}")
    
    # Réinitialisation totale
    elif menu == "🗑️ Réinitialiser tout":
        st.markdown('<h2 style="color:#1A237E;">🗑️ RÉINITIALISATION COMPLÈTE</h2>', unsafe_allow_html=True)
        st.error("⚠️ ACTION IRRÉVERSIBLE !")
        with st.expander("🔴 Cliquez pour réinitialiser"):
            confirmation = st.text_input("Tapez 'SUPPRIMER' pour confirmer")
            if confirmation == "SUPPRIMER":
                if os.path.exists("photos"):
                    shutil.rmtree("photos")
                c.execute("DELETE FROM abonnements")
                c.execute("DELETE FROM archives")
                c.execute("DELETE FROM membres")
                c.execute("DELETE FROM equipes")
                c.execute("DELETE FROM paroisses")
                c.execute("DELETE FROM utilisateurs WHERE role != 'diocese'")
                conn.commit()
                st.success("Toutes les données ont été supprimées")
                st.balloons()
                st.rerun()

# ==================== PAROISSE ====================
elif st.session_state['role'] == 'paroisse':
    pid = st.session_state['paroisse_id']
    nom_paroisse = c.execute("SELECT nom FROM paroisses WHERE id=?", (pid,)).fetchone()[0]
    menu = st.sidebar.radio("Navigation", ["Ma paroisse", "Mes équipes", "Membres", "Statistiques", "Abonnements", "WhatsApp", "Export Excel", "Archives"])
    
    # Ma paroisse
    if menu == "Ma paroisse":
        st.markdown(f'<h2 style="color:#1A237E;">🏘️ {nom_paroisse}</h2>', unsafe_allow_html=True)
        p = c.execute("SELECT commune, ville, responsable, bureau FROM paroisses WHERE id=?", (pid,)).fetchone()
        if p:
            st.write(f"Commune : {p[0]}")
            st.write(f"Ville : {p[1]}")
            st.write(f"Responsable : {p[2]}")
            st.write(f"Bureau : {p[3]}")
    
    # Mes équipes
    elif menu == "Mes équipes":
        st.markdown(f'<h2 style="color:#1A237E;">👥 Équipes de {nom_paroisse}</h2>', unsafe_allow_html=True)
        info_paroisse = c.execute("SELECT nom, commune FROM paroisses WHERE id=?", (pid,)).fetchone()
        nom_clean = info_paroisse[0].lower()
        for mot in ["saint ", "sainte ", "notre-dame ", "dame ", "st ", "ste ", "nd "]:
            if nom_clean.startswith(mot):
                nom_clean = nom_clean[len(mot):]
        prefixe = sans_accents(nom_clean[:3] + info_paroisse[1][:3])
        with st.expander("➕ Créer une équipe"):
            with st.form("creer_equipe"):
                nom_eq = st.text_input("Nom de l'équipe (ex: 3, Jeune, Enfant)")
                responsable = st.text_input("Responsable")
                bureau = st.text_area("Bureau")
                if st.form_submit_button("Créer"):
                    if nom_eq and responsable:
                        nb = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
                        identifiant = f"{prefixe}eq{nb+1}"
                        mdp = generer_mot_de_passe()
                        c.execute("INSERT INTO equipes (nom_equipe, responsable, bureau, paroisse_id) VALUES (?,?,?,?)", (nom_eq, responsable, bureau, pid))
                        eid = c.lastrowid
                        c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id, equipe_id) VALUES (?,?,?,?,?)", (identifiant, hash_password(mdp), "equipe", pid, eid))
                        conn.commit()
                        st.success(f"✅ Équipe '{nom_eq}' créée")
                        st.code(f"Identifiant : {identifiant}\nMot de passe : {mdp}", language="text")
        equipes = c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        for eq in equipes:
            nb_membres = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eq[0],)).fetchone()[0]
            st.write(f"- **{eq[1]}** : {eq[2]} ({nb_membres}/10 membres)")
    
    # Membres
    elif menu == "Membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres de {nom_paroisse}</h2>', unsafe_allow_html=True)
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
        if not equipes:
            st.warning("Aucune équipe. Créez une équipe d'abord.")
        else:
            equipe_dict = {eq[1]: eq[0] for eq in equipes}
            choix = st.selectbox("Équipe", list(equipe_dict.keys()))
            eid = equipe_dict[choix]
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchone()[0]
            st.info(f"{nb}/10 membres")
            if nb < 10:
                with st.expander("➕ Ajouter un membre"):
                    with st.form("ajout_membre"):
                        col1, col2 = st.columns(2)
                        with col1:
                            nom = st.text_input("Nom")
                            prenom = st.text_input("Prénom")
                            naissance = st.date_input("Date de naissance", min_value=date(1940,1,1), max_value=date.today())
                        with col2:
                            whatsapp = st.text_input("WhatsApp")
                            photo = st.file_uploader("Photo", type=['jpg','png','jpeg'])
                            date_adhesion = st.date_input("Date d'adhésion", min_value=date(1940,1,1), max_value=date.today(), value=date.today())
                        if st.form_submit_button("Ajouter"):
                            if nom and prenom:
                                existant = c.execute("SELECT id FROM membres WHERE nom=? AND prenom=? AND date_naissance=? AND statut='actif'", (nom, prenom, naissance)).fetchone()
                                if existant:
                                    st.error("Ce membre existe déjà actif.")
                                else:
                                    matricule = generer_matricule_unique()
                                    c.execute("INSERT INTO membres (matricule, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id, statut) VALUES (?,?,?,?,?,?,?,?,?)", (matricule, nom, prenom, naissance, whatsapp, date_adhesion, pid, eid, 'actif'))
                                    mid = c.lastrowid
                                    if photo:
                                        chemin = sauvegarder_photo(photo, matricule)
                                        c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                    conn.commit()
                                    st.success(f"Ajouté ! Matricule: {matricule}")
                                    st.rerun()
            membres = c.execute("SELECT id, matricule, nom, prenom, whatsapp, photo_path, date_adhesion FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eid,)).fetchall()
            for m in membres:
                with st.expander(f"{m[2]} {m[3]} - {m[1]}"):
                    col1, col2 = st.columns([3,1])
                    col1.write(f"💬 WhatsApp: {m[4]}")
                    col1.write(f"📅 Adhésion: {m[6]}")
                    if m[5]:
                        col1.image(m[5], width=80)
                    with col2:
                        if st.button("✏️ Modifier", key=f"mod_{m[0]}"):
                            st.session_state['modif_membre_id'] = m[0]
                            st.rerun()
                        if st.button("📦 Archiver", key=f"arch_{m[0]}"):
                            st.session_state['archive_membre_id'] = m[0]
                            st.rerun()
                        if st.button("🔄 Transférer", key=f"transf_{m[0]}"):
                            st.session_state['transfert_membre_id'] = m[0]
                            st.rerun()
            # Gestion de l'archivage
            if 'archive_membre_id' in st.session_state:
                mid_arch = st.session_state['archive_membre_id']
                membre_arch = c.execute("SELECT nom, prenom, matricule, date_adhesion FROM membres WHERE id=?", (mid_arch,)).fetchone()
                if membre_arch:
                    st.warning(f"Archivage de {membre_arch[0]} {membre_arch[1]} ({membre_arch[2]})")
                    with st.form("form_archive"):
                        situation = st.radio("Situation", ["Déplacé", "Radié", "Défunt"])
                        annee_debut_arch = st.number_input("Année de début (Sept)", min_value=2000, max_value=date.today().year+5, value=date.today().year, step=1)
                        annee_fin_arch = st.number_input("Année de fin (Sept)", min_value=2000, max_value=date.today().year+10, value=date.today().year+1, step=1)
                        commentaire = st.text_area("Commentaire")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Confirmer l'archivage"):
                                if annee_fin_arch <= annee_debut_arch:
                                    st.error("L'année de fin doit être après l'année de début.")
                                else:
                                    date_debut_arch = date(annee_debut_arch, 10, 1)
                                    date_fin_arch = date(annee_fin_arch, 10, 1)
                                    archiver_membre(mid_arch, situation, date_debut_arch, date_fin_arch, commentaire,
                                                    st.session_state['user_id'], st.session_state['username'], 'paroisse', pid, eid)
                                    del st.session_state['archive_membre_id']
                                    st.success("Membre archivé")
                                    st.rerun()
                        with col2:
                            if st.form_submit_button("Annuler"):
                                del st.session_state['archive_membre_id']
                                st.rerun()


            # Gestion du transfert
            if 'transfert_membre_id' in st.session_state:
                mid_transfert = st.session_state['transfert_membre_id']
                membre_info = c.execute("SELECT nom, prenom, matricule, equipe_id FROM membres WHERE id=?", (mid_transfert,)).fetchone()
                if membre_info:
                    st.markdown("---")
                    st.subheader(f"🔄 Transfert de {membre_info[0]} {membre_info[1]} ({membre_info[2]})")
                    with st.form("form_transfert_paroisse"):
                        # Sélection de la paroisse de destination
                        paroisses = c.execute("SELECT id, nom FROM paroisses ORDER BY nom").fetchall()
                        paroisse_dest = st.selectbox("Paroisse de destination", paroisses, format_func=lambda x: x[1])
                        nouvelle_paroisse_id = paroisse_dest[0]
                        
                        # Sélection de l'équipe de destination dans cette paroisse
                        equipes_dest = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (nouvelle_paroisse_id,)).fetchall()
                        if equipes_dest:
                            equipe_dest = st.selectbox("Équipe de destination", equipes_dest, format_func=lambda x: x[1])
                            nouvelle_equipe_id = equipe_dest[0]
                        else:
                            st.error("Aucune équipe dans cette paroisse. Créez-en une d'abord.")
                            nouvelle_equipe_id = None
                        
                        motif = st.text_area("Motif du transfert (optionnel)")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Confirmer le transfert"):
                                if nouvelle_equipe_id:
                                    success, msg = transferer_membre(mid_transfert, nouvelle_paroisse_id, nouvelle_equipe_id, motif,
                                                                      st.session_state['user_id'], st.session_state['username'], 'paroisse')
                                    if success:
                                        st.success(msg)
                                        del st.session_state['transfert_membre_id']
                                        st.rerun()
                                    else:
                                        st.error(msg)
                        with col2:
                            if st.form_submit_button("Annuler"):
                                del st.session_state['transfert_membre_id']
                                st.rerun()



            # Modification de membre
            if 'modif_membre_id' in st.session_state:
                mid = st.session_state['modif_membre_id']
                membre = c.execute("SELECT nom, prenom, whatsapp, photo_path FROM membres WHERE id=?", (mid,)).fetchone()
                if membre:
                    st.markdown("---")
                    with st.form("modif_membre"):
                        new_nom = st.text_input("Nom", value=membre[0])
                        new_prenom = st.text_input("Prénom", value=membre[1])
                        new_whatsapp = st.text_input("WhatsApp", value=membre[2])
                        new_photo = st.file_uploader("Nouvelle photo", type=['jpg','png','jpeg'])
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Enregistrer"):
                                c.execute("UPDATE membres SET nom=?, prenom=?, whatsapp=? WHERE id=?", (new_nom, new_prenom, new_whatsapp, mid))
                                if new_photo:
                                    if membre[3] and os.path.exists(membre[3]):
                                        os.remove(membre[3])
                                    matricule = c.execute("SELECT matricule FROM membres WHERE id=?", (mid,)).fetchone()[0]
                                    chemin = sauvegarder_photo(new_photo, matricule)
                                    c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                conn.commit()
                                del st.session_state['modif_membre_id']
                                st.success("Membre modifié")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("Annuler"):
                                del st.session_state['modif_membre_id']
                                st.rerun()
    
    # Statistiques
    elif menu == "Statistiques":
        st.markdown(f'<h2 style="color:#1A237E;">📊 Statistiques de {nom_paroisse}</h2>', unsafe_allow_html=True)
        nb_eq = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
        nb_m = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("Équipes", nb_eq)
        col2.metric("Membres actifs", nb_m)
    
    # Abonnements (gestion)
    elif menu == "Abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 Gestion des abonnements - {nom_paroisse}</h2>', unsafe_allow_html=True)
        annee_debut = st.number_input("Année de début de la période", min_value=2020, max_value=date.today().year, value=date.today().year-1, step=1)
        st.write(f"**Période :** {periode_affichage(annee_debut)}")
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        if equipes:
            eq_dict = {eq[1]: eq[0] for eq in equipes}
            choix_eq = st.selectbox("Équipe", list(eq_dict.keys()))
            eid = eq_dict[choix_eq]
            membres = c.execute("SELECT id, nom, prenom, matricule FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eid,)).fetchall()
            for m in membres:
                deja = verifier_abonnement(m[0], annee_debut)
                if deja:
                    type_ = c.execute("SELECT type_abonnement FROM abonnements WHERE membre_id=? AND annee_debut=?", (m[0], annee_debut)).fetchone()
                    type_ = type_[0] if type_ else "abonnement"
                    st.info(f"{m[1]} {m[2]} ({m[3]}) – ✅ {type_} effectué")
                else:
                    with st.expander(f"{m[1]} {m[2]} ({m[3]}) – ❌ Non enregistré"):
                        # Remplacement des checkboxes par un radio
                        type_abo = st.radio("Type", ["Abonnement", "Réabonnement"], key=f"type_{m[0]}_{annee_debut}", horizontal=True)
                        montant = st.number_input("Montant (FCFA)", min_value=0, value=1000, step=500, key=f"mont_{m[0]}_{annee_debut}")
                        if st.button("Enregistrer", key=f"btn_{m[0]}_{annee_debut}"):
                            type_val = "abonnement" if type_abo == "Abonnement" else "reabonnement"
                            enregistrer_abonnement(m[0], annee_debut, montant, type_val)
                            st.success(f"{type_val} enregistré pour {m[1]} {m[2]}")
                            st.rerun()
            st.markdown("---")
            tab_liste = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
            with tab_liste[0]:
                abonnes = c.execute('''SELECT m.nom, m.prenom, m.matricule, a.date_paiement, a.montant
                                       FROM membres m
                                       JOIN abonnements a ON m.id=a.membre_id
                                       WHERE m.equipe_id=? AND a.annee_debut=? AND a.type_abonnement='abonnement' AND a.statut='paye'
                                       ORDER BY m.nom''', (eid, annee_debut)).fetchall()
                for a in abonnes:
                    st.write(f"- {a[0]} {a[1]} ({a[2]}) – a payé le {a[3]} : {a[4]} FCFA")
            with tab_liste[1]:
                reabonnes = c.execute('''SELECT m.nom, m.prenom, m.matricule, a.date_paiement, a.montant
                                         FROM membres m
                                         JOIN abonnements a ON m.id=a.membre_id
                                         WHERE m.equipe_id=? AND a.annee_debut=? AND a.type_abonnement='reabonnement' AND a.statut='paye'
                                         ORDER BY m.nom''', (eid, annee_debut)).fetchall()
                for r in reabonnes:
                    st.write(f"- {r[0]} {r[1]} ({r[2]}) – a payé le {r[3]} : {r[4]} FCFA")
            with tab_liste[2]:
                non_inscrits = c.execute('''SELECT m.nom, m.prenom, m.matricule
                                            FROM membres m
                                            WHERE m.equipe_id=? AND m.statut='actif' AND m.id NOT IN (
                                                SELECT a.membre_id FROM abonnements a WHERE a.annee_debut=? AND a.statut='paye'
                                            ) ORDER BY m.nom''', (eid, annee_debut)).fetchall()
                for n in non_inscrits:
                    st.write(f"- {n[0]} {n[1]} ({n[2]})")
    
    # WhatsApp
    elif menu == "WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Communications WhatsApp - {nom_paroisse}</h2>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🎂 Anniversaires", "📢 Rappels réabonnement"])
        with tab1:
            afficher_anniversaires_whatsapp()
        with tab2:
            annee_rappel = st.number_input("Année de début", min_value=2020, max_value=date.today().year+1, value=date.today().year, step=1, key="rappel_paroisse")
            equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
            if equipes:
                eq_dict = {eq[1]: eq[0] for eq in equipes}
                choix_eq = st.selectbox("Équipe", list(eq_dict.keys()))
                afficher_rappels_reabonnement_whatsapp(annee_rappel, equipe_id=eq_dict[choix_eq])
            else:
                st.info("Aucune équipe")
    
    # Export Excel
    elif menu == "Export Excel":
        st.markdown(f'<h2 style="color:#1A237E;">📊 Export des membres de {nom_paroisse}</h2>', unsafe_allow_html=True)
        membres = c.execute('''SELECT m.matricule, m.nom, m.prenom, m.date_naissance, m.whatsapp, m.date_adhesion, e.nom_equipe
                               FROM membres m
                               JOIN equipes e ON m.equipe_id = e.id
                               WHERE m.paroisse_id = ? AND m.statut='actif'
                               ORDER BY e.nom_equipe, m.nom''', (pid,)).fetchall()
        if membres:
            df = pd.DataFrame(membres, columns=["Matricule", "Nom", "Prénom", "Date naissance", "WhatsApp", "Date adhésion", "Équipe"])
            output = io.BytesIO()
            try:
                with pd.ExcelWriter(output, engine=None) as writer:
                    df.to_excel(writer, sheet_name=f"Membres_{nom_paroisse}", index=False)
                output.seek(0)
                st.download_button("📥 Télécharger Excel", data=output, file_name=f"membres_{nom_paroisse}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e:
                st.error(f"Erreur lors de la création de l'Excel : {e}")
        else:
            st.warning("Aucun membre actif")
    
    # Archives (lecture seule)
    elif menu == "Archives":
        st.markdown(f'<h2 style="color:#1A237E; ; white-space: nowrap;">📦 Archives de la paroisse {nom_paroisse}</h2>', unsafe_allow_html=True)
        archives = c.execute('''
            SELECT m.matricule, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire,
                   e.nom_equipe as equipe, a.auteur_nom
            FROM archives a
            JOIN membres m ON a.membre_id = m.id
            LEFT JOIN equipes e ON a.equipe_id = e.id
            WHERE a.paroisse_id = ?
            ORDER BY a.date_fin DESC
        ''', (pid,)).fetchall()
        if not archives:
            st.info("Aucune archive pour cette paroisse")
        else:
            for a in archives:
                situation_affichee = afficher_situation(a[3])
                icone = {"Déplacé":"📤","Radié":"🚫","Défunt":"🕊️"}.get(a[3],"📌")
                date_debut_obj = convertir_en_date(a[4])
                date_fin_obj = convertir_en_date(a[5])
                duree = (date_fin_obj - date_debut_obj).days // 365 if (date_debut_obj and date_fin_obj) else 0
                with st.expander(f"{icone} {a[1]} {a[2]} ({a[0]}) – {situation_affichee} – a médité {duree} an(s) avec nous - d'sept {date_debut_obj.year} à sept {date_fin_obj.year}"):
                    st.write(f"Ajouté par : {a[7]}")
                    if date_debut_obj and date_fin_obj:
                        st.write(f"Période : Sept {date_debut_obj.year} – Sept {date_fin_obj.year} ({duree} an(s))")
                    if a[6]:
                        st.write(f"Commentaire : {a[6]}")

# ==================== ÉQUIPE ====================
elif st.session_state['role'] == 'equipe':
    eid = st.session_state['equipe_id']
    equipe_info = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (eid,)).fetchone()
    nom_equipe = equipe_info[0] if equipe_info else "Mon équipe"
    menu = st.sidebar.radio("Navigation", ["Mon équipe", "Mes membres", "Abonnements", "WhatsApp", "Archives"])
    
    # Mon équipe
    if menu == "Mon équipe":
        st.markdown(f'<h2 style="color:#1A237E;">👥 {nom_equipe}</h2>', unsafe_allow_html=True)
        eq = c.execute("SELECT responsable, bureau FROM equipes WHERE id=?", (eid,)).fetchone()
        if eq:
            st.write(f"**Responsable :** {eq[0]}")
            st.write(f"**Bureau :** {eq[1]}")
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchone()[0]
            st.metric("Effectif", f"{nb}/10")
    
    # Mes membres
    elif menu == "Mes membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres de {nom_equipe}</h2>', unsafe_allow_html=True)
        nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchone()[0]
        st.info(f"{nb}/10 membres")
        if nb < 10:
            with st.expander("➕ Ajouter un membre"):
                with st.form("ajout_membre_eq"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nom = st.text_input("Nom")
                        prenom = st.text_input("Prénom")
                        naissance = st.date_input("Date de naissance", min_value=date(1940,1,1), max_value=date.today())
                    with col2:
                        whatsapp = st.text_input("WhatsApp")
                        photo = st.file_uploader("Photo", type=['jpg','png','jpeg'])
                        date_adhesion = st.date_input("Date d'adhésion", min_value=date(1940,1,1), max_value=date.today(), value=date.today())
                    if st.form_submit_button("Ajouter"):
                        if nom and prenom:
                            existant = c.execute("SELECT id FROM membres WHERE nom=? AND prenom=? AND date_naissance=? AND statut='actif'", (nom, prenom, naissance)).fetchone()
                            if existant:
                                st.error("Membre déjà actif")
                            else:
                                matricule = generer_matricule_unique()
                                paroisse_id = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()[0]
                                c.execute("INSERT INTO membres (matricule, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id, statut) VALUES (?,?,?,?,?,?,?,?,?)", (matricule, nom, prenom, naissance, whatsapp, date_adhesion, paroisse_id, eid, 'actif'))
                                mid = c.lastrowid
                                if photo:
                                    chemin = sauvegarder_photo(photo, matricule)
                                    c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                conn.commit()
                                st.success(f"Ajouté ! Matricule: {matricule}")
                                st.rerun()
        membres = c.execute("SELECT id, matricule, nom, prenom, whatsapp, photo_path, date_adhesion FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eid,)).fetchall()
        for m in membres:
            with st.expander(f"{m[2]} {m[3]} - {m[1]}"):
                col1, col2 = st.columns([3,1])
                col1.write(f"💬 WhatsApp: {m[4]}")
                col1.write(f"📅 Adhésion: {m[6]}")
                if m[5]:
                    col1.image(m[5], width=80)
                with col2:
                    if st.button("✏️ Modifier", key=f"mod_eq_{m[0]}"):
                        st.session_state['modif_membre_id'] = m[0]
                        st.rerun()
                    # Remplacer Supprimer par Archiver
                    if st.button("📦 Archiver", key=f"arch_eq_{m[0]}"):
                        st.session_state['archive_membre_id'] = m[0]
                        st.rerun()
        # Gestion archivage
        if 'archive_membre_id' in st.session_state:
            mid_arch = st.session_state['archive_membre_id']
            membre_arch = c.execute("SELECT nom, prenom, matricule, date_adhesion FROM membres WHERE id=?", (mid_arch,)).fetchone()
            if membre_arch:
                st.warning(f"Archivage de {membre_arch[0]} {membre_arch[1]} ({membre_arch[2]})")
                with st.form("form_archive_eq"):
                    situation = st.radio("Situation", ["Déplacé", "Radié", "Défunt"])
                    annee_debut_arch = st.number_input("Année de début (Sept)", min_value=2000, max_value=date.today().year+5, value=date.today().year, step=1)
                    annee_fin_arch = st.number_input("Année de fin (Sept)", min_value=2000, max_value=date.today().year+10, value=date.today().year+1, step=1)
                    commentaire = st.text_area("Commentaire")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Confirmer l'archivage"):
                            if annee_fin_arch <= annee_debut_arch:
                                st.error("L'année de fin doit être après l'année de début.")
                            else:
                                date_debut_arch = date(annee_debut_arch, 10, 1)
                                date_fin_arch = date(annee_fin_arch, 10, 1)
                                paroisse_id = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()[0]
                                archiver_membre(mid_arch, situation, date_debut_arch, date_fin_arch, commentaire,
                                                st.session_state['user_id'], st.session_state['username'], 'equipe', paroisse_id, eid)
                                del st.session_state['archive_membre_id']
                                st.success("Membre archivé")
                                st.rerun()
                    with col2:
                        if st.form_submit_button("Annuler"):
                            del st.session_state['archive_membre_id']
                            st.rerun()
        # Modification de membre
        if 'modif_membre_id' in st.session_state:
            mid = st.session_state['modif_membre_id']
            membre = c.execute("SELECT nom, prenom, whatsapp, photo_path FROM membres WHERE id=?", (mid,)).fetchone()
            if membre:
                with st.form("modif_membre_eq"):
                    new_nom = st.text_input("Nom", value=membre[0])
                    new_prenom = st.text_input("Prénom", value=membre[1])
                    new_whatsapp = st.text_input("WhatsApp", value=membre[2])
                    new_photo = st.file_uploader("Nouvelle photo", type=['jpg','png','jpeg'])
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Enregistrer"):
                            c.execute("UPDATE membres SET nom=?, prenom=?, whatsapp=? WHERE id=?", (new_nom, new_prenom, new_whatsapp, mid))
                            if new_photo:
                                if membre[3] and os.path.exists(membre[3]):
                                    os.remove(membre[3])
                                matricule = c.execute("SELECT matricule FROM membres WHERE id=?", (mid,)).fetchone()[0]
                                chemin = sauvegarder_photo(new_photo, matricule)
                                c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                            conn.commit()
                            del st.session_state['modif_membre_id']
                            st.success("Membre modifié")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("Annuler"):
                            del st.session_state['modif_membre_id']
                            st.rerun()
    
    # Abonnements
    elif menu == "Abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 Gestion des abonnements - {nom_equipe}</h2>', unsafe_allow_html=True)
        annee_debut = st.number_input("Année de début de la période", min_value=2020, max_value=date.today().year, value=date.today().year-1, step=1)
        st.write(f"**Période :** {periode_affichage(annee_debut)}")
        membres = c.execute("SELECT id, nom, prenom, matricule FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eid,)).fetchall()
        for m in membres:
            deja = verifier_abonnement(m[0], annee_debut)
            if deja:
                type_ = c.execute("SELECT type_abonnement FROM abonnements WHERE membre_id=? AND annee_debut=?", (m[0], annee_debut)).fetchone()
                type_ = type_[0] if type_ else "abonnement"
                st.info(f"{m[1]} {m[2]} ({m[3]}) – ✅ {type_}")
            else:
                with st.expander(f"{m[1]} {m[2]} ({m[3]}) – ❌ Non enregistré"):
                    type_abo = st.radio("Type", ["Abonnement", "Réabonnement"], key=f"type_eq_{m[0]}_{annee_debut}", horizontal=True)
                    montant = st.number_input("Montant (FCFA)", min_value=0, value=1000, step=500, key=f"mont_eq_{m[0]}_{annee_debut}")
                    if st.button("Enregistrer", key=f"btn_eq_{m[0]}_{annee_debut}"):
                        type_val = "abonnement" if type_abo == "Abonnement" else "reabonnement"
                        enregistrer_abonnement(m[0], annee_debut, montant, type_val)
                        st.success(f"{type_val} enregistré")
                        st.rerun()
        st.markdown("---")
        tab_liste = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
        with tab_liste[0]:
            abonnes = c.execute('''SELECT m.nom, m.prenom, m.matricule, a.date_paiement, a.montant
                                   FROM membres m
                                   JOIN abonnements a ON m.id=a.membre_id
                                   WHERE m.equipe_id=? AND a.annee_debut=? AND a.type_abonnement='abonnement' AND a.statut='paye'
                                   ORDER BY m.nom''', (eid, annee_debut)).fetchall()
            for a in abonnes:
                st.write(f"- {a[0]} {a[1]} ({a[2]}) – a payé le {a[3]} : {a[4]} FCFA")
        with tab_liste[1]:
            reabonnes = c.execute('''SELECT m.nom, m.prenom, m.matricule, a.date_paiement, a.montant
                                     FROM membres m
                                     JOIN abonnements a ON m.id=a.membre_id
                                     WHERE m.equipe_id=? AND a.annee_debut=? AND a.type_abonnement='reabonnement' AND a.statut='paye'
                                     ORDER BY m.nom''', (eid, annee_debut)).fetchall()
            for r in reabonnes:
                st.write(f"- {r[0]} {r[1]} ({r[2]}) – a payé le {r[3]} : {r[4]} FCFA")
        with tab_liste[2]:
            non_inscrits = c.execute('''SELECT m.nom, m.prenom, m.matricule
                                        FROM membres m
                                        WHERE m.equipe_id=? AND m.statut='actif' AND m.id NOT IN (
                                            SELECT a.membre_id FROM abonnements a WHERE a.annee_debut=? AND a.statut='paye'
                                        ) ORDER BY m.nom''', (eid, annee_debut)).fetchall()
            for n in non_inscrits:
                st.write(f"- {n[0]} {n[1]} ({n[2]})")
    
    # WhatsApp
    elif menu == "WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Communications WhatsApp - {nom_equipe}</h2>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🎂 Anniversaires", "📢 Rappels réabonnement"])
        with tab1:
            afficher_anniversaires_whatsapp()
        with tab2:
            annee_rappel = st.number_input("Année de début", min_value=2020, max_value=date.today().year+1, value=date.today().year, step=1, key="rappel_equipe")
            afficher_rappels_reabonnement_whatsapp(annee_rappel, equipe_id=eid)
    
    # Archives (avec gestion complète)
    elif menu == "Archives":
        st.markdown(f'<h2 style="color:#1A237E;">📦 Archives de {nom_equipe}</h2>', unsafe_allow_html=True)
        membres_actifs = c.execute("SELECT id, nom, prenom, matricule FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eid,)).fetchall()
        archives_equipe = c.execute('''
            SELECT a.id, m.nom, m.prenom, m.matricule, a.situation, a.date_debut, a.date_fin, a.commentaire, m.id as membre_id
            FROM archives a
            JOIN membres m ON a.membre_id = m.id
            WHERE a.equipe_id = ?
            ORDER BY a.date_fin DESC
        ''', (eid,)).fetchall()
        
        # Ajout d'une archive
        with st.expander("➕ Archiver un membre de l'équipe"):
            if not membres_actifs:
                st.warning("Aucun membre actif à archiver.")
            else:
                with st.form("archive_membre"):
                    membre_choisi = st.selectbox("Membre à archiver", membres_actifs, format_func=lambda x: f"{x[1]} {x[2]} ({x[3]})")
                    situation = st.radio("Situation", ["Déplacé", "Radié", "Défunt"])
                    col1, col2 = st.columns(2)
                    with col1:
                        annee_debut_arch = st.number_input("Année de début (Sept)", min_value=2000, max_value=date.today().year+5, value=date.today().year, step=1)
                    with col2:
                        annee_fin_arch = st.number_input("Année de fin (Sept)", min_value=2000, max_value=date.today().year+10, value=date.today().year+1, step=1)
                    commentaire = st.text_area("Commentaire (optionnel)")
                    
                    if st.form_submit_button("Archiver"):
                        if annee_fin_arch <= annee_debut_arch:
                            st.error("❌ L'année de fin doit être au moins un an après l'année de début.")
                        else:
                            date_debut_obj = date(annee_debut_arch, 10, 1)
                            date_fin_obj = date(annee_fin_arch, 10, 1)
                            paroisse_id = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()[0]
                            archiver_membre(membre_choisi[0], situation, date_debut_obj, date_fin_obj, commentaire,
                                            st.session_state['user_id'], st.session_state['username'], 'equipe', paroisse_id, eid)
                            st.success(f"✅ {membre_choisi[1]} {membre_choisi[2]} archivé.")
                            st.rerun()
        
        # Gestion des archives existantes
        if archives_equipe:
            st.subheader("✏️ Gérer les archives de votre équipe")
            for arch in archives_equipe:
                arch_id, nom, prenom, matricule, situation, date_debut_raw, date_fin_raw, commentaire, membre_id = arch
                date_debut_obj = convertir_en_date(date_debut_raw)
                date_fin_obj = convertir_en_date(date_fin_raw)
                if date_debut_obj and date_fin_obj:
                    duree = (date_fin_obj - date_debut_obj).days // 365
                    annee_debut_aff = date_debut_obj.year
                    annee_fin_aff = date_fin_obj.year
                else:
                    duree = 0
                    annee_debut_aff = "?"
                    annee_fin_aff = "?"
                
                situation_affichee = afficher_situation(situation)
                with st.expander(f"{nom} {prenom} ({matricule}) – {situation_affichee} – a médité {duree} an(s) avec nous - de sept {annee_debut_aff} à sept {annee_fin_aff}"):
                    with st.form(f"edit_arch_{arch_id}"):
                        new_situation = st.selectbox("Situation", ["Déplacé", "Radié", "Défunt"],
                                                     index=["Déplacé","Radié","Défunt"].index(situation) if situation in ["Déplacé","Radié","Défunt"] else 0)
                        col1, col2 = st.columns(2)
                        with col1:
                            new_annee_debut = st.number_input("Année début (Sept)", min_value=2000, max_value=date.today().year+5,
                                                               value=date_debut_obj.year if date_debut_obj else date.today().year, step=1)
                        with col2:
                            new_annee_fin = st.number_input("Année fin (Sept)", min_value=2000, max_value=date.today().year+10,
                                                            value=date_fin_obj.year if date_fin_obj else date.today().year+1, step=1)
                        new_comment = st.text_area("Commentaire", value=commentaire or "")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Mettre à jour"):
                                if new_annee_fin <= new_annee_debut:
                                    st.error("L'année de fin doit être au moins un an après l'année de début.")
                                else:
                                    new_date_debut = date(new_annee_debut, 10, 1)
                                    new_date_fin = date(new_annee_fin, 10, 1)
                                    c.execute("UPDATE archives SET situation=?, date_debut=?, date_fin=?, commentaire=? WHERE id=?",
                                              (new_situation, new_date_debut, new_date_fin, new_comment, arch_id))
                                    conn.commit()
                                    st.success("Archive modifiée")
                                    st.rerun()
                        with col2:
                            if situation in ("Déplacé", "Radié"):
                                if st.form_submit_button("🔄 Réintégrer (devient actif)"):
                                    c.execute("UPDATE membres SET statut='actif' WHERE id=?", (membre_id,))
                                    c.execute("DELETE FROM archives WHERE id=?", (arch_id,))
                                    conn.commit()
                                    st.success(f"{nom} {prenom} a été réintégré(e).")
                                    st.rerun()
                            else:
                                st.info("Un défunt ne peut pas être réintégré.")
        else:
            st.info("Aucune archive pour cette équipe.")
