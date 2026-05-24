import streamlit as st
import sqlite3
from datetime import date
import os
import hashlib
import random
import string
from PIL import Image

# --- Configuration ---
st.set_page_config(page_title="Gestion des Équipes du Rosaire - Diocèse de Grand-Bassam", layout="wide")

# --- CSS pour forcer le thème CLAIR et supprimer "See More" ---
st.markdown("""
<style>
    /* Forcer le fond blanc et texte sombre */
    .stApp {
        background-color: #FFFFFF !important;
    }
    .main > div {
        background-color: #FFFFFF !important;
    }
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #1A237E !important;
    }
    /* Supprimer le "See More" des expanders */
    .streamlit-expanderHeader span:last-child {
        display: none !important;
    }
    /* Forcer les couleurs des métriques */
    .stMetric label, .stMetric .stMarkdown {
        color: #1A237E !important;
    }
    /* Forcer la sidebar en blanc */
    .stSidebar {
        background-color: #FFFFFF !important;
    }
    .stSidebar .stMarkdown, .stSidebar label {
        color: #1A237E !important;
    }
    /* Forcer les inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        background-color: #FFFFFF !important;
        color: #1A237E !important;
    }
    /* Supprimer le "See More" sur tous les titres */
    button[data-testid="baseButton-header"] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Connexion base de données ---
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
        with open(chemin, "wb") as f:
            f.write(photo_fichier.getbuffer())
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

# --- Création des tables ---
c.execute('''CREATE TABLE IF NOT EXISTS diocese
             (id INTEGER PRIMARY KEY, nom TEXT, responsable TEXT, bureau TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS paroisses
             (id INTEGER PRIMARY KEY, nom TEXT, commune TEXT, ville TEXT,
              responsable TEXT, bureau TEXT, diocese_id INTEGER,
              FOREIGN KEY(diocese_id) REFERENCES diocese(id))''')

c.execute('''CREATE TABLE IF NOT EXISTS equipes
             (id INTEGER PRIMARY KEY, nom_equipe TEXT, responsable TEXT, bureau TEXT,
              paroisse_id INTEGER, max_membres INTEGER DEFAULT 10,
              FOREIGN KEY(paroisse_id) REFERENCES paroisses(id))''')

c.execute('''CREATE TABLE IF NOT EXISTS membres
             (id INTEGER PRIMARY KEY, matricule TEXT UNIQUE, nom TEXT, prenom TEXT,
              date_naissance DATE, telephone TEXT, whatsapp TEXT, date_adhesion DATE,
              photo_path TEXT, paroisse_id INTEGER, equipe_id INTEGER,
              FOREIGN KEY(paroisse_id) REFERENCES paroisses(id),
              FOREIGN KEY(equipe_id) REFERENCES equipes(id))''')

c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs
             (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT,
              role TEXT, diocese_id INTEGER, paroisse_id INTEGER, equipe_id INTEGER,
              FOREIGN KEY(diocese_id) REFERENCES diocese(id),
              FOREIGN KEY(paroisse_id) REFERENCES paroisses(id),
              FOREIGN KEY(equipe_id) REFERENCES equipes(id))''')
conn.commit()

# --- Initialisation ---
c.execute("SELECT COUNT(*) FROM diocese")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO diocese (nom, responsable, bureau) VALUES (?, ?, ?)",
              ("GRAND-BASSAM", "À définir", "À définir"))
    conn.commit()

c.execute("SELECT COUNT(*) FROM utilisateurs WHERE role='diocese'")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?, ?, ?, ?)",
              ("diocese", hash_password("admin123"), "diocese", 1))
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
        user = c.execute("SELECT * FROM utilisateurs WHERE username=? AND password=?", 
                         (username, hash_password(password))).fetchone()
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

# ==================== TITRE PRINCIPAL ====================
st.markdown('<h1 style="color:#1A237E;">📿 Gestion des Équipes du Rosaire</h1>', unsafe_allow_html=True)
st.markdown("---")

# ==================== DIOCÈSE ====================
if st.session_state['role'] == 'diocese':
    
    menu = st.sidebar.radio("Navigation", 
                            ["Voir diocèse", "Créer paroisses", "Gérer paroisses", 
                             "Rechercher par matricule", "Gérer les accès", "Statistiques"])
    
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
                if nom and responsable:
                    c.execute("INSERT INTO paroisses (nom, commune, ville, responsable, bureau, diocese_id) VALUES (?, ?, ?, ?, ?, ?)",
                              (nom, commune, ville, responsable, bureau, 1))
                    pid = c.lastrowid
                    username = f"paroisse_{pid}"
                    mdp = generer_mot_de_passe()
                    c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id, paroisse_id) VALUES (?, ?, ?, ?, ?)",
                              (username, hash_password(mdp), "paroisse", 1, pid))
                    conn.commit()
                    st.success(f"✅ Paroisse '{nom}' créée")
                    st.info(f"Identifiant: {username} | Mot de passe: {mdp}")
    
    elif menu == "Gérer paroisses":
        st.markdown('<h2 style="color:#1A237E;">📋 Consultation des paroisses</h2>', unsafe_allow_html=True)
        paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau FROM paroisses WHERE diocese_id=?", (1,)).fetchall()
        for p in paroisses:
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (p[0],)).fetchone()[0]
            with st.expander(f"🏛️ {p[1]} ({p[2]} / {p[3]}) - {nb_equipes} équipe(s)"):
                st.write(f"**Responsable:** {p[4]}")
                st.write(f"**Bureau:** {p[5]}")
                equipes = c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (p[0],)).fetchall()
                if equipes:
                    st.write("**Équipes :**")
                    for eq in equipes:
                        st.write(f"- **{eq[1]}** (Responsable: {eq[2]})")
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
                        st.code(f"Nouveau mot de passe: {nouveau}")
                        st.rerun()
    
    elif menu == "Statistiques":
        st.markdown('<h2 style="color:#1A237E;">📊 Statistiques</h2>', unsafe_allow_html=True)
        nb_p = c.execute("SELECT COUNT(*) FROM paroisses").fetchone()[0]
        nb_e = c.execute("SELECT COUNT(*) FROM equipes").fetchone()[0]
        nb_m = c.execute("SELECT COUNT(*) FROM membres").fetchone()[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Paroisses", nb_p)
        col2.metric("Équipes", nb_e)
        col3.metric("Membres", nb_m)

# ==================== PAROISSE ====================
elif st.session_state['role'] == 'paroisse':
    
    pid = st.session_state['paroisse_id']
    nom_paroisse = c.execute("SELECT nom FROM paroisses WHERE id=?", (pid,)).fetchone()[0]
    
    menu = st.sidebar.radio("Navigation", ["Ma paroisse", "Mes équipes", "Membres", "Statistiques", "Modifier paroisse", "Gérer les accès"])
    
    if menu == "Ma paroisse":
        st.markdown(f'<h2 style="color:#1A237E;">🏘️ {nom_paroisse}</h2>', unsafe_allow_html=True)
        p = c.execute("SELECT commune, ville, responsable, bureau FROM paroisses WHERE id=?", (pid,)).fetchone()
        st.write(f"**Commune:** {p[0]}")
        st.write(f"**Ville:** {p[1]}")
        st.write(f"**Responsable:** {p[2]}")
        st.write(f"**Bureau:** {p[3]}")
    
    elif menu == "Mes équipes":
        st.markdown(f'<h2 style="color:#1A237E;">👥 Équipes de {nom_paroisse}</h2>', unsafe_allow_html=True)
        with st.expander("➕ Créer équipes"):
            with st.form("ajout_eq"):
                nom_eq = st.text_input("Nom (ex: 3, Jeune, Enfant)")
                responsable = st.text_input("Responsable")
                bureau = st.text_area("Bureau")
                mdp = st.text_input("Mot de passe", type="password")
                if st.form_submit_button("Créer équipes"):
                    if nom_eq and mdp:
                        if equipe_existe(pid, nom_eq):
                            st.error("Existe déjà")
                        else:
                            c.execute("INSERT INTO equipes (nom_equipe, responsable, bureau, paroisse_id) VALUES (?, ?, ?, ?)",
                                      (nom_eq, responsable, bureau, pid))
                            eid = c.lastrowid
                            c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id, equipe_id) VALUES (?, ?, ?, ?, ?)",
                                      (f"equipe_{eid}", hash_password(mdp), "equipe", pid, eid))
                            conn.commit()
                            st.success(f"✅ Équipe '{nom_eq}' créée")
                            st.info(f"Identifiant: equipe_{eid} | Mot de passe: {mdp}")
                            st.rerun()
        
        equipes = c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        for eq in equipes:
            st.write(f"- **{eq[1]}** : {eq[2]}")
    
    elif menu == "Membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres de {nom_paroisse}</h2>', unsafe_allow_html=True)
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        if equipes:
            choix = st.selectbox("Équipe", [e[1] for e in equipes])
            eid = [e[0] for e in equipes if e[1] == choix][0]
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=?", (eid,)).fetchone()[0]
            st.info(f"{nb}/10 membres")
            
            if nb < 10:
                with st.expander("➕ Ajouter"):
                    with st.form(f"add_{st.session_state['form_counter']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            nom = st.text_input("Nom")
                            prenom = st.text_input("Prénom")
                            naissance = st.date_input("Naissance", min_value=date(1930,1,1))
                        with col2:
                            tel = st.text_input("Téléphone")
                            whats = st.text_input("WhatsApp")
                            photo = st.file_uploader("Photo", type=['jpg','png'])
                        if st.form_submit_button("Ajouter"):
                            if nom and prenom:
                                existant = membre_existe_deja(nom, prenom, naissance)
                                if existant:
                                    st.error(f"Existe déjà: {existant}")
                                else:
                                    matricule = generer_matricule_unique()
                                    c.execute("INSERT INTO membres (matricule, nom, prenom, date_naissance, telephone, whatsapp, date_adhesion, paroisse_id, equipe_id) VALUES (?,?,?,?,?,?,?,?,?)",
                                              (matricule, nom, prenom, naissance, tel, whats, date.today(), pid, eid))
                                    mid = c.lastrowid
                                    if photo:
                                        chemin = sauvegarder_photo(photo, matricule)
                                        c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                    conn.commit()
                                    st.success(f"Ajouté ! Matricule: {matricule}")
                                    st.session_state['form_counter'] += 1
                                    st.rerun()
            
            membres = c.execute("SELECT id, matricule, nom, prenom, telephone, whatsapp, photo_path FROM membres WHERE equipe_id=?", (eid,)).fetchall()
            for m in membres:
                with st.expander(f"{m[2]} {m[3]} - {m[1]}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"Tél: {m[4]}, WhatsApp: {m[5]}")
                        if m[6] and os.path.exists(m[6]):
                            st.image(m[6], width=80)
                    with col2:
                        if st.button("✏️ Modifier", key=f"mod_{m[0]}"):
                            st.session_state['modif_membre_id'] = m[0]
                            st.session_state['modif_equipe_id'] = eid
                            st.rerun()
                        if st.button("🗑️ Supprimer", key=f"del_{m[0]}"):
                            c.execute("DELETE FROM membres WHERE id=?", (m[0],))
                            conn.commit()
                            st.rerun()
            
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
                                st.success("Modifié")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("❌ Annuler"):
                                del st.session_state['modif_membre_id']
                                st.rerun()
    
    elif menu == "Statistiques":
        st.markdown(f'<h2 style="color:#1A237E;">📊 Statistiques de {nom_paroisse}</h2>', unsafe_allow_html=True)
        nb_e = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
        nb_m = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=?", (pid,)).fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("Équipes", nb_e)
        col2.metric("Membres", nb_m)
    
    elif menu == "Modifier paroisse":
        st.markdown(f'<h2 style="color:#1A237E;">✏️ Modifier {nom_paroisse}</h2>', unsafe_allow_html=True)
        p = c.execute("SELECT nom, commune, ville, responsable, bureau FROM paroisses WHERE id=?", (pid,)).fetchone()
        with st.form("modif_paroisse"):
            nom = st.text_input("Nom", value=p[0])
            commune = st.text_input("Commune", value=p[1])
            ville = st.text_input("Ville", value=p[2])
            responsable = st.text_input("Responsable", value=p[3])
            bureau = st.text_area("Bureau", value=p[4])
            if st.form_submit_button("Enregistrer"):
                c.execute("UPDATE paroisses SET nom=?, commune=?, ville=?, responsable=?, bureau=? WHERE id=?",
                          (nom, commune, ville, responsable, bureau, pid))
                conn.commit()
                st.success("Modifié")
                st.rerun()
    
    elif menu == "Gérer les accès":
        st.markdown(f'<h2 style="color:#1A237E;">🔐 Gestion des accès des équipes</h2>', unsafe_allow_html=True)
        equipes = c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        for eq in equipes:
            user = c.execute("SELECT id, username FROM utilisateurs WHERE equipe_id=? AND role='equipe'", (eq[0],)).fetchone()
            if user:
                with st.expander(f"👥 {eq[1]} - {eq[2]}"):
                    st.write(f"**Identifiant:** `{user[1]}`")
                    col1, col2 = st.columns