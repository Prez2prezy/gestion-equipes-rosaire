import streamlit as st
import sqlite3
from datetime import date
import os
import hashlib
import random
import string
from PIL import Image
import shutil
import pandas as pd
import io
import csv
from io import StringIO

# --- Configuration ---
st.set_page_config(page_title="Gestionnaire des Équipes du Rosaire - Diocèse de Grand-Bassam", layout="wide")

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

def supprimer_photo(photo_path):
    if photo_path and os.path.exists(photo_path):
        os.remove(photo_path)

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

def exporter_excel_diocese():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau FROM paroisses").fetchall()
        if paroisses:
            df_paroisses = pd.DataFrame(paroisses, columns=["ID", "Nom", "Commune", "Ville", "Responsable", "Bureau"])
            df_paroisses.to_excel(writer, sheet_name="Paroisses", index=False)
        
        equipes = c.execute('''SELECT e.id, e.nom_equipe, e.responsable, e.bureau, p.nom as paroisse, e.max_membres
                               FROM equipes e
                               JOIN paroisses p ON e.paroisse_id = p.id''').fetchall()
        if equipes:
            df_equipes = pd.DataFrame(equipes, columns=["ID", "Nom équipe", "Responsable", "Bureau", "Paroisse", "Max membres"])
            df_equipes.to_excel(writer, sheet_name="Equipes", index=False)
        
        membres = c.execute('''SELECT m.matricule, m.nom, m.prenom, m.date_naissance, m.whatsapp, 
                                      m.date_adhesion, p.nom as paroisse, e.nom_equipe as equipe
                               FROM membres m
                               JOIN paroisses p ON m.paroisse_id = p.id
                               JOIN equipes e ON m.equipe_id = e.id
                               ORDER BY p.nom, e.nom_equipe, m.nom''').fetchall()
        if membres:
            df_membres = pd.DataFrame(membres, columns=["Matricule", "Nom", "Prénom", "Date naissance", "WhatsApp", "Date adhésion", "Paroisse", "Équipe"])
            df_membres.to_excel(writer, sheet_name="Membres", index=False)
        
        abonnements = c.execute('''SELECT a.id, m.matricule, m.nom, m.prenom, a.annee, a.date_paiement, a.montant, a.statut
                                   FROM abonnements a
                                   JOIN membres m ON a.membre_id = m.id
                                   ORDER BY a.annee DESC, m.nom''').fetchall()
        if abonnements:
            df_abonnements = pd.DataFrame(abonnements, columns=["ID", "Matricule", "Nom", "Prénom", "Année", "Date paiement", "Montant", "Statut"])
            df_abonnements.to_excel(writer, sheet_name="Abonnements", index=False)
    
    output.seek(0)
    return output

# --- Fonctions pour les réabonnements ---
def enregistrer_abonnement(membre_id, annee, montant=0):
    date_paiement = date.today()
    existant = c.execute("SELECT id FROM abonnements WHERE membre_id=? AND annee=?", (membre_id, annee)).fetchone()
    if existant:
        c.execute("UPDATE abonnements SET date_paiement=?, montant=?, statut='paye' WHERE id=?", (date_paiement, montant, existant[0]))
    else:
        c.execute('''INSERT INTO abonnements (membre_id, annee, date_paiement, montant, statut)
                     VALUES (?, ?, ?, ?, ?)''',
                  (membre_id, annee, date_paiement, montant, 'paye'))
    conn.commit()

def verifier_abonnement(membre_id, annee):
    result = c.execute('''SELECT id FROM abonnements 
                          WHERE membre_id = ? AND annee = ? AND statut = 'paye' ''',
                       (membre_id, annee)).fetchone()
    return result is not None

def get_statut_abonnement(membre_id, annee_courante):
    if verifier_abonnement(membre_id, annee_courante):
        return "✅ À jour"
    else:
        return "❌ En retard"

# --- Création des tables (sans telephone) ---
c.execute('''CREATE TABLE IF NOT EXISTS diocese (id INTEGER PRIMARY KEY, nom TEXT, responsable TEXT, bureau TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS paroisses (id INTEGER PRIMARY KEY, nom TEXT, commune TEXT, ville TEXT, responsable TEXT, bureau TEXT, diocese_id INTEGER, FOREIGN KEY(diocese_id) REFERENCES diocese(id))''')
c.execute('''CREATE TABLE IF NOT EXISTS equipes (id INTEGER PRIMARY KEY, nom_equipe TEXT, responsable TEXT, bureau TEXT, paroisse_id INTEGER, max_membres INTEGER DEFAULT 10, FOREIGN KEY(paroisse_id) REFERENCES paroisses(id))''')
c.execute('''CREATE TABLE IF NOT EXISTS membres (id INTEGER PRIMARY KEY, matricule TEXT UNIQUE, nom TEXT, prenom TEXT, date_naissance DATE, whatsapp TEXT, date_adhesion DATE, photo_path TEXT, paroisse_id INTEGER, equipe_id INTEGER, FOREIGN KEY(paroisse_id) REFERENCES paroisses(id), FOREIGN KEY(equipe_id) REFERENCES equipes(id))''')
c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, diocese_id INTEGER, paroisse_id INTEGER, equipe_id INTEGER, FOREIGN KEY(diocese_id) REFERENCES diocese(id), FOREIGN KEY(paroisse_id) REFERENCES paroisses(id), FOREIGN KEY(equipe_id) REFERENCES equipes(id))''')
c.execute('''CREATE TABLE IF NOT EXISTS abonnements (id INTEGER PRIMARY KEY, membre_id INTEGER, annee INTEGER, date_paiement DATE, montant REAL DEFAULT 0, statut TEXT DEFAULT 'non_paye', FOREIGN KEY(membre_id) REFERENCES membres(id))''')
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
            st.sidebar.markdown("### 📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE")
    else:
        st.sidebar.markdown("### 📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE")
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

# --- Titre principal ---
st.markdown('<h1 style="color:#1A237E;">📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE</h1>', unsafe_allow_html=True)
st.markdown("---")

# ==================== DIOCÈSE ====================
if st.session_state['role'] == 'diocese':
    
    menu = st.sidebar.radio("Navigation", ["Voir diocèse", "Créer paroisses", "Gérer paroisses", "Rechercher par matricule", "Gérer les accès", "Statistiques", "📅 Réabonnements", "📊 Export Excel", "🗑️ Réinitialiser tout"])
    
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
            m = c.execute('''SELECT m.matricule, m.nom, m.prenom, m.whatsapp, p.nom, e.nom_equipe, m.photo_path
                             FROM membres m
                             JOIN paroisses p ON m.paroisse_id = p.id
                             JOIN equipes e ON m.equipe_id = e.id
                             WHERE m.matricule = ?''', (matricule.upper(),)).fetchone()
            if m:
                st.success("Membre trouvé")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**{m[1]} {m[2]}** - Matricule: {m[0]}")
                    st.write(f"💬 WhatsApp: {m[3]} - Paroisse: {m[4]} - Équipe: {m[5]}")
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
        col1.metric("🏘️ Paroisses", nb_p)
        col2.metric("👥 Équipes", nb_e)
        col3.metric("👤 Membres", nb_m)
        
        st.markdown("---")
        st.subheader("📊 Répartition des membres par paroisse")
        repartition = c.execute('''SELECT p.nom, COUNT(m.id) as nb
                                   FROM paroisses p
                                   LEFT JOIN membres m ON m.paroisse_id = p.id
                                   GROUP BY p.id
                                   ORDER BY nb DESC''').fetchall()
        if repartition:
            valeurs = [r[1] for r in repartition]
            max_val = max(valeurs) if valeurs else 1
            for nom, val in repartition:
                st.write(f"**{nom}** : {val} membre(s)")
                st.progress(val / max_val if max_val > 0 else 0)
    
    elif menu == "📅 Réabonnements":
        st.markdown('<h2 style="color:#1A237E;">📅 Suivi des réabonnements - Diocèse</h2>', unsafe_allow_html=True)
        st.info("Consultation des listes des paroisses (lecture seule)")
        
        annee_courante = date.today().year
        annee_selectionnee = st.number_input("Année", min_value=2020, max_value=annee_courante+1, value=annee_courante, step=1)
        
        paroisses = c.execute("SELECT id, nom FROM paroisses WHERE diocese_id=?", (1,)).fetchall()
        
        total_membres = c.execute("SELECT COUNT(*) FROM membres").fetchone()[0]
        total_payes = c.execute("SELECT COUNT(*) FROM abonnements WHERE annee=? AND statut='paye'", (annee_selectionnee,)).fetchone()[0]
        
        col1, col2 = st.columns(2)
        col1.metric("📊 Total membres diocèse", total_membres)
        col2.metric("✅ Total à jour", total_payes, delta=f"{total_payes/total_membres*100:.0f}%" if total_membres > 0 else "0%")
        
        st.markdown("---")
        
        if total_payes > 0:
            if st.button("📥 Exporter tous les paiements en CSV"):
                paiements = c.execute('''SELECT m.matricule, m.nom, m.prenom, p.nom as paroisse, e.nom_equipe as equipe,
                                                a.annee, a.date_paiement, a.montant
                                         FROM abonnements a
                                         JOIN membres m ON a.membre_id = m.id
                                         JOIN paroisses p ON m.paroisse_id = p.id
                                         JOIN equipes e ON m.equipe_id = e.id
                                         WHERE a.annee = ? AND a.statut = 'paye'
                                         ORDER BY p.nom, e.nom_equipe, m.nom''', (annee_selectionnee,)).fetchall()
                
                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(["Matricule", "Nom", "Prénom", "Paroisse", "Équipe", "Année", "Date paiement", "Montant"])
                for p in paiements:
                    writer.writerow(p)
                st.download_button("Télécharger", output.getvalue(), f"paiements_{annee_selectionnee}.csv", "text/csv")
        
        for p in paroisses:
            with st.expander(f"🏛️ {p[1]}"):
                total_paroisse = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=?", (p[0],)).fetchone()[0]
                payes_paroisse = c.execute('''SELECT COUNT(*) FROM abonnements a
                                              JOIN membres m ON a.membre_id = m.id
                                              WHERE m.paroisse_id = ? AND a.annee = ? AND a.statut = 'paye' ''',
                                           (p[0], annee_selectionnee)).fetchone()[0]
                
                st.write(f"**Statistiques :** {payes_paroisse}/{total_paroisse} membres à jour ({payes_paroisse/total_paroisse*100:.0f}%)" if total_paroisse > 0 else "Aucun membre")
                
                equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (p[0],)).fetchall()
                
                for eq in equipes:
                    st.markdown(f"**👥 {eq[1]}**")
                    
                    membres_ok = c.execute('''SELECT m.matricule, m.nom, m.prenom, a.montant
                                              FROM membres m
                                              JOIN abonnements a ON m.id = a.membre_id
                                              WHERE m.equipe_id = ? AND a.annee = ? AND a.statut = 'paye'
                                              ORDER BY m.nom''', (eq[0], annee_selectionnee)).fetchall()
                    
                    membres_retard = c.execute('''SELECT m.matricule, m.nom, m.prenom
                                                  FROM membres m
                                                  WHERE m.equipe_id = ? AND m.id NOT IN (
                                                      SELECT a.membre_id FROM abonnements a 
                                                      WHERE a.annee = ? AND a.statut = 'paye'
                                                  )
                                                  ORDER BY m.nom''', (eq[0], annee_selectionnee)).fetchall()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("*✅ À jour*")
                        for m in membres_ok:
                            st.write(f"  - {m[1]} {m[2]} ({m[0]}) - {m[3]} FCFA")
                        if not membres_ok:
                            st.write("  *Aucun*")
                    
                    with col2:
                        st.markdown("*❌ En retard*")
                        for m in membres_retard:
                            st.write(f"  - {m[1]} {m[2]} ({m[0]})")
                        if not membres_retard:
                            st.write("  *Aucun*")
                    st.markdown("---")
    
    elif menu == "📊 Export Excel":
        st.markdown('<h2 style="color:#1A237E;">📊 Export des données (Diocèse)</h2>', unsafe_allow_html=True)
        st.info("Exportez toutes les données dans un fichier Excel (4 onglets : Paroisses, Équipes, Membres, Abonnements)")
        nb_membres = c.execute("SELECT COUNT(*) FROM membres").fetchone()[0]
        if nb_membres == 0:
            st.warning("Aucune donnée à exporter pour le moment.")
        else:
            excel_file = exporter_excel_diocese()
            st.download_button(
                label="📥 Télécharger l'export Excel",
                data=excel_file,
                file_name=f"export_equipes_rosaire_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    elif menu == "🗑️ Réinitialiser tout":
        st.markdown('<h2 style="color:#1A237E;">🗑️ RÉINITIALISATION COMPLÈTE</h2>', unsafe_allow_html=True)
        st.error("⚠️ ACTION IRRÉVERSIBLE !")
        with st.expander("🔴 Cliquez ici pour réinitialiser"):
            st.warning("Cette action est irréversible.")
            confirmation = st.text_input("Tapez 'SUPPRIMER' pour confirmer")
            if confirmation == "SUPPRIMER":
                if os.path.exists("photos"):
                    shutil.rmtree("photos")
                    os.makedirs("photos")
                c.execute("DELETE FROM abonnements")
                c.execute("DELETE FROM membres")
                c.execute("DELETE FROM equipes")
                c.execute("DELETE FROM paroisses")
                c.execute("DELETE FROM utilisateurs WHERE role != 'diocese'")
                conn.commit()
                st.success("✅ Toutes les données ont été supprimées !")
                st.balloons()
                st.rerun()

# ==================== PAROISSE ====================
elif st.session_state['role'] == 'paroisse':
    
    pid = st.session_state['paroisse_id']
    nom_paroisse = c.execute("SELECT nom FROM paroisses WHERE id=?", (pid,)).fetchone()
    nom_paroisse = nom_paroisse[0] if nom_paroisse else "Ma paroisse"
    
    menu = st.sidebar.radio("Navigation", ["Ma paroisse", "Mes équipes", "Membres", "Statistiques", "Modifier paroisse", "Gérer les accès", "📊 Export Excel", "💰 Gestion des abonnements"])
    
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
        paroisse_info = c.execute("SELECT nom, commune FROM paroisses WHERE id=?", (pid,)).fetchone()
        if paroisse_info:
            nom_clean = paroisse_info[0].lower()
            mots_a_supprimer = ["saint ", "sainte ", "notre-dame ", "dame ", "st ", "ste ", "nd "]
            for mot in mots_a_supprimer:
                if nom_clean.startswith(mot):
                    nom_clean = nom_clean[len(mot):]
            nom_clean = nom_clean.strip()
            prefixe_paroisse = sans_accents(nom_clean[:3])
            prefixe_commune = sans_accents(paroisse_info[1][:3])
            prefixe = f"{prefixe_paroisse}{prefixe_commune}"
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
            st.info(f"💡 Format des identifiants : **{prefixe}eqX**")
        
        with st.expander("➕ Créer équipes"):
            with st.form("ajout_eq"):
                col1, col2 = st.columns(2)
                with col1:
                    nom_eq = st.text_input("Nom de l'équipe (ex: 3, Jeune, Enfant)")
                    responsable = st.text_input("Responsable")
                with col2:
                    bureau = st.text_area("Bureau")
                mdp_auto = generer_mot_de_passe()
                st.caption(f"🔑 Mot de passe généré : `{mdp_auto}`")
                if st.form_submit_button("Créer équipes"):
                    if nom_eq and responsable:
                        if equipe_existe(pid, nom_eq):
                            st.error("❌ Cette équipe existe déjà")
                        else:
                            nb_equipes_avant = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
                            identifiant = f"{prefixe}eq{nb_equipes_avant + 1}"
                            c.execute("INSERT INTO equipes (nom_equipe, responsable, bureau, paroisse_id) VALUES (?, ?, ?, ?)",
                                      (nom_eq, responsable, bureau, pid))
                            eid = c.lastrowid
                            c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id, equipe_id) VALUES (?, ?, ?, ?, ?)",
                                      (identifiant, hash_password(mdp_auto), "equipe", pid, eid))
                            conn.commit()
                            st.success(f"✅ Équipe '{nom_eq}' créée")
                            st.markdown(f"""
                            <div style="background-color:#e8f5e9; padding:15px; border-radius:10px; margin:10px 0;">
                                🔑 Identifiant : <code>{identifiant}</code><br>
                                🔒 Mot de passe : <code>{mdp_auto}</code>
                            </div>
                            """, unsafe_allow_html=True)
                            st.rerun()
        
        equipes = c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        if equipes:
            st.markdown("---")
            st.subheader("📋 Équipes existantes")
            for eq in equipes:
                user = c.execute("SELECT username FROM utilisateurs WHERE equipe_id=? AND role='equipe'", (eq[0],)).fetchone()
                identifiant = user[0] if user else "inconnu"
                st.write(f"- **{eq[1]}** - {eq[2]} (`{identifiant}`)")
    
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
                        with col2:
                            whatsapp = st.text_input("WhatsApp")
                            photo = st.file_uploader("Photo", type=['jpg', 'png', 'jpeg'])
                            date_adhesion = st.date_input("Date d'adhésion", value=date.today(), max_value=date.today())
                        if st.form_submit_button("Ajouter"):
                            if nom and prenom:
                                existant = membre_existe_deja(nom, prenom, naissance)
                                if existant:
                                    st.error(f"❌ Ce membre existe déjà avec le matricule {existant}")
                                else:
                                    matricule = generer_matricule_unique()
                                    c.execute("INSERT INTO membres (matricule, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id) VALUES (?,?,?,?,?,?,?,?)",
                                              (matricule, nom, prenom, naissance, whatsapp, date_adhesion, pid, eid))
                                    mid = c.lastrowid
                                    if photo:
                                        chemin = sauvegarder_photo(photo, matricule)
                                        c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                    conn.commit()
                                    st.success(f"✅ Membre ajouté ! Matricule: {matricule}")
                                    st.session_state['form_counter'] += 1
                                    st.rerun()
                            else:
                                st.error("Le nom et le prénom sont obligatoires")
            
            membres = c.execute("SELECT id, matricule, nom, prenom, whatsapp, photo_path, date_adhesion FROM membres WHERE equipe_id=? ORDER BY nom", (eid,)).fetchall()
            annee_courante = date.today().year
            for m in membres:
                statut = get_statut_abonnement(m[0], annee_courante)
                with st.expander(f"**{m[2]} {m[3]}** - {m[1]}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"💬 WhatsApp: {m[4]}")
                        st.write(f"📅 Adhésion: {m[6]}")
                        st.write(f"📅 Statut {annee_courante}: {statut}")
                        if m[5] and os.path.exists(m[5]):
                            st.image(m[5], width=80)
                    with col2:
                        if st.button("✏️ Modifier", key=f"mod_par_{m[0]}"):
                            st.session_state['modif_membre_id'] = m[0]
                            st.rerun()
                        if st.button("🗑️ Supprimer", key=f"del_par_{m[0]}"):
                            c.execute("DELETE FROM membres WHERE id=?", (m[0],))
                            conn.commit()
                            st.rerun()
            
            if 'modif_membre_id' in st.session_state:
                mid = st.session_state['modif_membre_id']
                membre = c.execute("SELECT matricule, nom, prenom, whatsapp, photo_path FROM membres WHERE id=?", (mid,)).fetchone()
                if membre:
                    st.markdown("---")
                    st.markdown(f"### ✏️ Modifier {membre[1]} {membre[2]}")
                    with st.form("modif_membre"):
                        new_nom = st.text_input("Nom", value=membre[1])
                        new_prenom = st.text_input("Prénom", value=membre[2])
                        new_whatsapp = st.text_input("WhatsApp", value=membre[3])
                        new_photo = st.file_uploader("📷 Nouvelle photo (laissez vide pour garder l'ancienne)", type=['jpg', 'png', 'jpeg'])
                        
                        if membre[4] and os.path.exists(membre[4]):
                            st.image(membre[4], width=100)
                            st.caption("Photo actuelle")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Enregistrer"):
                                c.execute("UPDATE membres SET nom=?, prenom=?, whatsapp=? WHERE id=?",
                                          (new_nom, new_prenom, new_whatsapp, mid))
                                
                                if new_photo:
                                    if membre[4] and os.path.exists(membre[4]):
                                        os.remove(membre[4])
                                    chemin_photo = sauvegarder_photo(new_photo, membre[0])
                                    c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin_photo, mid))
                                
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
                        st.error("❌ Une autre paroisse existe déjà")
                    else:
                        c.execute("UPDATE paroisses SET nom=?, commune=?, ville=?, responsable=?, bureau=? WHERE id=?",
                                  (nom, commune, ville, responsable, bureau, pid))
                        conn.commit()
                        st.success("Paroisse modifiée")
                        st.rerun()
    
    elif menu == "Gérer les accès":
        st.markdown(f'<h2 style="color:#1A237E;">🔐 Gestion des accès des équipes</h2>', unsafe_allow_html=True)
        equipes = c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
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
                            st.code(nouveau)
                    with col2:
                        if st.button(f"🗑️ Supprimer équipe", key=f"del_eq_{eq[0]}"):
                            c.execute("DELETE FROM membres WHERE equipe_id=?", (eq[0],))
                            c.execute("DELETE FROM equipes WHERE id=?", (eq[0],))
                            c.execute("DELETE FROM utilisateurs WHERE id=?", (user[0],))
                            conn.commit()
                            st.rerun()
    
    elif menu == "📊 Export Excel":
        st.markdown(f'<h2 style="color:#1A237E;">📊 Export des membres de {nom_paroisse}</h2>', unsafe_allow_html=True)
        st.info("Exportez la liste des membres de votre paroisse au format Excel")
        
        membres_paroisse = c.execute('''SELECT m.matricule, m.nom, m.prenom, m.date_naissance, m.whatsapp, 
                                               m.date_adhesion, e.nom_equipe as equipe
                                        FROM membres m
                                        JOIN equipes e ON m.equipe_id = e.id
                                        WHERE m.paroisse_id = ?
                                        ORDER BY e.nom_equipe, m.nom''', (pid,)).fetchall()
        
        if not membres_paroisse:
            st.warning("Aucun membre dans votre paroisse pour le moment.")
        else:
            df = pd.DataFrame(membres_paroisse, columns=["Matricule", "Nom", "Prénom", "Date naissance", "WhatsApp", "Date adhésion", "Équipe"])
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=f"Membres_{nom_paroisse}", index=False)
            
            output.seek(0)
            
            st.download_button(
                label="📥 Télécharger l'export Excel",
                data=output,
                file_name=f"membres_{nom_paroisse}_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.success(f"✅ {len(membres_paroisse)} membre(s) à exporter")
    
    elif menu == "💰 Gestion des abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 Gestion des abonnements - {nom_paroisse}</h2>', unsafe_allow_html=True)
        
        annee_courante = date.today().year
        annee_prochaine = annee_courante + 1
        
        col1, col2 = st.columns(2)
        with col1:
            annee_selectionnee = st.number_input("Année", min_value=2020, max_value=annee_prochaine, value=annee_courante, step=1)
        
        st.markdown("---")
        
        total_membres = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=?", (pid,)).fetchone()[0]
        membres_a_jour = c.execute('''SELECT COUNT(*) FROM abonnements a
                                      JOIN membres m ON a.membre_id = m.id
                                      WHERE m.paroisse_id = ? AND a.annee = ? AND a.statut = 'paye' ''',
                                   (pid, annee_selectionnee)).fetchone()[0]
        membres_en_retard = total_membres - membres_a_jour
        
        col1, col2, col3 = st.columns(3)
        col1.metric("👥 Total membres paroisse", total_membres)
        col2.metric("✅ À jour", membres_a_jour)
        col3.metric("❌ En retard", membres_en_retard)
        
        st.markdown("---")
        
        tab1, tab2, tab3 = st.tabs(["📋 Enregistrer un paiement", "✅ Membres à jour", "❌ Membres en retard"])
        
        with tab1:
            st.subheader("📋 Enregistrer un paiement")
            
            equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
            if equipes:
                equipe_dict = {eq[1]: eq[0] for eq in equipes}
                choix_equipe = st.selectbox("Choisir une équipe", list(equipe_dict.keys()))
                eid_selected = equipe_dict[choix_equipe]
                
                membres = c.execute("SELECT id, matricule, nom, prenom FROM membres WHERE equipe_id=? ORDER BY nom", (eid_selected,)).fetchall()
                
                for m in membres:
                    deja_paye = verifier_abonnement(m[0], annee_selectionnee)
                    statut_actuel = "✅ Déjà payé" if deja_paye else "❌ Non payé"
                    
                    with st.expander(f"{m[2]} {m[3]} ({m[1]}) - {statut_actuel}"):
                        if not deja_paye:
                            montant = st.number_input(f"Montant (FCFA)", min_value=0, value=1000, step=500, key=f"montant_par_{m[0]}_{annee_selectionnee}")
                            if st.button(f"💰 Enregistrer le paiement {annee_selectionnee}", key=f"btn_par_{m[0]}_{annee_selectionnee}"):
                                enregistrer_abonnement(m[0], annee_selectionnee, montant)
                                st.success(f"✅ Paiement enregistré pour {m[2]} {m[3]} !")
                                st.rerun()
                        else:
                            st.info(f"✅ Déjà payé pour {annee_selectionnee}")
            else:
                st.warning("Aucune équipe dans cette paroisse")
        
        with tab2:
            st.subheader(f"✅ Membres à jour - {annee_selectionnee}")
            
            equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
            for eq in equipes:
                membres_ok = c.execute('''SELECT m.matricule, m.nom, m.prenom, a.date_paiement, a.montant
                                          FROM membres m
                                          JOIN abonnements a ON m.id = a.membre_id
                                          WHERE m.equipe_id = ? AND a.annee = ? AND a.statut = 'paye'
                                          ORDER BY m.nom''', (eq[0], annee_selectionnee)).fetchall()
                
                if membres_ok:
                    st.markdown(f"**👥 {eq[1]}**")
                    for m in membres_ok:
                        st.write(f"  - {m[1]} {m[2]} ({m[0]}) - Payé le {m[3]} : {m[4]} FCFA")
            
            if not any(c.execute('''SELECT COUNT(*) FROM abonnements a
                                    JOIN membres m ON a.membre_id = m.id
                                    WHERE m.paroisse_id = ? AND a.annee = ? AND a.statut = 'paye' ''',
                                 (pid, annee_selectionnee)).fetchone()[0] for _ in [1]):
                st.info("Aucun membre à jour")
        
        with tab3:
            st.subheader(f"❌ Membres en retard - {annee_selectionnee}")
            
            equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
            for eq in equipes:
                membres_retard = c.execute('''SELECT m.matricule, m.nom, m.prenom
                                              FROM membres m
                                              WHERE m.equipe_id = ? AND m.id NOT IN (
                                                  SELECT a.membre_id FROM abonnements a 
                                                  WHERE a.annee = ? AND a.statut = 'paye'
                                              )
                                              ORDER BY m.nom''', (eq[0], annee_selectionnee)).fetchall()
                
                if membres_retard:
                    st.markdown(f"**👥 {eq[1]}**")
                    for m in membres_retard:
                        st.write(f"  - {m[1]} {m[2]} ({m[0]})")
            
            if not any(c.execute('''SELECT COUNT(*) FROM membres m
                                    WHERE m.paroisse_id = ? AND m.id NOT IN (
                                        SELECT a.membre_id FROM abonnements a 
                                        WHERE a.annee = ? AND a.statut = 'paye'
                                    )''', (pid, annee_selectionnee)).fetchone()[0] for _ in [1]):
                st.success("🎉 Tous les membres sont à jour !")

# ==================== ÉQUIPE ====================
elif st.session_state['role'] == 'equipe':
    
    eid = st.session_state['equipe_id']
    nom_equipe = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (eid,)).fetchone()
    nom_equipe = nom_equipe[0] if nom_equipe else "Mon équipe"
    
    menu = st.sidebar.radio("Navigation", ["Mon équipe", "Mes membres", "💰 Gestion des abonnements", "Modifier mon équipe"])
    
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
                    with col2:
                        whatsapp = st.text_input("WhatsApp")
                        photo = st.file_uploader("Photo", type=['jpg', 'png', 'jpeg'])
                        date_adhesion = st.date_input("Date d'adhésion", value=date.today(), max_value=date.today())
                    if st.form_submit_button("Ajouter"):
                        if nom and prenom:
                            existant = membre_existe_deja(nom, prenom, naissance)
                            if existant:
                                st.error(f"❌ Ce membre existe déjà avec le matricule {existant}")
                            else:
                                matricule = generer_matricule_unique()
                                pid = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()[0]
                                c.execute("INSERT INTO membres (matricule, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id) VALUES (?,?,?,?,?,?,?,?)",
                                          (matricule, nom, prenom, naissance, whatsapp, date_adhesion, pid, eid))
                                mid = c.lastrowid
                                if photo:
                                    chemin = sauvegarder_photo(photo, matricule)
                                    c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                conn.commit()
                                st.success(f"✅ Membre ajouté ! Matricule: {matricule}")
                                st.session_state['form_counter'] += 1
                                st.rerun()
                        else:
                            st.error("Le nom et le prénom sont obligatoires")
        
        membres = c.execute("SELECT id, matricule, nom, prenom, whatsapp, photo_path, date_adhesion FROM membres WHERE equipe_id=? ORDER BY nom", (eid,)).fetchall()
        annee_courante = date.today().year
        for m in membres:
            statut = get_statut_abonnement(m[0], annee_courante)
            with st.expander(f"**{m[2]} {m[3]}** - {m[1]}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"💬 WhatsApp: {m[4]}")
                    st.write(f"📅 Adhésion: {m[6]}")
                    st.write(f"📅 Statut {annee_courante}: {statut}")
                    if m[5] and os.path.exists(m[5]):
                        st.image(m[5], width=80)
                with col2:
                    if st.button("✏️ Modifier", key=f"mod_eq_{m[0]}"):
                        st.session_state['modif_membre_id'] = m[0]
                        st.rerun()
                    if st.button("🗑️ Supprimer", key=f"del_eq_{m[0]}"):
                        c.execute("DELETE FROM membres WHERE id=?", (m[0],))
                        conn.commit()
                        st.rerun()
        
        if 'modif_membre_id' in st.session_state:
            mid = st.session_state['modif_membre_id']
            membre = c.execute("SELECT matricule, nom, prenom, whatsapp, photo_path FROM membres WHERE id=?", (mid,)).fetchone()
            if membre:
                st.markdown("---")
                st.markdown(f"### ✏️ Modifier {membre[1]} {membre[2]}")
                with st.form("modif_membre_eq"):
                    new_nom = st.text_input("Nom", value=membre[1])
                    new_prenom = st.text_input("Prénom", value=membre[2])
                    new_whatsapp = st.text_input("WhatsApp", value=membre[3])
                    new_photo = st.file_uploader("📷 Nouvelle photo (laissez vide pour garder l'ancienne)", type=['jpg', 'png', 'jpeg'])
                    
                    if membre[4] and os.path.exists(membre[4]):
                        st.image(membre[4], width=100)
                        st.caption("Photo actuelle")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Enregistrer"):
                            c.execute("UPDATE membres SET nom=?, prenom=?, whatsapp=? WHERE id=?",
                                      (new_nom, new_prenom, new_whatsapp, mid))
                            
                            if new_photo:
                                if membre[4] and os.path.exists(membre[4]):
                                    os.remove(membre[4])
                                chemin_photo = sauvegarder_photo(new_photo, membre[0])
                                c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin_photo, mid))
                            
                            conn.commit()
                            del st.session_state['modif_membre_id']
                            st.success("Membre modifié")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("❌ Annuler"):
                            del st.session_state['modif_membre_id']
                            st.rerun()
    
    elif menu == "💰 Gestion des abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 Gestion des abonnements - {nom_equipe}</h2>', unsafe_allow_html=True)
        
        annee_courante = date.today().year
        annee_prochaine = annee_courante + 1
        
        col1, col2 = st.columns(2)
        with col1:
            annee_selectionnee = st.number_input("Année", min_value=2020, max_value=annee_prochaine, value=annee_courante, step=1)
        
        st.markdown("---")
        
        membres_equipe = c.execute("SELECT id, matricule, nom, prenom FROM membres WHERE equipe_id=?", (eid,)).fetchall()
        total_membres = len(membres_equipe)
        membres_a_jour = c.execute('''SELECT COUNT(*) FROM abonnements a
                                      JOIN membres m ON a.membre_id = m.id
                                      WHERE m.equipe_id = ? AND a.annee = ? AND a.statut = 'paye' ''',
                                   (eid, annee_selectionnee)).fetchone()[0]
        membres_en_retard = total_membres - membres_a_jour
        
        col1, col2, col3 = st.columns(3)
        col1.metric("👥 Total membres équipe", total_membres)
        col2.metric("✅ À jour", membres_a_jour)
        col3.metric("❌ En retard", membres_en_retard)
        
        st.markdown("---")
        
        tab1, tab2, tab3 = st.tabs(["📋 Enregistrer un paiement", "✅ Membres à jour", "❌ Membres en retard"])
        
        with tab1:
            st.subheader("📋 Enregistrer un paiement")
            
            membres = c.execute("SELECT id, matricule, nom, prenom FROM membres WHERE equipe_id=? ORDER BY nom", (eid,)).fetchall()
            
            for m in membres:
                deja_paye = verifier_abonnement(m[0], annee_selectionnee)
                statut_actuel = "✅ Déjà payé" if deja_paye else "❌ Non payé"
                
                with st.expander(f"{m[2]} {m[3]} ({m[1]}) - {statut_actuel}"):
                    if not deja_paye:
                        montant = st.number_input(f"Montant (FCFA)", min_value=0, value=1000, step=500, key=f"montant_eq_{m[0]}_{annee_selectionnee}")
                        if st.button(f"💰 Enregistrer le paiement {annee_selectionnee}", key=f"btn_eq_{m[0]}_{annee_selectionnee}"):
                            enregistrer_abonnement(m[0], annee_selectionnee, montant)
                            st.success(f"✅ Paiement enregistré pour {m[2]} {m[3]} !")
                            st.rerun()
                    else:
                        st.info(f"✅ Déjà payé pour {annee_selectionnee}")
        
        with tab2:
            st.subheader(f"✅ Membres à jour - {annee_selectionnee}")
            membres_ok = c.execute('''SELECT m.matricule, m.nom, m.prenom, a.date_paiement, a.montant
                                      FROM membres m
                                      JOIN abonnements a ON m.id = a.membre_id
                                      WHERE m.equipe_id = ? AND a.annee = ? AND a.statut = 'paye'
                                      ORDER BY m.nom''', (eid, annee_selectionnee)).fetchall()
            
            if membres_ok:
                for m in membres_ok:
                    st.write(f"- **{m[1]} {m[2]}** ({m[0]}) - Payé le {m[3]} : {m[4]} FCFA")
            else:
                st.info("Aucun membre à jour")
        
        with tab3:
            st.subheader(f"❌ Membres en retard - {annee_selectionnee}")
            membres_retard = c.execute('''SELECT m.matricule, m.nom, m.prenom
                                          FROM membres m
                                          WHERE m.equipe_id = ? AND m.id NOT IN (
                                              SELECT a.membre_id FROM abonnements a 
                                              WHERE a.annee = ? AND a.statut = 'paye'
                                          )
                                          ORDER BY m.nom''', (eid, annee_selectionnee)).fetchall()
            
            if membres_retard:
                st.warning(f"⚠️ {len(membres_retard)} membre(s) en retard")
                for m in membres_retard:
                    st.write(f"- **{m[1]} {m[2]}** ({m[0]})")
            else:
                st.success("🎉 Tous les membres sont à jour !")
    
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
