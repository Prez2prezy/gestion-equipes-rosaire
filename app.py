import streamlit as st
import sqlite3
from datetime import date
import os
import hashlib
import random
import string
from PIL import Image
import shutil

# --- Configuration ---
st.set_page_config(page_title="Gestion des Équipes du Rosaire - Diocèse de Grand-Bassam", layout="wide")

# --- CSS ---
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
</style>
""", unsafe_allow_html=True)

# --- Base de données ---
conn = sqlite3.connect('gestion_religieuse.db', check_same_thread=False)
c = conn.cursor()

# --- Fonctions ---
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

def membre_existe_deja(nom, prenom, date_naissance, exclude_id=None):
    if exclude_id:
        query = "SELECT matricule FROM membres WHERE nom=? AND prenom=? AND date_naissance=? AND id != ?"
        params = (nom, prenom, date_naissance, exclude_id)
    else:
        query = "SELECT matricule FROM membres WHERE nom=? AND prenom=? AND date_naissance=?"
        params = (nom, prenom, date_naissance)
    result = c.execute(query, params).fetchone()
    return result[0] if result else None

def equipe_existe(paroisse_id, nom_equipe, exclude_id=None):
    if exclude_id:
        query = "SELECT id FROM equipes WHERE paroisse_id=? AND nom_equipe=? AND id != ?"
        params = (paroisse_id, nom_equipe, exclude_id)
    else:
        query = "SELECT id FROM equipes WHERE paroisse_id=? AND nom_equipe=?"
        params = (paroisse_id, nom_equipe)
    return c.execute(query, params).fetchone() is not None

def paroisse_existe(nom, commune, ville, exclude_id=None):
    if exclude_id:
        query = "SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=? AND id != ?"
        params = (nom, commune, ville, exclude_id)
    else:
        query = "SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=?"
        params = (nom, commune, ville)
    return c.execute(query, params).fetchone() is not None

def sans_accents(texte):
    """Supprime les accents d'un texte"""
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

def nettoyer_nom_paroisse(nom):
    """Supprime les préfixes religieux (Saint, Sainte, Notre-Dame, etc.)"""
    mots_a_supprimer = [
        "saint", "sainte", "Notre", "Dame", "St", "Ste", "notre-dame", "dame", 
        "st", "ste", "nd", "notre dame",
        "monseigneur", "mgr", "père", "pere"
    ]
    nom_clean = nom.lower()
    for mot in mots_a_supprimer:
        if nom_clean.startswith(mot + " "):
            nom_clean = nom_clean[len(mot)+1:]
        elif nom_clean.startswith(mot):
            nom_clean = nom_clean[len(mot):]
    nom_clean = nom_clean.strip()
    if len(nom_clean) >= 3:
        return nom_clean[:3]
    else:
        return nom_clean

# --- Création des tables ---
c.execute('''CREATE TABLE IF NOT EXISTS diocese (id INTEGER PRIMARY KEY, nom TEXT, responsable TEXT, bureau TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS paroisses (id INTEGER PRIMARY KEY, nom TEXT, commune TEXT, ville TEXT, responsable TEXT, bureau TEXT, diocese_id INTEGER, FOREIGN KEY(diocese_id) REFERENCES diocese(id))''')
c.execute('''CREATE TABLE IF NOT EXISTS equipes (id INTEGER PRIMARY KEY, nom_equipe TEXT, responsable TEXT, bureau TEXT, paroisse_id INTEGER, max_membres INTEGER DEFAULT 10, FOREIGN KEY(paroisse_id) REFERENCES paroisses(id))''')
c.execute('''CREATE TABLE IF NOT EXISTS membres (id INTEGER PRIMARY KEY, matricule TEXT UNIQUE, nom TEXT, prenom TEXT, date_naissance DATE, telephone TEXT, whatsapp TEXT, date_adhesion DATE, photo_path TEXT, paroisse_id INTEGER, equipe_id INTEGER, FOREIGN KEY(paroisse_id) REFERENCES paroisses(id), FOREIGN KEY(equipe_id) REFERENCES equipes(id))''')
c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, diocese_id INTEGER, paroisse_id INTEGER, equipe_id INTEGER, FOREIGN KEY(diocese_id) REFERENCES diocese(id), FOREIGN KEY(paroisse_id) REFERENCES paroisses(id), FOREIGN KEY(equipe_id) REFERENCES equipes(id))''')
conn.commit()

# --- Initialisation ---
c.execute("SELECT COUNT(*) FROM diocese")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO diocese (nom, responsable, bureau) VALUES (?, ?, ?)", ("GRAND-BASSAM", "À définir", "À définir"))
    conn.commit()

c.execute("SELECT COUNT(*) FROM utilisateurs WHERE role='diocese'")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?, ?, ?, ?)", ("diocese", hash_password("admin123"), "diocese", 1))
    conn.commit()

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
            st.sidebar.markdown("### 📿 Équipes du Rosaire")
    else:
        st.sidebar.markdown("### 📿 Équipes du Rosaire")
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🏛️ DIOCÈSE DE GRAND-BASSAM")
    st.sidebar.markdown("---")

# --- Connexion ---
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

# --- Titre ---
st.markdown('<h1 style="color:#1A237E;">📿 Gestion des Équipes du Rosaire</h1>', unsafe_allow_html=True)
st.markdown("---")

# ==================== DIOCÈSE ====================
if st.session_state['role'] == 'diocese':
    
    menu = st.sidebar.radio("Navigation", ["Voir diocèse", "Créer paroisses", "Gérer paroisses", "Rechercher par matricule", "Gérer les accès", "Statistiques", "🗑️ Réinitialiser tout"])
    
    if menu == "Voir diocèse":
        st.markdown('<h2 style="color:#1A237E;">🏛️ DIOCÈSE DE GRAND-BASSAM</h2>', unsafe_allow_html=True)
        d = c.execute("SELECT responsable, bureau FROM diocese WHERE id=?", (st.session_state['diocese_id'],)).fetchone()
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
                    if paroisse_existe(nom, commune, ville):
                        st.error(f"❌ La paroisse '{nom}' à {commune} ({ville}) existe déjà !")
                    else:
                        c.execute("INSERT INTO paroisses (nom, commune, ville, responsable, bureau, diocese_id) VALUES (?, ?, ?, ?, ?, ?)",
                                  (nom, commune, ville, responsable, bureau, 1))
                        pid = c.lastrowid
                        username = f"paroisse_{pid}"
                        mdp = generer_mot_de_passe()
                        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id, paroisse_id) VALUES (?, ?, ?, ?, ?)",
                                  (username, hash_password(mdp), "paroisse", 1, pid))
                        conn.commit()
                        st.success(f"✅ Paroisse '{nom}' créée")
                        st.markdown(f"""
                        <div style="background-color:#e8f5e9; padding:15px; border-radius:10px; margin:10px 0;">
                            <strong>📋 Identifiants à remettre au responsable</strong><br>
                            🔑 Identifiant : <code>{username}</code><br>
                            🔒 Mot de passe : <code>{mdp}</code>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.error("Veuillez remplir tous les champs (nom, commune, ville, responsable)")
    
    elif menu == "Gérer paroisses":
        st.markdown('<h2 style="color:#1A237E;">📋 Consultation des paroisses</h2>', unsafe_allow_html=True)
        paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau FROM paroisses WHERE diocese_id=?", (1,)).fetchall()
        for p in paroisses:
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (p[0],)).fetchone()[0]
            with st.expander(f"🏛️ {p[1]} ({p[2]} / {p[3]}) - {nb_equipes} équipe(s)"):
                st.write(f"**Responsable:** {p[4]}")
                st.write(f"**Bureau:** {p[5]}")
                equipes = c.execute("SELECT nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (p[0],)).fetchall()
                if equipes:
                    st.write("**Équipes :**")
                    for eq in equipes:
                        st.write(f"- **{eq[0]}** (Responsable: {eq[1]})")
                else:
                    st.info("Aucune équipe")
    
    elif menu == "Rechercher par matricule":
        st.markdown('<h2 style="color:#1A237E;">🔍 Recherche par matricule</h2>', unsafe_allow_html=True)
        matricule = st.text_input("Matricule (ex: BN-ABCDE)")
        if matricule:
            m = c.execute('''SELECT m.matricule, m.nom, m.prenom, m.telephone, p.nom, e.nom_equipe, m.photo_path
                             FROM membres m
                             JOIN paroisses p ON m.paroisse_id = p.id
                             JOIN equipes e ON m.equipe_id = e.id
                             WHERE m.matricule = ?''', (matricule.upper(),)).fetchone()
            if m:
                st.success("Membre trouvé")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**{m[1]} {m[2]}** - Matricule: {m[0]}")
                    st.write(f"Tél: {m[3]} - Paroisse: {m[4]} - Équipe: {m[5]}")
                with col2:
                    if m[6] and os.path.exists(m[6]):
                        st.image(m[6], width=100)
            else:
                st.error("Non trouvé")
    
    elif menu == "Gérer les accès":
        st.markdown('<h2 style="color:#1A237E;">🔐 Gestion des accès</h2>', unsafe_allow_html=True)
        st.markdown("### 🏘️ Paroisses")
        paroisses = c.execute("SELECT id, nom, responsable FROM paroisses WHERE diocese_id=?", (1,)).fetchall()
        for p in paroisses:
            user = c.execute("SELECT id, username FROM utilisateurs WHERE paroisse_id=? AND role='paroisse'", (p[0],)).fetchone()
            if user:
                with st.expander(f"🏛️ {p[1]} - {p[2]}"):
                    st.write(f"**Identifiant:** `{user[1]}`")
                    if st.button(f"🔄 Réinitialiser", key=f"reset_par_{p[0]}"):
                        nouveau = generer_mot_de_passe()
                        c.execute("UPDATE utilisateurs SET password=? WHERE id=?", (hash_password(nouveau), user[0]))
                        conn.commit()
                        st.success(f"✅ Mot de passe réinitialisé !")
                        st.markdown(f"""
                        <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; margin:10px 0;">
                            <strong>🔑 Nouveau mot de passe pour {p[1]}</strong><br>
                            <code style="font-size:1.2em;">{nouveau}</code>
                        </div>
                        """, unsafe_allow_html=True)
                        st.info("📝 Notez ce mot de passe avant de continuer")
    
    elif menu == "Statistiques":
        st.markdown('<h2 style="color:#1A237E;">📊 Statistiques</h2>', unsafe_allow_html=True)
        nb_p = c.execute("SELECT COUNT(*) FROM paroisses").fetchone()[0]
        nb_e = c.execute("SELECT COUNT(*) FROM equipes").fetchone()[0]
        nb_m = c.execute("SELECT COUNT(*) FROM membres").fetchone()[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Paroisses", nb_p)
        col2.metric("Équipes", nb_e)
        col3.metric("Membres", nb_m)
    
    elif menu == "🗑️ Réinitialiser tout":
        st.markdown('<h2 style="color:#1A237E;">🗑️ RÉINITIALISATION COMPLÈTE</h2>', unsafe_allow_html=True)
        st.error("⚠️ ACTION IRRÉVERSIBLE ! Cette opération va supprimer TOUTES les données :")
        st.markdown("- Toutes les paroisses")
        st.markdown("- Toutes les équipes")
        st.markdown("- Tous les membres")
        st.markdown("- Tous les comptes (sauf le diocèse)")
        st.markdown("- Toutes les photos")
        
        with st.expander("🔴 Cliquez ici pour réinitialiser (action définitive)"):
            st.warning("Cette action est irréversible. Toutes les données seront perdues.")
            confirmation = st.text_input("Tapez 'SUPPRIMER' pour confirmer")
            if confirmation == "SUPPRIMER":
                if os.path.exists("photos"):
                    shutil.rmtree("photos")
                    os.makedirs("photos")
                c.execute("DELETE FROM membres")
                c.execute("DELETE FROM equipes")
                c.execute("DELETE FROM paroisses")
                c.execute("DELETE FROM utilisateurs WHERE role != 'diocese'")
                conn.commit()
                st.success("✅ Toutes les données ont été supprimées avec succès !")
                st.info("Il ne reste que le compte diocèse. Vous pouvez recréer vos paroisses.")
                st.balloons()
                st.rerun()

# ==================== PAROISSE ====================
elif st.session_state['role'] == 'paroisse':
    
    pid = st.session_state['paroisse_id']
    nom_paroisse = c.execute("SELECT nom FROM paroisses WHERE id=?", (pid,)).fetchone()
    if nom_paroisse:
        nom_paroisse = nom_paroisse[0]
    else:
        nom_paroisse = "Ma paroisse"
    
    menu = st.sidebar.radio("Navigation", ["Ma paroisse", "Mes équipes", "Membres", "Statistiques", "Modifier paroisse", "Gérer les accès"])
    
    if menu == "Ma paroisse":
        st.markdown(f'<h2 style="color:#1A237E;">🏘️ {nom_paroisse}</h2>', unsafe_allow_html=True)
        p = c.execute("SELECT commune, ville, responsable, bureau FROM paroisses WHERE id=?", (pid,)).fetchone()
        if p:
            st.write(f"**Commune:** {p[0]}")
            st.write(f"**Ville:** {p[1]}")
            st.write(f"**Responsable:** {p[2]}")
            st.write(f"**Bureau:** {p[3]}")

    elif menu == "Mes équipes":
        st.markdown(f'<h2 style="color:#1A237E;">👥 Équipes de {nom_paroisse}</h2>', unsafe_allow_html=True)
        
        # Récupérer les infos de la paroisse
        paroisse_info = c.execute("SELECT nom, commune FROM paroisses WHERE id=?", (pid,)).fetchone()
        
        if paroisse_info:
            # Nettoyer le nom de la paroisse (enlever Saint, Sainte, etc.)
            nom_clean = paroisse_info[0].lower()
            mots_a_supprimer = ["saint ", "sainte ", "Notre", "Dame", "St", "Ste", "notre-dame ", "dame ", "st ", "ste ", "nd "]
            for mot in mots_a_supprimer:
                if nom_clean.startswith(mot):
                    nom_clean = nom_clean[len(mot):]
            nom_clean = nom_clean.strip()
            prefixe_paroisse = sans_accents(nom_clean[:3])
            
            # 3 premières lettres de la commune sans accents
            prefixe_commune = sans_accents(paroisse_info[1][:3])
            
            # Assembler le préfixe
            prefixe = f"{prefixe_paroisse}{prefixe_commune}"
            
            # Compter les équipes existantes
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
            prochain_numero = nb_equipes + 1
            identifiant_suggest = f"{prefixe}eq{prochain_numero}"
            
            st.info(f"💡 Format des identifiants : **{prefixe}eqX** (ex: {identifiant_suggest})")
        else:
            st.error("Erreur : paroisse non trouvée")
            st.stop()
        
        with st.expander("➕ Créer équipes"):
            with st.form("ajout_eq"):
                col1, col2 = st.columns(2)
                with col1:
                    nom_eq = st.text_input("Nom de l'équipe (ex: 3, Jeune, Enfant)")
                    responsable = st.text_input("Responsable")
                with col2:
                    bureau = st.text_area("Bureau")
                
                # Mot de passe auto-généré
                mdp_auto = generer_mot_de_passe()
                st.caption(f"🔑 Mot de passe généré : `{mdp_auto}`")
                
                if st.form_submit_button("Créer équipes"):
                    if nom_eq and responsable:
                        if equipe_existe(pid, nom_eq):
                            st.error("❌ Cette équipe existe déjà dans votre paroisse")
                        else:
                            # Compter à nouveau pour avoir le bon numéro
                            nb_equipes_avant = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
                            nouveau_numero = nb_equipes_avant + 1
                            identifiant = f"{prefixe}eq{nouveau_numero}"
                            
                            c.execute("INSERT INTO equipes (nom_equipe, responsable, bureau, paroisse_id) VALUES (?, ?, ?, ?)",
                                    (nom_eq, responsable, bureau, pid))
                            eid = c.lastrowid
                            c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id, equipe_id) VALUES (?, ?, ?, ?, ?)",
                                    (identifiant, hash_password(mdp_auto), "equipe", pid, eid))
                            conn.commit()
                            
                            st.success(f"✅ Équipe '{nom_eq}' créée")
                            st.markdown(f"""
                            <div style="background-color:#e8f5e9; padding:15px; border-radius:10px; margin:10px 0;">
                                <strong>📋 Identifiants à remettre au responsable</strong><br>
                                🔑 Identifiant : <code>{identifiant}</code><br>
                                🔒 Mot de passe : <code>{mdp_auto}</code>
                            </div>
                            """, unsafe_allow_html=True)
                            st.rerun()
                    else:
                        st.error("Le nom de l'équipe et le responsable sont obligatoires")
        
        # Liste des équipes existantes
        equipes = c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=? ORDER BY id", (pid,)).fetchall()
        if equipes:
            st.markdown("---")
            st.subheader("📋 Équipes existantes")
            for eq in equipes:
                user = c.execute("SELECT username FROM utilisateurs WHERE equipe_id=? AND role='equipe'", (eq[0],)).fetchone()
                identifiant = user[0] if user else "inconnu"
                st.write(f"- **{eq[1]}** - Responsable: {eq[2]} (`{identifiant}`)")
        else:
            st.info("Aucune équipe créée pour le moment")
    
    elif menu == "Membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres de {nom_paroisse}</h2>', unsafe_allow_html=True)
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        if equipes:
            equipe_dict = {eq[1]: eq[0] for eq in equipes}
            choix = st.selectbox("Choisir une équipe", list(equipe_dict.keys()))
            eid = equipe_dict[choix]
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=?", (eid,)).fetchone()[0]
            st.info(f"{nb}/10 membres")
            
            if nb < 10:
                with st.expander("➕ Ajouter un membre"):
                    with st.form(f"add_membre_{st.session_state['form_counter']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            nom = st.text_input("Nom")
                            prenom = st.text_input("Prénom")
                            naissance = st.date_input("Date de naissance", min_value=date(1930,1,1), max_value=date.today())
                            telephone = st.text_input("Téléphone")
                        with col2:
                            whatsapp = st.text_input("WhatsApp")
                            photo = st.file_uploader("Photo", type=['jpg', 'png', 'jpeg'])
                        if st.form_submit_button("Ajouter"):
                            if nom and prenom:
                                existant = membre_existe_deja(nom, prenom, naissance)
                                if existant:
                                    st.error(f"❌ Ce membre existe déjà avec le matricule {existant}")
                                else:
                                    matricule = generer_matricule_unique()
                                    c.execute("INSERT INTO membres (matricule, nom, prenom, date_naissance, telephone, whatsapp, date_adhesion, paroisse_id, equipe_id) VALUES (?,?,?,?,?,?,?,?,?)",
                                              (matricule, nom, prenom, naissance, telephone, whatsapp, date.today(), pid, eid))
                                    mid = c.lastrowid
                                    if photo:
                                        chemin = sauvegarder_photo(photo, matricule)
                                        c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                    conn.commit()
                                    st.success(f"✅ Membre ajouté ! Matricule: {matricule}")
                                    st.session_state['form_counter'] = st.session_state.get('form_counter', 0) + 1
                                    st.rerun()
                            else:
                                st.error("Le nom et le prénom sont obligatoires")
            
            # Liste des membres
            membres = c.execute("SELECT id, matricule, nom, prenom, telephone, whatsapp, photo_path FROM membres WHERE equipe_id=? ORDER BY nom", (eid,)).fetchall()
            if membres:
                for m in membres:
                    with st.expander(f"**{m[2]} {m[3]}** - {m[1]}"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"📞 Tél: {m[4]}, WhatsApp: {m[5]}")
                            if m[6] and os.path.exists(m[6]):
                                st.image(m[6], width=80)
                        with col2:
                            if st.button("✏️ Modifier", key=f"mod_par_{m[0]}"):
                                st.session_state['modif_membre_id'] = m[0]
                                st.session_state['modif_equipe_id'] = eid
                                st.rerun()
                            if st.button("🗑️ Supprimer", key=f"del_par_{m[0]}"):
                                c.execute("DELETE FROM membres WHERE id=?", (m[0],))
                                conn.commit()
                                st.success("Membre supprimé")
                                st.rerun()
            else:
                st.info("Aucun membre dans cette équipe")
            
            # Modification
            if 'modif_membre_id' in st.session_state:
                mid = st.session_state['modif_membre_id']
                membre = c.execute("SELECT matricule, nom, prenom, telephone, whatsapp FROM membres WHERE id=?", (mid,)).fetchone()
                if membre:
                    st.markdown("---")
                    st.markdown(f"### ✏️ Modifier {membre[1]} {membre[2]}")
                    with st.form("modif_membre"):
                        new_nom = st.text_input("Nom", value=membre[1])
                        new_prenom = st.text_input("Prénom", value=membre[2])
                        new_tel = st.text_input("Téléphone", value=membre[3])
                        new_whats = st.text_input("WhatsApp", value=membre[4])
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Enregistrer"):
                                c.execute("UPDATE membres SET nom=?, prenom=?, telephone=?, whatsapp=? WHERE id=?",
                                          (new_nom, new_prenom, new_tel, new_whats, mid))
                                conn.commit()
                                del st.session_state['modif_membre_id']
                                st.success("Membre modifié")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("❌ Annuler"):
                                del st.session_state['modif_membre_id']
                                st.rerun()
        else:
            st.warning("⚠️ Créez d'abord une équipe dans 'Mes équipes'")
    
    elif menu == "Statistiques":
        st.markdown(f'<h2 style="color:#1A237E;">📊 Statistiques de {nom_paroisse}</h2>', unsafe_allow_html=True)
        nb_eq = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
        nb_m = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=?", (pid,)).fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("Équipes", nb_eq)
        col2.metric("Membres", nb_m)
    
    elif menu == "Modifier paroisse":
        st.markdown(f'<h2 style="color:#1A237E;">✏️ Modifier {nom_paroisse}</h2>', unsafe_allow_html=True)
        p = c.execute("SELECT nom, commune, ville, responsable, bureau FROM paroisses WHERE id=?", (pid,)).fetchone()
        if p:
            with st.form("modif_paroisse"):
                col1, col2 = st.columns(2)
                with col1:
                    nom = st.text_input("Nom", value=p[0])
                    commune = st.text_input("Commune", value=p[1])
                    responsable = st.text_input("Responsable", value=p[3])
                with col2:
                    ville = st.text_input("Ville", value=p[2])
                    bureau = st.text_area("Bureau", value=p[4])
                if st.form_submit_button("Enregistrer"):
                    if (nom != p[0] or commune != p[1] or ville != p[2]) and paroisse_existe(nom, commune, ville, exclude_id=pid):
                        st.error("❌ Une autre paroisse avec ce nom, commune et ville existe déjà")
                    else:
                        c.execute("UPDATE paroisses SET nom=?, commune=?, ville=?, responsable=?, bureau=? WHERE id=?",
                                  (nom, commune, ville, responsable, bureau, pid))
                        conn.commit()
                        st.success("Paroisse modifiée")
                        st.rerun()
    
    elif menu == "Gérer les accès":
        st.markdown(f'<h2 style="color:#1A237E;">🔐 Gestion des accès des équipes</h2>', unsafe_allow_html=True)
        equipes = c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        if equipes:
            for eq in equipes:
                user = c.execute("SELECT id, username FROM utilisateurs WHERE equipe_id=? AND role='equipe'", (eq[0],)).fetchone()
                if user:
                    with st.expander(f"👥 {eq[1]} - {eq[2]}"):
                        st.write(f"**Identifiant:** `{user[1]}`")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"🔄 Réinitialiser", key=f"reset_eq_{eq[0]}"):
                                nouveau = generer_mot_de_passe()
                                c.execute("UPDATE utilisateurs SET password=? WHERE id=?", (hash_password(nouveau), user[0]))
                                conn.commit()
                                st.success(f"✅ Mot de passe réinitialisé !")
                                st.markdown(f"""
                                <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; margin:10px 0;">
                                    <strong>🔑 Nouveau mot de passe pour {eq[1]}</strong><br>
                                    <code style="font-size:1.2em;">{nouveau}</code>
                                </div>
                                """, unsafe_allow_html=True)
                        with col2:
                            if st.button(f"🗑️ Supprimer équipe", key=f"del_eq_{eq[0]}"):
                                c.execute("DELETE FROM membres WHERE equipe_id=?", (eq[0],))
                                c.execute("DELETE FROM equipes WHERE id=?", (eq[0],))
                                c.execute("DELETE FROM utilisateurs WHERE id=?", (user[0],))
                                conn.commit()
                                st.success(f"Équipe {eq[1]} supprimée")
                                st.rerun()
        else:
            st.info("Aucune équipe dans cette paroisse")

# ==================== ÉQUIPE ====================
elif st.session_state['role'] == 'equipe':
    
    eid = st.session_state['equipe_id']
    equipe_info = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (eid,)).fetchone()
    if equipe_info:
        nom_equipe = equipe_info[0]
    else:
        nom_equipe = "Mon équipe"
    
    menu = st.sidebar.radio("Navigation", ["Mon équipe", "Mes membres", "Modifier mon équipe"])
    
    if menu == "Mon équipe":
        st.markdown(f'<h2 style="color:#1A237E;">👥 {nom_equipe}</h2>', unsafe_allow_html=True)
        eq = c.execute("SELECT responsable, bureau FROM equipes WHERE id=?", (eid,)).fetchone()
        if eq:
            st.write(f"**Responsable:** {eq[0]}")
            st.write(f"**Bureau:** {eq[1]}")
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=?", (eid,)).fetchone()[0]
            st.metric("Effectif", f"{nb}/10")
    
    elif menu == "Mes membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres de {nom_equipe}</h2>', unsafe_allow_html=True)
        nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=?", (eid,)).fetchone()[0]
        st.info(f"{nb}/10 membres")
        
        if nb < 10:
            with st.expander("➕ Ajouter un membre"):
                with st.form(f"add_membre_eq_{st.session_state['form_counter']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nom = st.text_input("Nom")
                        prenom = st.text_input("Prénom")
                        naissance = st.date_input("Date de naissance", min_value=date(1930,1,1), max_value=date.today())
                        telephone = st.text_input("Téléphone")
                    with col2:
                        whatsapp = st.text_input("WhatsApp")
                        photo = st.file_uploader("Photo", type=['jpg', 'png', 'jpeg'])
                    if st.form_submit_button("Ajouter"):
                        if nom and prenom:
                            existant = membre_existe_deja(nom, prenom, naissance)
                            if existant:
                                st.error(f"❌ Ce membre existe déjà avec le matricule {existant}")
                            else:
                                matricule = generer_matricule_unique()
                                pid = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()[0]
                                c.execute("INSERT INTO membres (matricule, nom, prenom, date_naissance, telephone, whatsapp, date_adhesion, paroisse_id, equipe_id) VALUES (?,?,?,?,?,?,?,?,?)",
                                          (matricule, nom, prenom, naissance, telephone, whatsapp, date.today(), pid, eid))
                                mid = c.lastrowid
                                if photo:
                                    chemin = sauvegarder_photo(photo, matricule)
                                    c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                conn.commit()
                                st.success(f"✅ Membre ajouté ! Matricule: {matricule}")
                                st.session_state['form_counter'] = st.session_state.get('form_counter', 0) + 1
                                st.rerun()
                        else:
                            st.error("Le nom et le prénom sont obligatoires")
        
        # Liste des membres
        membres = c.execute("SELECT id, matricule, nom, prenom, telephone, whatsapp, photo_path FROM membres WHERE equipe_id=? ORDER BY nom", (eid,)).fetchall()
        if membres:
            for m in membres:
                with st.expander(f"**{m[2]} {m[3]}** - {m[1]}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📞 Tél: {m[4]}, WhatsApp: {m[5]}")
                        if m[6] and os.path.exists(m[6]):
                            st.image(m[6], width=80)
                    with col2:
                        if st.button("✏️ Modifier", key=f"mod_eq_{m[0]}"):
                            st.session_state['modif_membre_id'] = m[0]
                            st.rerun()
                        if st.button("🗑️ Supprimer", key=f"del_eq_{m[0]}"):
                            c.execute("DELETE FROM membres WHERE id=?", (m[0],))
                            conn.commit()
                            st.success("Membre supprimé")
                            st.rerun()
        else:
            st.info("Aucun membre dans cette équipe")
        
        # Modification
        if 'modif_membre_id' in st.session_state:
            mid = st.session_state['modif_membre_id']
            membre = c.execute("SELECT matricule, nom, prenom, telephone, whatsapp FROM membres WHERE id=?", (mid,)).fetchone()
            if membre:
                st.markdown("---")
                st.markdown(f"### ✏️ Modifier {membre[1]} {membre[2]}")
                with st.form("modif_membre_eq"):
                    new_nom = st.text_input("Nom", value=membre[1])
                    new_prenom = st.text_input("Prénom", value=membre[2])
                    new_tel = st.text_input("Téléphone", value=membre[3])
                    new_whats = st.text_input("WhatsApp", value=membre[4])
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Enregistrer"):
                            c.execute("UPDATE membres SET nom=?, prenom=?, telephone=?, whatsapp=? WHERE id=?",
                                      (new_nom, new_prenom, new_tel, new_whats, mid))
                            conn.commit()
                            del st.session_state['modif_membre_id']
                            st.success("Membre modifié")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("❌ Annuler"):
                            del st.session_state['modif_membre_id']
                            st.rerun()
    
    elif menu == "Modifier mon équipe":
        st.markdown(f'<h2 style="color:#1A237E;">✏️ Modifier {nom_equipe}</h2>', unsafe_allow_html=True)
        eq = c.execute("SELECT nom_equipe, responsable, bureau FROM equipes WHERE id=?", (eid,)).fetchone()
        if eq:
            with st.form("modif_equipe"):
                nouveau_nom = st.text_input("Nom de l'équipe", value=eq[0])
                nouveau_resp = st.text_input("Responsable", value=eq[1])
                nouveau_bureau = st.text_area("Bureau", value=eq[2])
                if st.form_submit_button("Enregistrer"):
                    c.execute("UPDATE equipes SET nom_equipe=?, responsable=?, bureau=? WHERE id=?",
                              (nouveau_nom, nouveau_resp, nouveau_bureau, eid))
                    conn.commit()
                    st.success("Équipe modifiée")
                    st.rerun()
