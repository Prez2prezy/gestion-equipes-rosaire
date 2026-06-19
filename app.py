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
import csv
from io import StringIO
import urllib.parse
import cloudinary
import cloudinary.uploader

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



# --- Connexion à la base de données (Locale ou Turso Cloud) ---
import sqlite3

# Variable globale pour vérifier si on utilise le cloud
USE_TURSO = False

try:
    from libsql_experimental import connect as turso_connect
    TURSO_URL = st.secrets.get("TURSO_URL")
    TURSO_AUTH_TOKEN = st.secrets.get("TURSO_AUTH_TOKEN")
    if TURSO_URL and TURSO_AUTH_TOKEN:
        USE_TURSO = True
except Exception:
    pass  # Si la librairie n'est pas installée, on reste en local

if USE_TURSO:
    # Connexion Cloud (Turso) en mode 100% distant (plus de fichier local)
    # On remplace libsql:// par https:// pour une connexion HTTP directe plus stable
    url_https = TURSO_URL.replace("libsql://", "https://")
    conn = turso_connect(url_https, auth_token=TURSO_AUTH_TOKEN)
    c = conn.cursor()
else:
    # Connexion Locale classique (pour votre PC)
    conn = sqlite3.connect('gestion_religieuse.db', check_same_thread=False)
    c = conn.cursor()

# Fonction pour sauvegarder
def commit_and_sync():
    conn.commit()
    # En mode distant, commit() envoie directement les données sur le cloud. Pas besoin de sync().


# --- Configuration de Cloudinary (Stockage Photos Cloud) ---

USE_CLOUDINARY = False
try:
    cloudinary.config(
        cloud_name=st.secrets.get("CLOUDINARY_CLOUD_NAME"),
        api_key=st.secrets.get("CLOUDINARY_API_KEY"),
        api_secret=st.secrets.get("CLOUDINARY_API_SECRET"),
        secure=True
    )
    if st.secrets.get("CLOUDINARY_CLOUD_NAME"):
        USE_CLOUDINARY = True
except Exception:
    pass # Reste en mode local si Cloudinary n'est pas configuré

# Fonction pour sauvegarder (pas besoin de sync() en mode HTTP, commit suffit)
def commit_and_sync():
    conn.commit()

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
        if USE_CLOUDINARY:
            # Envoi vers le cloud Cloudinary
            resultat = cloudinary.uploader.upload(
                photo_fichier, 
                public_id=f"rosaire_membres/{matricule}", # Nom du fichier en ligne
                overwrite=True, # Écrase si on met à jour la photo
                transformation=[{"width": 300, "height": 300, "crop": "fill"}] # Redimensionne auto
            )
            return resultat['secure_url'] # Retourne le lien HTTPS de la photo
        else:
            # Mode local de secours (pour votre PC)
            if not os.path.exists("photos"):
                os.makedirs("photos")
            chemin = f"photos/{matricule}.jpg"
            img = Image.open(photo_fichier)
            img = img.resize((300, 300))
            img.save(chemin, "JPEG", quality=60)
            return chemin
    return None

def supprimer_photo(photo_path):
    if not photo_path:
        return
    if USE_CLOUDINARY and photo_path.startswith("http"):
        # Extraction de l'ID Cloudinary depuis l'URL pour la supprimer
        try:
            parts = photo_path.split('/upload/')[-1]
            if parts.startswith('v'):
                parts = '/'.join(parts.split('/')[1:])
            public_id = os.path.splitext(parts)[0]
            cloudinary.uploader.destroy(public_id)
        except Exception:
            pass
    elif not photo_path.startswith("http") and os.path.exists(photo_path):
        # Mode local de secours
        os.remove(photo_path)


def ajouter_evenement_agenda(equipe_id=None, paroisse_id=None, diocese_id=None, auteur_nom="Système"):
    """Formulaire d'ajout d'un événement."""
    st.subheader("📅 Vos événements à venir")
    
    prefix = f"ag_{equipe_id}_{paroisse_id}_{diocese_id}"
    
    with st.expander("➕ Ajouter / Enregistrer un événement à l'agenda"):
        with st.form(f"ajout_agenda_{prefix}"):
            col1, col2 = st.columns(2)
            with col1:
                date_agenda = st.date_input("📅 Date de l'événement", value=date.today() + timedelta(days=7), min_value=date.today(), key=f"date_ag_{prefix}")
            with col2:
                type_agenda = st.selectbox("⛪ Type", ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage", "Réunion", "Autre"], key=f"type_ag_{prefix}")
            lieu_agenda = st.text_input("📍 Lieu", key=f"lieu_ag_{prefix}")
            desc_agenda = st.text_area("📝 Description / Notes (optionnel)", key=f"desc_ag_{prefix}")
            
            if st.form_submit_button("📅 Enregistrer dans l'agenda", use_container_width=True):
                c.execute('''INSERT INTO agenda (equipe_id, paroisse_id, diocese_id, date_event, type_event, lieu, description, auteur_nom) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          (equipe_id, paroisse_id, diocese_id, date_agenda, type_agenda, lieu_agenda, desc_agenda, auteur_nom))
                commit_and_sync()
                st.success("Événement enregistré avec succès ! ✅")
                st.rerun()


def afficher_agenda_complet_universel(equipe_id=None, paroisse_id=None, diocese_id=None):
    """Affiche l'agenda global en fonction du niveau hiérarchique de l'utilisateur."""
    st.subheader("📋 Planification des agendas (Vue d'ensemble)")
    
    aujourd_hui = date.today()
    query = '''SELECT id, date_event, type_event, lieu, description, auteur_nom,
                      equipe_id, paroisse_id, diocese_id
               FROM agenda 
               WHERE date_event >= ? '''
    params = [aujourd_hui]
    
    # Construction des conditions pour voir les enfants et les parents
    conditions = []
    if equipe_id:
        # 1. Les événements de l'équipe elle-même
        conditions.append("equipe_id = ?")
        params.append(equipe_id)
        # 2. Les événements de sa paroisse parente
        pid = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (equipe_id,)).fetchone()
        if pid and pid[0]:
            conditions.append("(paroisse_id = ? AND equipe_id IS NULL)")
            params.append(pid[0])
        # 3. Les événements du diocèse
        conditions.append("(diocese_id = 1 AND paroisse_id IS NULL AND equipe_id IS NULL)")
        
    elif paroisse_id:
        # 1. Les événements de la paroisse elle-même
        conditions.append("(paroisse_id = ? AND equipe_id IS NULL)")
        params.append(paroisse_id)
        # 2. Les événements de ses équipes enfants
        conditions.append("equipe_id IN (SELECT id FROM equipes WHERE paroisse_id = ?)")
        params.append(paroisse_id)
        # 3. Les événements du diocèse
        conditions.append("(diocese_id = 1 AND paroisse_id IS NULL AND equipe_id IS NULL)")

    elif diocese_id:
        # 1. Les événements créés par le diocèse lui-même
        conditions.append("(diocese_id = ? AND paroisse_id IS NULL AND equipe_id IS NULL)")
        params.append(diocese_id)
        # 2. Les événements créés par les paroisses du diocèse
        conditions.append("paroisse_id IN (SELECT id FROM paroisses WHERE diocese_id = ?)")
        params.append(diocese_id)
        # 3. Les événements créés par les équipes du diocèse
        conditions.append("equipe_id IN (SELECT id FROM equipes WHERE paroisse_id IN (SELECT id FROM paroisses WHERE diocese_id = ?))")
        params.append(diocese_id)

    if conditions:
        query += " AND (" + " OR ".join(conditions) + ")"
        
    query += " ORDER BY date_event ASC"
    
    try:
        agenda_items = c.execute(query, params).fetchall()
    except Exception as e:
        st.error(f"Erreur de base de données : {e}")
        st.info("Essayez de redémarrer l'application ou vérifiez la table 'agenda'.")
        return
    
    if agenda_items:
        for item in agenda_items:
            item_id, item_date_raw, item_type, item_lieu, item_desc, item_auteur, item_eid, item_pid, item_did = item
            item_date = safe_date(item_date_raw)
            if not item_date: continue
            
            # ✅ Déterminer la source en Python (beaucoup plus sûr que les sous-requêtes SQL)
            source = ""
            if item_eid:
                eq_info = c.execute("SELECT e.nom_equipe, p.nom FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id WHERE e.id=?", (item_eid,)).fetchone()
                if eq_info:
                    source = f"👥 {eq_info[0]} ({eq_info[1]})"
            elif item_pid:
                par_info = c.execute("SELECT nom FROM paroisses WHERE id=?", (item_pid,)).fetchone()
                if par_info:
                    source = f"🏘️ Paroisse {par_info[0]}"
            elif item_did:
                source = f"🏛️ Diocèse"
            
            # Calcul du délai
            delta = (item_date - aujourd_hui).days
            if delta == 0: delai_str = "🔴 **Aujourd'hui !**"
            elif delta == 1: delai_str = "🟠 **Demain**"
            elif delta <= 7: delai_str = f"🟡 Dans **{delta} jours**"
            else: delai_str = f"🟢 Dans **{delta} jours**"
            
            icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝", "Autre": "📅"}.get(item_type, "📅")
            header = f"{icone} {item_date.strftime('%d/%m/%Y')} - {item_type} - {source} ({delai_str})"
            
            with st.expander(header):
                if source: st.write(f"🏢 **Source :** {source}")
                if item_auteur: st.write(f"👤 **Ajouté par :** {item_auteur}")
                if item_lieu: st.write(f"📍 **Lieu :** {item_lieu}")
                if item_desc: st.write(f"📝 **Détails :** {item_desc}")
                
                # Bouton supprimer (uniquement si l'événement appartient à l'entité connectée)
                can_delete = False
                if equipe_id and item_eid == equipe_id: can_delete = True
                if paroisse_id and item_pid == paroisse_id and not item_eid: can_delete = True
                if diocese_id and item_did == diocese_id and not item_pid and not item_eid: can_delete = True
                
                if can_delete:
                    # Ajout d'un suffixe unique pour éviter les erreurs de clés dupliquées
                    btn_key_suffix = f"eq{equipe_id}_par{paroisse_id}_dio{diocese_id}"
                    if st.button("🗑️ Supprimer de l'agenda", key=f"del_agenda_{item_id}_{btn_key_suffix}"):
                        c.execute("DELETE FROM agenda WHERE id=?", (item_id,))
                        commit_and_sync()
                        st.rerun()
    else:
        st.info("Aucun événement à venir pour le moment.")

def afficher_agenda(equipe_id):
    """Affiche l'agenda à venir d'une équipe (lecture seule)."""
    aujourd_hui = date.today()
    agenda_items = c.execute('''SELECT date_event, type_event, lieu, description 
                                FROM agenda 
                                WHERE equipe_id=? AND date_event >= ? 
                                ORDER BY date_event ASC''', (equipe_id, aujourd_hui)).fetchall()
    
    if agenda_items:
        for item in agenda_items:
            item_date_raw, item_type, item_lieu, item_desc = item
            item_date = safe_date(item_date_raw)
            if not item_date: continue
            
            delta = (item_date - aujourd_hui).days
            if delta == 0: delai_str = "🔴 **Aujourd'hui !**"
            elif delta == 1: delai_str = "🟠 **Demain**"
            elif delta <= 7: delai_str = f"🟡 Dans **{delta} jours**"
            else: delai_str = f"🟢 Dans **{delta} jours**"
            
            icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝", "Autre": "📅"}.get(item_type, "📅")
            header = f"{icone} {item_date.strftime('%d/%m/%Y')} - {item_type} ({delai_str})"
            
            with st.expander(header):
                if item_lieu: st.write(f"📍 **Lieu :** {item_lieu}")
                if item_desc: st.write(f"📝 **Détails :** {item_desc}")
    else:
        st.info("Aucun événement à venir pour cette équipe.")

# ✅ Widget centralisé pour le choix abonnement/réabonnement
def widget_type_abonnement(key_prefix, membre_id, annee_debut):
    """Widget pour choisir le type d'abonnement. Retourne (type, montant)."""
    type_abo = st.radio("Type", ["📝 Abonnement", "🔄 Réabonnement"],
                        key=f"type_{key_prefix}_{membre_id}_{annee_debut}", horizontal=True)
    montant = st.number_input("Montant (FCFA)", min_value=0, value=1000, step=500,
                              key=f"mont_{key_prefix}_{membre_id}_{annee_debut}")
    type_str = "abonnement" if "Abonnement" in type_abo else "reabonnement"
    return type_str, montant

def safe_date(value):
    """Convertit une valeur en objet date de façon robuste."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    return None
    
def afficher_historique_suivi(equipe_id, filtre_type="Tous", limit=20):
    """Affiche l'historique de présence d'une équipe (lecture seule)."""
    types_evenements = ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage"]
    
    requete = '''
        SELECT e.id, e.date_evenement, e.type_evenement, e.lieu,
               SUM(CASE WHEN sp.statut='present' THEN 1 ELSE 0 END) as nb_presents,
               SUM(CASE WHEN sp.statut='excuse' THEN 1 ELSE 0 END) as nb_excuses,
               SUM(CASE WHEN sp.statut='absent' THEN 1 ELSE 0 END) as nb_absents
        FROM evenements e
        LEFT JOIN suivi_presences sp ON e.id = sp.evenement_id
        WHERE e.equipe_id = ?
        {filtre}
        GROUP BY e.id
        ORDER BY e.date_evenement DESC
        LIMIT ?
    '''
    params = [equipe_id]
    if filtre_type != "Tous":
        requete = requete.format(filtre="AND e.type_evenement = ?")
        params.append(filtre_type)
    else:
        requete = requete.format(filtre="")
    params.append(limit)
    
    evenements = c.execute(requete, params).fetchall()
    
    if evenements:
        for ev in evenements:
            ev_id, date_raw, type_ev, lieu, nb_p, nb_e, nb_a = ev
            
            # Sécurité contre les valeurs NULL
            nb_p = nb_p or 0
            nb_e = nb_e or 0
            nb_a = nb_a or 0
            
            date_ev = safe_date(date_raw)
            if not date_ev:
                continue
            
            date_str = date_ev.strftime('%d/%m/%Y')
            icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️"}.get(type_ev, "📅")
            
            total_reponses = nb_p + nb_e + nb_a
            taux = (nb_p / total_reponses * 100) if total_reponses > 0 else 0
            
            if taux >= 75: couleur = "green"
            elif taux >= 50: couleur = "orange"
            else: couleur = "red"
            
            lieu_str = f" à **{lieu}**" if lieu else ""
            header = f"{icone} {date_str} - {type_ev}{lieu_str} | ✅ {nb_p} ⚠️ {nb_e} ❌ {nb_a}"
            
            with st.expander(header):
                st.markdown(f"**Taux de présence :** :{couleur}[{taux:.0f}%]")
                if lieu:
                    st.write(f"📍 **Lieu :** {lieu}")
                
                presents = c.execute('''SELECT m.nom, m.prenom FROM membres m JOIN suivi_presences sp ON m.id=sp.membre_id 
                                        WHERE sp.evenement_id=? AND sp.statut='present' ORDER BY m.nom''', (ev_id,)).fetchall()
                excuses = c.execute('''SELECT m.nom, m.prenom FROM membres m JOIN suivi_presences sp ON m.id=sp.membre_id 
                                       WHERE sp.evenement_id=? AND sp.statut='excuse' ORDER BY m.nom''', (ev_id,)).fetchall()
                absents = c.execute('''SELECT m.nom, m.prenom FROM membres m JOIN suivi_presences sp ON m.id=sp.membre_id 
                                       WHERE sp.evenement_id=? AND sp.statut='absent' ORDER BY m.nom''', (ev_id,)).fetchall()
                
                if presents:
                    st.write("✅ **Présents :** " + ", ".join([f"{p[0]} {p[1]}" for p in presents]))
                if excuses:
                    st.write("⚠️ **Excusés :** " + ", ".join([f"{e[0]} {e[1]}" for e in excuses]))
                if absents:
                    st.write("❌ **Absents :** " + ", ".join([f"{a[0]} {a[1]}" for a in absents]))
    else:
        st.info("Aucun historique de présence pour le moment.")

# ✅ Fonction centralisée pour archiver un membre
def archiver_membre(membre_id, situation, annee_debut, annee_fin, commentaire, auteur_id, auteur_nom, auteur_role):
    """Archive un membre : change son statut et crée une entrée dans les archives."""
    membre = c.execute("SELECT equipe_id FROM membres WHERE id=?", (membre_id,)).fetchone()
    if not membre:
        return False
    equipe_id = membre[0]
    paroisse_id = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (equipe_id,)).fetchone()
    paroisse_id = paroisse_id[0] if paroisse_id else None

    date_debut_obj = date(annee_debut, 10, 1)
    date_fin_obj = date(annee_fin, 10, 1)

    c.execute("UPDATE membres SET statut='archive' WHERE id=?", (membre_id,))
    c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire,
                 auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (membre_id, situation, date_debut_obj, date_fin_obj, commentaire,
               auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id))
    commit_and_sync()  # On utilise la fonction de sauvegarde unifiée
    return True

# ✅ Fonction pour réintégrer un membre archivé
def reintegrer_membre(archive_id, membre_id):
    """Réintègre un membre : remet le statut actif et supprime l'archive."""
    c.execute("UPDATE membres SET statut='actif' WHERE id=?", (membre_id,))
    c.execute("DELETE FROM archives WHERE id=?", (archive_id,))
    commit_and_sync()  # On utilise la fonction de sauvegarde unifiée

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
    commit_and_sync()

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

# --- Export Excel ---
def exporter_excel_diocese():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
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

# --- Création des tables ---
c.execute('''CREATE TABLE IF NOT EXISTS diocese (id INTEGER PRIMARY KEY, nom TEXT, responsable TEXT, bureau TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS paroisses (id INTEGER PRIMARY KEY, nom TEXT, commune TEXT, ville TEXT, responsable TEXT, bureau TEXT, diocese_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS equipes (id INTEGER PRIMARY KEY, nom_equipe TEXT, responsable TEXT, bureau TEXT, paroisse_id INTEGER, max_membres INTEGER DEFAULT 10)''')
c.execute('''CREATE TABLE IF NOT EXISTS membres (id INTEGER PRIMARY KEY, matricule TEXT UNIQUE, nom TEXT, prenom TEXT, date_naissance DATE, whatsapp TEXT, date_adhesion DATE, photo_path TEXT, paroisse_id INTEGER, equipe_id INTEGER, statut TEXT DEFAULT 'actif')''')
c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, diocese_id INTEGER, paroisse_id INTEGER, equipe_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS abonnements (id INTEGER PRIMARY KEY, membre_id INTEGER, annee_debut INTEGER, date_paiement DATE, montant REAL DEFAULT 0, type_abonnement TEXT DEFAULT 'abonnement', statut TEXT DEFAULT 'non_paye')''')
c.execute('''CREATE TABLE IF NOT EXISTS archives (id INTEGER PRIMARY KEY, membre_id INTEGER, situation TEXT, date_debut DATE, date_fin DATE, commentaire TEXT, auteur_id INTEGER, auteur_nom TEXT, auteur_role TEXT, paroisse_id INTEGER, equipe_id INTEGER)''')
# On supprime l'ancienne table si elle existait pour la nouvelle structure

c.execute('''CREATE TABLE IF NOT EXISTS evenements (id INTEGER PRIMARY KEY, equipe_id INTEGER, type_evenement TEXT, date_evenement DATE, lieu TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS suivi_presences (id INTEGER PRIMARY KEY, membre_id INTEGER, evenement_id INTEGER, statut TEXT DEFAULT 'absent')''')
c.execute('''CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY, equipe_id INTEGER, paroisse_id INTEGER, diocese_id INTEGER, date_event DATE, type_event TEXT, lieu TEXT, description TEXT, auteur_nom TEXT)''')
commit_and_sync()

# Migrations (ajout de colonnes si absentes)
try: 
    c.execute("ALTER TABLE membres ADD COLUMN statut TEXT DEFAULT 'actif'")
    commit_and_sync()
except: 
    pass

try: 
    c.execute("ALTER TABLE membres ADD COLUMN numero_meditation TEXT")
    commit_and_sync()
except: 
    pass

try: 
    c.execute("ALTER TABLE abonnements ADD COLUMN annee_debut INTEGER")
    commit_and_sync()
except: 
    pass

try: 
    c.execute("ALTER TABLE archives ADD COLUMN situation TEXT")
    commit_and_sync()
except: 
    pass

try: 
    c.execute("ALTER TABLE archives ADD COLUMN date_debut DATE")
    commit_and_sync()
except: 
    pass

try: 
    c.execute("ALTER TABLE archives ADD COLUMN date_fin DATE")
    commit_and_sync()
except: 
    pass


# --- Migration pour le Suivi des présences ---
# On vérifie si l'ancienne table suivi_presences existe avec l'ancien schéma
try:
    cols = c.execute("PRAGMA table_info(suivi_presences)").fetchall()
    col_names = [col[1] for col in cols]
    # Si la table existe mais n'a pas la colonne 'evenement_id', c'est l'ancienne version
    if col_names and 'evenement_id' not in col_names:
        c.execute("DROP TABLE IF EXISTS suivi_presences")
        c.execute("DROP TABLE IF EXISTS evenements")
        commit_and_sync()
except:
    pass

# --- Initialisation ---
c.execute("SELECT COUNT(*) FROM diocese")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO diocese (nom, responsable, bureau) VALUES (?, ?, ?)", ("GRAND-BASSAM", "À définir", "À définir"))
    commit_and_sync()

c.execute("SELECT COUNT(*) FROM utilisateurs WHERE role='diocese'")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?, ?, ?, ?)", ("diocese", hash_password("admin123"), "diocese", 1))
    commit_and_sync()

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
st.markdown('<h1 style="color:#1A237E;">📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE</h1>', unsafe_allow_html=True)
st.markdown("---")

# ==================== DIOCÈSE ====================
if st.session_state['role'] == 'diocese':
    # Après (supprimer "📊 Export Excel")
    menu = st.sidebar.radio("Navigation", ["Voir diocèse", "Créer paroisses", "Gérer paroisses", "Rechercher par matricule", "Gérer les accès", "Statistiques", "📅 Abonnements", "📌 Suivi", "💬 WhatsApp", "📦 Archives", "🗑️ Réinitialiser tout"])


    if USE_TURSO:
        st.sidebar.success("☁️ Connecté au Cloud (Turso)")
    else:
        st.sidebar.error("💾 Mode Local (Les données seront perdues)")



    
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
                    commit_and_sync()
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
                        commit_and_sync()
                        st.success(f"✅ Paroisse '{nom}' créée")
                        st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px'>🔑 Identifiant : <code>{username}</code><br>🔒 Mot de passe : <code>{mdp}</code></div>", unsafe_allow_html=True)
                else:
                    st.error("Tous les champs sont requis")
    
    # Gérer paroisses
    elif menu == "Gérer paroisses":
        st.markdown('<h2 style="color:#1A237E;">📋 Consultation des paroisses</h2>', unsafe_allow_html=True)
        
        # Initialisation des états de session pour les dialogues
        if 'show_equipes' not in st.session_state:
            st.session_state['show_equipes'] = None
        if 'show_equipiers' not in st.session_state:
            st.session_state['show_equipiers'] = None
        if 'show_membres_equipe' not in st.session_state:
            st.session_state['show_membres_equipe'] = None
        
        paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau FROM paroisses ORDER BY nom").fetchall()
        
        for p in paroisses:
            pid, nom, commune, ville, responsable, bureau = p
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
            nb_membres = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0]
            
            with st.expander(f"🏛️ {nom} ({commune} / {ville}) - {nb_equipes} équipe(s) - {nb_membres} membre(s)"):
                st.write(f"**Responsable :** {responsable}")
                st.write(f"**Bureau :** {bureau}")
                
                # Boutons Équipes et Équipiers
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👥 Voir les équipes", key=f"btn_equipes_{pid}"):
                        if st.session_state['show_equipes'] == pid:
                            st.session_state['show_equipes'] = None
                        else:
                            st.session_state['show_equipes'] = pid
                            st.session_state['show_equipiers'] = None
                            st.session_state['show_membres_equipe'] = None
                        st.rerun()
                with col2:
                    if st.button(f"👤 Voir tous les équipiers", key=f"btn_equipiers_{pid}"):
                        if st.session_state['show_equipiers'] == pid:
                            st.session_state['show_equipiers'] = None
                        else:
                            st.session_state['show_equipiers'] = pid
                            st.session_state['show_equipes'] = None
                            st.session_state['show_membres_equipe'] = None
                        st.rerun()
                
                # --- Affichage des équipes ---
                if st.session_state.get('show_equipes') == pid:
                    st.markdown("---")
                    st.markdown(f"#### 👥 Équipes de {nom}")
                    equipes = c.execute("SELECT id, nom_equipe, responsable, bureau FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
                    
                    if not equipes:
                        st.info("Aucune équipe dans cette paroisse")
                    else:
                        for eq in equipes:
                            eq_id, eq_nom, eq_resp, eq_bureau = eq
                            nb_membres_eq = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eq_id,)).fetchone()[0]
                            
                            with st.expander(f"📌 {eq_nom} - Respo: {eq_resp} ({nb_membres_eq} membres)"):
                                st.write(f"**Bureau :** {eq_bureau}")
                                
                                # Bouton pour voir les membres de l'équipe
                                if st.button(f"📋 Voir les membres de {eq_nom}", key=f"btn_membres_eq_{eq_id}"):
                                    if st.session_state['show_membres_equipe'] == eq_id:
                                        st.session_state['show_membres_equipe'] = None
                                    else:
                                        st.session_state['show_membres_equipe'] = eq_id
                                    st.rerun()
                                
                                # Affichage des membres de l'équipe
                                if st.session_state.get('show_membres_equipe') == eq_id:
                                    membres_eq = c.execute("""
                                        SELECT matricule, nom, prenom, whatsapp, numero_meditation, date_adhesion, photo_path
                                        FROM membres 
                                        WHERE equipe_id=? AND statut='actif' 
                                        ORDER BY nom
                                    """, (eq_id,)).fetchall()
                                    
                                    if not membres_eq:
                                        st.info("Aucun membre dans cette équipe")
                                    else:
                                        # Tableau des membres
                                        data = []
                                        for m in membres_eq:
                                            data.append({
                                                "Matricule": m[0],
                                                "Nom": m[1],
                                                "Prénom": m[2],
                                                "WhatsApp": m[3],
                                                "N° méditation": m[4] or "-",
                                                "Date d'adhésion": m[5]
                                            })
                                        df = pd.DataFrame(data)
                                        df.index = df.index + 1  # ✅ AJOUTEZ CETTE LIGNE
                                        st.dataframe(df, use_container_width=True)
                                        
                                        # Export Excel des membres de l'équipe
                                        output = io.BytesIO()
                                        try:
                                            with pd.ExcelWriter(output, engine=None) as writer:
                                                df.to_excel(writer, sheet_name=f"Membres_{eq_nom}", index=False)
                                            output.seek(0)
                                            st.download_button(
                                                f"📥 Exporter les membres de {eq_nom}",
                                                data=output,
                                                file_name=f"membres_{eq_nom}_{date.today()}.xlsx",
                                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                key=f"export_membres_eq_{eq_id}_{date.today()}"
                                            )
                                        except Exception as e:
                                            st.error(f"Erreur export: {e}")
                
                # --- Affichage de tous les équipiers de la paroisse ---
                if st.session_state.get('show_equipiers') == pid:
                    st.markdown("---")
                    st.markdown(f"#### 👤 Tous les équipiers de {nom}")
                    
                    # Récupérer tous les membres actifs de la paroisse avec leur équipe
                    membres_paroisse = c.execute("""
                        SELECT m.matricule, m.nom, m.prenom, m.whatsapp, m.numero_meditation, m.date_adhesion, 
                            e.nom_equipe, m.photo_path
                        FROM membres m
                        JOIN equipes e ON m.equipe_id = e.id
                        WHERE m.paroisse_id=? AND m.statut='actif'
                        ORDER BY e.nom_equipe, m.nom
                    """, (pid,)).fetchall()
                    
                    if not membres_paroisse:
                        st.info("Aucun membre actif dans cette paroisse")
                    else:
                        # Statistiques
                        total_membres = len(membres_paroisse)
                        st.info(f"📊 Total : {total_membres} membre(s) actif(s)")
                        
                        # Tableau des membres
                        data = []
                        for m in membres_paroisse:
                            data.append({
                                "Matricule": m[0],
                                "Nom": m[1],
                                "Prénom": m[2],
                                "WhatsApp": m[3],
                                "N° méditation": m[4] or "-",
                                "Date d'adhésion": m[5],
                                "Équipe": m[6]
                            })
                        df = pd.DataFrame(data)
                        df.index = df.index + 1  # ✅ AJOUTEZ CETTE LIGNE
                        st.dataframe(df, use_container_width=True)
                        
                        # Export Excel de tous les membres
                        output = io.BytesIO()
                        try:
                            with pd.ExcelWriter(output, engine=None) as writer:
                                df.to_excel(writer, sheet_name=f"Equipiers_{nom}", index=False)
                            output.seek(0)
                            st.download_button(
                                f"📥 Exporter tous les équipiers de {nom}",
                                data=output,
                                file_name=f"equipiers_{nom}_{date.today()}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"export_equipiers_{pid}_{date.today()}"
                            )
                        except Exception as e:
                            st.error(f"Erreur export: {e}")    

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

                if m[6]:
                    try:
                        col2.image(m[6], width=100)
                    except:
                        pass

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
                        commit_and_sync()
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
    
    # Abonnements (Diocèse) avec hiérarchisation
    elif menu == "📅 Abonnements":
        st.markdown('<h2 style="color:#1A237E;">📅 Suivi des abonnements (Diocèse)</h2>', unsafe_allow_html=True)
        
        # Initialisation des états de session
        if 'show_paroisse_abos' not in st.session_state:
            st.session_state['show_paroisse_abos'] = None
        if 'show_equipe_abos' not in st.session_state:
            st.session_state['show_equipe_abos'] = None
        if 'abos_view_type' not in st.session_state:
            st.session_state['abos_view_type'] = None  # 'equipes' ou 'membres'
        
        annee_debut = st.number_input("Année de début de la période", min_value=2020, max_value=date.today().year, value=date.today().year-1, step=1)
        periode_aff = f"Sept {annee_debut} – Sept {annee_debut+1}"
        st.write(f"**Période :** {periode_aff}")
        
        # Statistiques générales
        total_membres = c.execute("SELECT COUNT(*) FROM membres WHERE statut='actif'").fetchone()[0]
        payes = c.execute("SELECT COUNT(*) FROM abonnements WHERE annee_debut=? AND statut='paye'", (annee_debut,)).fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("📊 Total membres actifs", total_membres)
        col2.metric("✅ Abonnements enregistrés", payes, delta=f"{payes/total_membres*100:.0f}%" if total_membres else "0%")
        
        st.markdown("---")
        st.markdown("### 🏛️ Paroisses")
        
        paroisses = c.execute("SELECT id, nom FROM paroisses ORDER BY nom").fetchall()
        
        for p in paroisses:
            pid, nom_paroisse = p
            
            # Statistiques de la paroisse
            stats = c.execute("""
                SELECT COUNT(m.id) as total, 
                    SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes
                FROM membres m
                LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=?
                WHERE m.paroisse_id=? AND m.statut='actif'
            """, (annee_debut, annee_debut, pid)).fetchone()
            
            total_par = stats[0] or 0
            payes_par = stats[1] or 0
            pourcent = f"{(payes_par/total_par*100):.0f}%" if total_par > 0 else "0%"
            
            with st.expander(f"🏛️ {nom_paroisse} - {total_par} membre(s) - {payes_par} à jour ({pourcent})"):
                # Boutons Voir les équipes et Voir tous les équipiers
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👥 Voir les équipes", key=f"abos_btn_equipes_{pid}"):
                        if st.session_state['show_paroisse_abos'] == pid and st.session_state['abos_view_type'] == 'equipes':
                            st.session_state['show_paroisse_abos'] = None
                            st.session_state['abos_view_type'] = None
                        else:
                            st.session_state['show_paroisse_abos'] = pid
                            st.session_state['abos_view_type'] = 'equipes'
                            st.session_state['show_equipe_abos'] = None
                        st.rerun()
                with col2:
                    if st.button(f"👤 Voir tous les équipiers", key=f"abos_btn_membres_{pid}"):
                        if st.session_state['show_paroisse_abos'] == pid and st.session_state['abos_view_type'] == 'membres':
                            st.session_state['show_paroisse_abos'] = None
                            st.session_state['abos_view_type'] = None
                        else:
                            st.session_state['show_paroisse_abos'] = pid
                            st.session_state['abos_view_type'] = 'membres'
                            st.session_state['show_equipe_abos'] = None
                        st.rerun()
                
                # --- Vue par équipes ---
                if st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'equipes':
                    st.markdown("---")
                    st.markdown(f"#### 👥 Équipes de {nom_paroisse}")
                    
                    equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
                    
                    if not equipes:
                        st.info("Aucune équipe dans cette paroisse")
                    else:
                        for eq in equipes:
                            eid, eq_nom = eq
                            
                            # Statistiques de l'équipe
                            stats_eq = c.execute("""
                                SELECT COUNT(m.id) as total,
                                    SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes
                                FROM membres m
                                LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=?
                                WHERE m.equipe_id=? AND m.statut='actif'
                            """, (annee_debut, annee_debut, eid)).fetchone()
                            
                            total_eq = stats_eq[0] or 0
                            payes_eq = stats_eq[1] or 0
                            pourcent_eq = f"{(payes_eq/total_eq*100):.0f}%" if total_eq > 0 else "0%"
                            
                            with st.expander(f"📌 {eq_nom} - {total_eq} membre(s) - {payes_eq} à jour ({pourcent_eq})"):
                                if st.button(f"📋 Voir les détails", key=f"abos_voir_eq_{eid}"):
                                    if st.session_state['show_equipe_abos'] == eid:
                                        st.session_state['show_equipe_abos'] = None
                                    else:
                                        st.session_state['show_equipe_abos'] = eid
                                    st.rerun()
                                
                                # Affichage des listes pour l'équipe
                                if st.session_state.get('show_equipe_abos') == eid:
                                    # Récupérer les données de l'équipe
                                    membres_eq = c.execute("""
                                        SELECT m.id, m.nom, m.prenom, m.matricule, 
                                            a.type_abonnement, a.date_paiement, a.montant
                                        FROM membres m
                                        LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=? AND a.statut='paye'
                                        WHERE m.equipe_id=? AND m.statut='actif'
                                        ORDER BY m.nom
                                    """, (annee_debut, eid)).fetchall()
                                    
                                    # Séparer les listes
                                    abonnes = []
                                    reabonnes = []
                                    non_inscrits = []
                                    
                                    for m in membres_eq:
                                        if m[4] == 'abonnement':
                                            abonnes.append(m)
                                        elif m[4] == 'reabonnement':
                                            reabonnes.append(m)
                                        else:
                                            non_inscrits.append(m)
                                    
                                    # Affichage des onglets
                                    tab1, tab2, tab3 = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
                                    
                                    with tab1:
                                        st.write(f"**Période :** {periode_aff}")
                                        if abonnes:
                                            data = []
                                            for a in abonnes:
                                                data.append({
                                                    "Nom": a[1], "Prénom": a[2], "Matricule": a[3],
                                                    "Date paiement": a[5], "Montant": f"{a[6]} FCFA"
                                                })
                                            df = pd.DataFrame(data)
                                            df.index = df.index + 1  # ✅ AJOUTEZ CETTE LIGNE
                                            st.dataframe(df, use_container_width=True)
                                            
                                            # Export Excel
                                            output = io.BytesIO()
                                            try:
                                                with pd.ExcelWriter(output, engine=None) as writer:
                                                    df.to_excel(writer, sheet_name=f"Abonnes_{eq_nom}", index=False)
                                                output.seek(0)
                                                st.download_button(f"📥 Exporter les abonnés de {eq_nom}", data=output,
                                                                file_name=f"abonnes_{eq_nom}_{annee_debut} - {annee_debut+1}.xlsx",
                                                                key=f"export_abos_eq_{eid}_{annee_debut}")
                                            except Exception as e:
                                                st.error(f"Erreur export: {e}")
                                        else:
                                            st.info("Aucun abonnement enregistré")
                                    
                                    with tab2:
                                        st.write(f"**Période :** {periode_aff}")
                                        if reabonnes:
                                            data = []
                                            for r in reabonnes:
                                                data.append({
                                                    "Nom": r[1], "Prénom": r[2], "Matricule": r[3],
                                                    "Date paiement": r[5], "Montant": f"{r[6]} FCFA"
                                                })
                                            df = pd.DataFrame(data)
                                            df.index = df.index + 1  # ✅ AJOUTEZ CETTE LIGNE
                                            st.dataframe(df, use_container_width=True)
                                            
                                            output = io.BytesIO()
                                            try:
                                                with pd.ExcelWriter(output, engine=None) as writer:
                                                    df.to_excel(writer, sheet_name=f"Reabonnes_{eq_nom}", index=False)
                                                output.seek(0)
                                                st.download_button(f"📥 Exporter les réabonnés de {eq_nom}", data=output,
                                                                file_name=f"reabonnes_{eq_nom}_{annee_debut}.xlsx",
                                                                key=f"export_reabos_eq_{eid}_{annee_debut}")
                                            except Exception as e:
                                                st.error(f"Erreur export: {e}")
                                        else:
                                            st.info("Aucun réabonnement enregistré")
                                    
                                    with tab3:
                                        if non_inscrits:
                                            for n in non_inscrits:
                                                st.write(f"- {n[1]} {n[2]} ({n[3]})")
                                        else:
                                            st.success("✓ Tous les membres sont à jour")
                
                # --- Vue par tous les équipiers de la paroisse ---
                if st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'membres':
                    st.markdown("---")
                    st.markdown(f"#### 👤 Tous les équipiers de {nom_paroisse}")
                    
                    # Récupérer tous les membres de la paroisse
                    membres_paroisse = c.execute("""
                        SELECT m.id, m.nom, m.prenom, m.matricule, m.whatsapp,
                            e.nom_equipe, a.type_abonnement, a.date_paiement, a.montant
                        FROM membres m
                        JOIN equipes e ON m.equipe_id = e.id
                        LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=? AND a.statut='paye'
                        WHERE m.paroisse_id=? AND m.statut='actif'
                        ORDER BY e.nom_equipe, m.nom
                    """, (annee_debut, pid)).fetchall()
                    
                    if not membres_paroisse:
                        st.info("Aucun membre actif dans cette paroisse")
                    else:
                        # Séparer les listes
                        abonnes_par = []
                        reabonnes_par = []
                        non_inscrits_par = []
                        
                        for m in membres_paroisse:
                            if m[6] == 'abonnement':
                                abonnes_par.append(m)
                            elif m[6] == 'reabonnement':
                                reabonnes_par.append(m)
                            else:
                                non_inscrits_par.append(m)
                        
                        # Statistiques
                        st.info(f"📊 Total : {len(membres_paroisse)} membre(s) - ✅ {len(abonnes_par)} abonné(s) - 🔄 {len(reabonnes_par)} réabonné(s) - ❌ {len(non_inscrits_par)} non enregistré(s)")
                        
                        # Affichage des onglets
                        tab1, tab2, tab3 = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
                        
                        with tab1:
                            st.write(f"**Période :** {periode_aff}")
                            if abonnes_par:
                                data = []
                                for a in abonnes_par:
                                    data.append({
                                        "Nom": a[1], "Prénom": a[2], "Matricule": a[3],
                                        "WhatsApp": a[4], "Équipe": a[5],
                                        "Date paiement": a[7], "Montant": f"{a[8]} FCFA"
                                    })
                                df = pd.DataFrame(data)
                                df.index = df.index + 1  # ✅ AJOUTEZ CETTE LIGNE
                                st.dataframe(df, use_container_width=True)
                                
                                output = io.BytesIO()
                                try:
                                    with pd.ExcelWriter(output, engine=None) as writer:
                                        df.to_excel(writer, sheet_name=f"Abonnes_{nom_paroisse}", index=False)
                                    output.seek(0)
                                    st.download_button(f"📥 Exporter les abonnés de {nom_paroisse}", data=output,
                                                    file_name=f"abonnes_{nom_paroisse}_{annee_debut} - {annee_debut+1}.xlsx",
                                                    key=f"export_abos_par_{pid}_{annee_debut}")
                                except Exception as e:
                                    st.error(f"Erreur export: {e}")
                            else:
                                st.info("Aucun abonnement enregistré")
                        
                        with tab2:
                            st.write(f"**Période :** {periode_aff}")
                            if reabonnes_par:
                                data = []
                                for r in reabonnes_par:
                                    data.append({
                                        "Nom": r[1], "Prénom": r[2], "Matricule": r[3],
                                        "WhatsApp": r[4], "Équipe": r[5],
                                        "Date paiement": r[7], "Montant": f"{r[8]} FCFA"
                                    })
                                df = pd.DataFrame(data)
                                df.index = df.index + 1  # ✅ AJOUTEZ CETTE LIGNE
                                st.dataframe(df, use_container_width=True)
                                
                                output = io.BytesIO()
                                try:
                                    with pd.ExcelWriter(output, engine=None) as writer:
                                        df.to_excel(writer, sheet_name=f"Reabonnes_{nom_paroisse}", index=False)
                                    output.seek(0)
                                    st.download_button(f"📥 Exporter les réabonnés de {nom_paroisse}", data=output,
                                                    file_name=f"reabonnes_{nom_paroisse}_{annee_debut}.xlsx",
                                                    key=f"export_reabos_par_{pid}_{annee_debut}")
                                except Exception as e:
                                    st.error(f"Erreur export: {e}")
                            else:
                                st.info("Aucun réabonnement enregistré")
                        
                        with tab3:
                            if non_inscrits_par:
                                for n in non_inscrits_par:
                                    st.write(f"- {n[1]} {n[2]} ({n[3]}) - {n[5]}")
                            else:
                                st.success("✓ Tous les membres sont à jour")

    # Suivi consultatif Diocèse
    elif menu == "📌 Suivi":
        st.markdown('<h2 style="color:#1A237E;">📌 Suivi et Agenda - Diocèse</h2>', unsafe_allow_html=True)
        tab_avenir, tab_passe = st.tabs(["📅 Agenda - A venir", "📝 Séances réalisées"])

        with tab_avenir:
            # Formulaire d'ajout
            ajouter_evenement_agenda(diocese_id=1, auteur_nom=st.session_state['username'])
            st.markdown("---")
            # Vue globale (Diocèse + Toutes Paroisses + Toutes Équipes)
            afficher_agenda_complet_universel(diocese_id=1)

        with tab_passe:
            st.subheader("📊 Historique des présences (Lecture seule)")
            paroisses = c.execute("SELECT id, nom FROM paroisses").fetchall()
            if paroisses:
                par_dict = {p[1]: p[0] for p in paroisses}
                choix_par = st.selectbox("Sélectionnez une paroisse", list(par_dict.keys()), key="suivi_hist_dio_par")
                pid_select = par_dict[choix_par]
                
                equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid_select,)).fetchall()
                if equipes:
                    eq_dict = {eq[1]: eq[0] for eq in equipes}
                    choix_eq = st.selectbox("Sélectionnez une équipe", list(eq_dict.keys()), key="suivi_hist_dio_eq")
                    eid_select = eq_dict[choix_eq]
                    
                    types_evenements = ["Tous", "Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage"]
                    filtre_type = st.selectbox("Filtrer par type", types_evenements, key="filtre_hist_dio")
                    afficher_historique_suivi(eid_select, filtre_type)
                else:
                    st.info("Aucune équipe dans cette paroisse.")
            else:
                st.info("Aucune paroisse créée.")

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
                duree = (date.fromisoformat(a[5]) - date.fromisoformat(a[4])).days // 365 if a[4] and a[5] else 0
                with st.expander(f"{icone} {a[1]} {a[2]} ({a[0]}) – {situation_affichee} – {a[5]}"):
                    st.write(f"Ajouté par : {a[9]}")
                    st.write(f"Paroisse : {a[7]}")
                    st.write(f"Équipe : {a[8]}")
                    if a[4] and a[5]:
                        st.write(f"Période : Sept {a[4].year} – Sept {a[5].year} ({duree} an(s))")
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
                commit_and_sync()
                st.success("Toutes les données ont été supprimées")
                st.balloons()
                st.rerun()

# ==================== PAROISSE ====================
elif st.session_state['role'] == 'paroisse':
    pid = st.session_state['paroisse_id']
    nom_paroisse = c.execute("SELECT nom FROM paroisses WHERE id=?", (pid,)).fetchone()[0]
    menu = st.sidebar.radio("Navigation", ["Ma paroisse", "Mes équipes", "Membres", "Statistiques", "Abonnements", "📌 Suivi", "WhatsApp", "Export Excel", "Archives"])
    
    # Ma paroisse
    if menu == "Ma paroisse":
        st.markdown(f'<h2 style="color:#1A237E;">🏘️ {nom_paroisse}</h2>', unsafe_allow_html=True)
        p = c.execute("SELECT commune, ville, responsable, bureau FROM paroisses WHERE id=?", (pid,)).fetchone()
        if p:
            st.write(f"Commune : {p[0]}")
            st.write(f"Ville : {p[1]}")
            st.write(f"**Responsable :** {p[2]}")
            st.write(f"**Bureau :** {p[3]}")
            
            # ✅ Ajout du bouton de modification
            with st.expander("✏️ Modifier les informations"):
                nouveau_respo = st.text_input("Nouveau responsable", value=p[2] or "")
                nouveau_bureau = st.text_area("Nouveau bureau", value=p[3] or "")
                if st.button("💾 Enregistrer les modifications", key="update_paroisse"):
                    if nouveau_respo:
                        c.execute("UPDATE paroisses SET responsable=?, bureau=? WHERE id=?", (nouveau_respo, nouveau_bureau, pid))
                        commit_and_sync()
                        st.success("Informations de la paroisse mises à jour ! ✅")
                        st.rerun()
                    else:
                        st.error("Le nom du responsable est obligatoire.")

    # Mes équipes (Paroisse) - Version avec vérification renforcée
    elif menu == "Mes équipes":
        st.markdown(f'<h2 style="color:#1A237E;">👥 Équipes de {nom_paroisse}</h2>', unsafe_allow_html=True)
        
        # Initialisation des états
        if 'show_equipe_details' not in st.session_state:
            st.session_state['show_equipe_details'] = None
        if 'show_membres_equipe_par' not in st.session_state:
            st.session_state['show_membres_equipe_par'] = None
        if 'new_equipe_info' not in st.session_state:
            st.session_state['new_equipe_info'] = None
        if 'resp_doublon' not in st.session_state:
            st.session_state['resp_doublon'] = None
        
        info_paroisse = c.execute("SELECT nom, commune FROM paroisses WHERE id=?", (pid,)).fetchone()
        nom_clean = info_paroisse[0].lower()
        for mot in ["saint ", "sainte ", "notre-dame ", "dame ", "st ", "ste ", "nd "]:
            if nom_clean.startswith(mot):
                nom_clean = nom_clean[len(mot):]
        prefixe = sans_accents(nom_clean[:3] + info_paroisse[1][:3])
        
        # Fonction utilitaire de création d'équipe
        def creer_equipe(nom_eq, responsable, bureau):
            nb = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
            identifiant = f"{prefixe}eq{nb+1}"
            mdp = generer_mot_de_passe()
            c.execute("INSERT INTO equipes (nom_equipe, responsable, bureau, paroisse_id) VALUES (?,?,?,?)", 
                    (nom_eq, responsable, bureau, pid))
            eid_new = c.lastrowid
            c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id, equipe_id) VALUES (?,?,?,?,?)", 
                    (identifiant, hash_password(mdp), "equipe", pid, eid_new))
            commit_and_sync()
            st.session_state['new_equipe_info'] = {
                'nom': nom_eq,
                'identifiant': identifiant,
                'mdp': mdp
            }
        
        # Formulaire de création d'équipe
        with st.expander("➕ Créer une équipe"):
            with st.form("creer_equipe"):
                nom_eq = st.text_input("Nom de l'équipe (ex: 3, Jeune, Enfant)")
                responsable = st.text_input("Responsable")
                bureau = st.text_area("Bureau")
                submitted = st.form_submit_button("Créer")
                
                if submitted:
                    if nom_eq and responsable:
                        # Vérification doublon nom
                        existe_nom = c.execute("SELECT id FROM equipes WHERE nom_equipe=? AND paroisse_id=?", (nom_eq, pid)).fetchone()
                        if existe_nom:
                            st.error(f"❌ Une équipe nommée '{nom_eq}' existe déjà dans cette paroisse !")
                        else:
                            # Vérification doublon responsable
                            existe_resp = c.execute("SELECT id, nom_equipe FROM equipes WHERE responsable=? AND paroisse_id=?", (responsable, pid)).fetchone()
                            if existe_resp:
                                st.session_state['resp_doublon'] = {
                                    'nom_eq': nom_eq,
                                    'responsable': responsable,
                                    'bureau': bureau,
                                    'equipe_existante': existe_resp[1]
                                }
                                st.warning(f"⚠️ Le responsable '{responsable}' est déjà responsable de l'équipe '{existe_resp[1]}'. Veuillez confirmer la création ci-dessous.")
                            else:
                                creer_equipe(nom_eq, responsable, bureau)
                                st.rerun()
                    else:
                        st.error("Le nom et le responsable sont requis")
            
            # Affichage de la confirmation si doublon responsable
            if st.session_state.get('resp_doublon'):
                info = st.session_state['resp_doublon']
                st.warning(f"Le responsable '{info['responsable']}' est déjà responsable de l'équipe '{info['equipe_existante']}'.")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Confirmer la création", key="confirm_creation"):
                        creer_equipe(info['nom_eq'], info['responsable'], info['bureau'])
                        st.session_state['resp_doublon'] = None
                        st.rerun()
                with col2:
                    if st.button("❌ Annuler", key="cancel_creation"):
                        st.session_state['resp_doublon'] = None
                        st.rerun()
            
            # Affichage des informations de la nouvelle équipe
            if st.session_state.get('new_equipe_info'):
                info = st.session_state['new_equipe_info']
                st.success(f"✅ Équipe '{info['nom']}' créée avec succès !")
                st.markdown(f"""
                <div style='background-color: #e8f5e9; padding: 15px; border-radius: 10px; margin-top: 10px;'>
                    <strong>🔑 Identifiant :</strong> <code>{info['identifiant']}</code><br>
                    <strong>🔒 Mot de passe :</strong> <code>{info['mdp']}</code><br>
                    <small>⚠️ Veuillez noter ces informations. Le mot de passe devra être changé à la première connexion.</small>
                </div>
                """, unsafe_allow_html=True)
                if st.button("OK", key="clear_equipe_info"):
                    st.session_state['new_equipe_info'] = None
                    st.rerun()
        
        st.markdown("---")
        
        # Liste des équipes existantes (le reste du code inchangé)
        equipes = c.execute("SELECT id, nom_equipe, responsable, bureau FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
        
        if not equipes:
            st.info("Aucune équipe dans cette paroisse")
        else:
            for eq in equipes:
                eq_id, eq_nom, eq_resp, eq_bureau = eq
                nb_membres = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eq_id,)).fetchone()[0]
                
                with st.expander(f"📌 {eq_nom} - Respo: {eq_resp} ({nb_membres}/10 membres)"):
                    st.write(f"**Bureau :** {eq_bureau}")
                    
                    # Bouton pour voir les membres
                    if st.button(f"👥 Voir les membres", key=f"par_voir_membres_{eq_id}"):
                        if st.session_state['show_membres_equipe_par'] == eq_id:
                            st.session_state['show_membres_equipe_par'] = None
                        else:
                            st.session_state['show_membres_equipe_par'] = eq_id
                            st.session_state['show_equipe_details'] = None
                        st.rerun()
                    
                    # Bouton pour modifier/supprimer l'équipe
                    if st.button(f"⚙️ Gérer l'équipe", key=f"par_gerer_equipe_{eq_id}"):
                        if st.session_state['show_equipe_details'] == eq_id:
                            st.session_state['show_equipe_details'] = None
                        else:
                            st.session_state['show_equipe_details'] = eq_id
                            st.session_state['show_membres_equipe_par'] = None
                        st.rerun()
                    
                    # Affichage des membres de l'équipe
                    if st.session_state.get('show_membres_equipe_par') == eq_id:
                        st.markdown("---")
                        st.markdown(f"#### 👤 Membres de {eq_nom}")
                        membres_eq = c.execute("""
                            SELECT m.id, m.matricule, m.nom, m.prenom, m.whatsapp, m.numero_meditation, m.date_adhesion
                            FROM membres m
                            WHERE m.equipe_id=? AND m.statut='actif'
                            ORDER BY m.nom
                        """, (eq_id,)).fetchall()
                        
                        if not membres_eq:
                            st.info("Aucun membre dans cette équipe")
                        else:
                            data = []
                            for m in membres_eq:
                                data.append({
                                    "Matricule": m[1],
                                    "Nom": m[2],
                                    "Prénom": m[3],
                                    "WhatsApp": m[4],
                                    "N° méditation": m[5] or "-",
                                    "Date adhésion": m[6]
                                })
                            df = pd.DataFrame(data)
                            df.index = df.index + 1  # ✅ AJOUTEZ CETTE LIGNE
                            st.dataframe(df, use_container_width=True)
                            
                            output = io.BytesIO()
                            try:
                                with pd.ExcelWriter(output, engine=None) as writer:
                                    df.to_excel(writer, sheet_name=f"Membres_{eq_nom}", index=False)
                                output.seek(0)
                                st.download_button(
                                    f"📥 Exporter les membres de {eq_nom}",
                                    data=output,
                                    file_name=f"membres_{eq_nom}_{nom_paroisse}_{date.today()}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key=f"export_membres_par_eq_{eq_id}_{date.today()}"
                                )
                            except Exception as e:
                                st.error(f"Erreur export: {e}")
                    
                    # Gestion de l'équipe (modification/suppression)
                    if st.session_state.get('show_equipe_details') == eq_id:
                        st.markdown("---")
                        st.markdown(f"#### ⚙️ Gestion de {eq_nom}")
                        
                        user_info = c.execute("SELECT username FROM utilisateurs WHERE equipe_id=? AND role='equipe'", (eq_id,)).fetchone()
                        if user_info:
                            st.info(f"🔑 Identifiant de connexion : `{user_info[0]}`")
                        
                        with st.form(f"form_gerer_equipe_{eq_id}"):
                            new_nom = st.text_input("Nom de l'équipe", value=eq_nom)
                            new_resp = st.text_input("Responsable", value=eq_resp)
                            new_bureau = st.text_area("Bureau", value=eq_bureau or "")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("💾 Mettre à jour"):
                                    if new_nom != eq_nom:
                                        existe = c.execute("SELECT id FROM equipes WHERE nom_equipe=? AND paroisse_id=? AND id!=?", (new_nom, pid, eq_id)).fetchone()
                                        if existe:
                                            st.error(f"❌ Une équipe nommée '{new_nom}' existe déjà dans cette paroisse !")
                                        else:
                                            c.execute("UPDATE equipes SET nom_equipe=?, responsable=?, bureau=? WHERE id=?", 
                                                    (new_nom, new_resp, new_bureau, eq_id))
                                            commit_and_sync()
                                            st.success("Équipe mise à jour")
                                            st.session_state['show_equipe_details'] = None
                                            st.rerun()
                                    else:
                                        c.execute("UPDATE equipes SET nom_equipe=?, responsable=?, bureau=? WHERE id=?", 
                                                (new_nom, new_resp, new_bureau, eq_id))
                                        commit_and_sync()
                                        st.success("Équipe mise à jour")
                                        st.session_state['show_equipe_details'] = None
                                        st.rerun()
                            with col2:
                                if nb_membres == 0:
                                    if st.form_submit_button("🗑️ Supprimer l'équipe"):
                                        c.execute("DELETE FROM equipes WHERE id=?", (eq_id,))
                                        c.execute("DELETE FROM utilisateurs WHERE equipe_id=?", (eq_id,))
                                        commit_and_sync()
                                        st.success("Équipe supprimée")
                                        st.session_state['show_equipe_details'] = None
                                        st.rerun()
                                else:
                                    st.warning(f"⚠️ Impossible de supprimer : {nb_membres} membre(s) dans cette équipe")
                        
                        if user_info:
                            if st.button(f"🔄 Réinitialiser le mot de passe", key=f"reset_mdp_{eq_id}"):
                                nouveau_mdp = generer_mot_de_passe()
                                c.execute("UPDATE utilisateurs SET password=? WHERE equipe_id=?", (hash_password(nouveau_mdp), eq_id))
                                commit_and_sync()
                                st.success("Mot de passe réinitialisé !")
                                st.code(f"Nouveau mot de passe : {nouveau_mdp}", language="text")    
        
    # Membres (Paroisse) - Version fluidifiée avec gestion unique
    elif menu == "Membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres de {nom_paroisse}</h2>', unsafe_allow_html=True)
        
        # Initialisation des états
        if 'open_form_par' not in st.session_state:
            st.session_state['open_form_par'] = None
        
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
        if not equipes:
            st.warning("Aucune équipe. Créez une équipe d'abord.")
        else:
            equipe_dict = {eq[1]: eq[0] for eq in equipes}
            choix = st.selectbox("Équipe", list(equipe_dict.keys()))
            eid = equipe_dict[choix]
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut=?", (eid, 'actif')).fetchone()[0]
            st.info(f"{nb}/10 membres")
            
            # Formulaire d'ajout
            if nb < 10:
                if st.button("➕ Ajouter un membre", key="btn_ajout_par"):
                    if st.session_state['open_form_par'] == "ajout":
                        st.session_state['open_form_par'] = None
                    else:
                        st.session_state['open_form_par'] = "ajout"
                    st.rerun()
                
                if st.session_state.get('open_form_par') == "ajout":
                    with st.container():
                        st.markdown("---")
                        st.markdown("#### ➕ Nouveau membre")
                        with st.form("form_ajout_par"):
                            col1, col2 = st.columns(2)
                            with col1:
                                nom = st.text_input("Nom")
                                prenom = st.text_input("Prénom")
                                naissance = st.date_input("Date de naissance", min_value=date(1940,1,1), max_value=date.today())
                            with col2:
                                whatsapp = st.text_input("WhatsApp")
                                numero_meditation = st.text_input("N° méditation", max_chars=2)
                                photo = st.file_uploader("Photo", type=['jpg','png','jpeg'])
                                date_adhesion = st.date_input("Date d'adhésion", min_value=date(1940,1,1), max_value=date.today(), value=date.today())
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("❌ Annuler"):
                                    st.session_state['open_form_par'] = None
                                    st.rerun()
                            with col2:
                                if st.form_submit_button("✅ Ajouter"):
                                    if nom and prenom:
                                        existant = c.execute("SELECT id FROM membres WHERE nom=? AND prenom=? AND date_naissance=? AND statut=?", 
                                                        (nom, prenom, naissance, 'actif')).fetchone()
                                        if existant:
                                            st.error("Ce membre existe déjà actif.")
                                        else:
                                            matricule = generer_matricule_unique()
                                            c.execute("""INSERT INTO membres 
                                                (matricule, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id, statut, numero_meditation) 
                                                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                                (matricule, nom, prenom, naissance, whatsapp, date_adhesion, pid, eid, 'actif', numero_meditation))
                                            mid = c.lastrowid
                                            if photo:
                                                chemin = sauvegarder_photo(photo, matricule)
                                                c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                            commit_and_sync()
                                            st.session_state['open_form_par'] = None
                                            st.success(f"Ajouté ! Matricule: {matricule}")
                                            st.rerun()
                                    else:
                                        st.error("Le nom et le prénom sont requis.")
            
            # Liste des membres
            st.markdown("---")
            membres = c.execute("""
                SELECT id, matricule, nom, prenom, whatsapp, photo_path, date_adhesion, numero_meditation 
                FROM membres 
                WHERE equipe_id=? AND statut=? 
                ORDER BY nom
            """, (eid, 'actif')).fetchall()
            
            for m in membres:
                id_m, matricule, nom, prenom, whatsapp, photo_path, date_adhesion, num_med = m
                
                with st.expander(f"{nom} {prenom} - {matricule}" + (f" - N° {num_med}" if num_med else "")):
                    col1, col2 = st.columns([3,1])
                    col1.write(f"💬 WhatsApp: {whatsapp}")
                    col1.write(f"📅 Adhésion: {date_adhesion}")
                    if photo_path:
                        col1.image(photo_path, width=80)
                    
                    with col2:
                        if st.button("✏️ Modifier", key=f"par_btn_mod_{id_m}"):
                            if st.session_state['open_form_par'] == f"mod_{id_m}":
                                st.session_state['open_form_par'] = None
                            else:
                                st.session_state['open_form_par'] = f"mod_{id_m}"
                            st.rerun()
                        if st.button("📦 Archiver", key=f"par_btn_arch_{id_m}"):
                            if st.session_state['open_form_par'] == f"arch_{id_m}":
                                st.session_state['open_form_par'] = None
                            else:
                                st.session_state['open_form_par'] = f"arch_{id_m}"
                            st.rerun()
                        if st.button("🔄 Transférer", key=f"par_btn_transf_{id_m}"):
                            if st.session_state['open_form_par'] == f"transf_{id_m}":
                                st.session_state['open_form_par'] = None
                            else:
                                st.session_state['open_form_par'] = f"transf_{id_m}"
                            st.rerun()
                    
                    # Formulaire de modification
                    if st.session_state.get('open_form_par') == f"mod_{id_m}":
                        st.markdown("---")
                        st.markdown("#### ✏️ Modification")
                        membre_data = c.execute("SELECT nom, prenom, whatsapp, photo_path, numero_meditation FROM membres WHERE id=?", (id_m,)).fetchone()
                        if membre_data:
                            with st.form(f"form_mod_par_{id_m}"):
                                new_nom = st.text_input("Nom", value=membre_data[0])
                                new_prenom = st.text_input("Prénom", value=membre_data[1])
                                new_whatsapp = st.text_input("WhatsApp", value=membre_data[2])
                                new_num_med = st.text_input("N° méditation", value=membre_data[4] or "", max_chars=2)
                                new_photo = st.file_uploader("Nouvelle photo", type=['jpg','png','jpeg'])
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("❌ Annuler"):
                                        st.session_state['open_form_par'] = None
                                        st.rerun()
                                with col2:
                                    if st.form_submit_button("💾 Enregistrer"):
                                        c.execute("UPDATE membres SET nom=?, prenom=?, whatsapp=?, numero_meditation=? WHERE id=?", 
                                                (new_nom, new_prenom, new_whatsapp, new_num_med, id_m))
                                        if new_photo:
                                            if membre_data[3] and os.path.exists(membre_data[3]):
                                                os.remove(membre_data[3])
                                            chemin = sauvegarder_photo(new_photo, matricule)
                                            c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, id_m))
                                        commit_and_sync()
                                        st.session_state['open_form_par'] = None
                                        st.success("Membre modifié")
                                        st.rerun()
                    
                    # Formulaire d'archivage
                    elif st.session_state.get('open_form_par') == f"arch_{id_m}":
                        st.markdown("---")
                        st.markdown("#### 📦 Archivage")
                        with st.form(f"form_arch_par_{id_m}"):
                            situation = st.radio("Situation", ["Déplacé", "Radié", "Défunt"])
                            col1, col2 = st.columns(2)
                            with col1:
                                annee_debut_arch = st.number_input("Année de début (Sept)", min_value=2000, max_value=date.today().year+5, value=date.today().year, step=1)
                            with col2:
                                annee_fin_arch = st.number_input("Année de fin (Sept)", min_value=2000, max_value=date.today().year+10, value=date.today().year+1, step=1)
                            commentaire = st.text_area("Commentaire")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("❌ Annuler"):
                                    st.session_state['open_form_par'] = None
                                    st.rerun()
                            with col2:
                                if st.form_submit_button("✅ Archiver"):
                                    if annee_fin_arch <= annee_debut_arch:
                                        st.error("L'année de fin doit être après l'année de début.")
                                    else:
                                        date_debut_arch = date(annee_debut_arch, 9, 1)
                                        date_fin_arch = date(annee_fin_arch, 9, 1)
                                        archiver_membre(id_m, situation, date_debut_arch, date_fin_arch, commentaire,
                                                        st.session_state['user_id'], st.session_state['username'], 'paroisse', pid, eid)
                                        st.session_state['open_form_par'] = None
                                        st.success("Membre archivé")
                                        st.rerun()
                    
                    # Formulaire de transfert
                    elif st.session_state.get('open_form_par') == f"transf_{id_m}":
                        st.markdown("---")
                        st.markdown("#### 🔄 Transfert")
                        with st.form(f"form_transf_par_{id_m}"):
                            paroisses = c.execute("SELECT id, nom FROM paroisses ORDER BY nom").fetchall()
                            paroisse_dest = st.selectbox("Paroisse de destination", paroisses, format_func=lambda x: x[1])
                            nouvelle_paroisse_id = paroisse_dest[0]
                            
                            equipes_dest = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (nouvelle_paroisse_id,)).fetchall()
                            if equipes_dest:
                                equipe_dest = st.selectbox("Équipe de destination", equipes_dest, format_func=lambda x: x[1])
                                nouvelle_equipe_id = equipe_dest[0]
                            else:
                                st.error("Aucune équipe dans cette paroisse")
                                nouvelle_equipe_id = None
                            
                            motif = st.text_area("Motif du transfert (optionnel)")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("❌ Annuler"):
                                    st.session_state['open_form_par'] = None
                                    st.rerun()
                            with col2:
                                if st.form_submit_button("✅ Transférer"):
                                    if nouvelle_equipe_id:
                                        if nouvelle_paroisse_id == pid:
                                            c.execute("UPDATE membres SET equipe_id=? WHERE id=?", (nouvelle_equipe_id, id_m))
                                            commit_and_sync()
                                            st.success(f"Transfert effectué vers {equipe_dest}")
                                        else:
                                            date_adhesion_membre = c.execute("SELECT date_adhesion FROM membres WHERE id=?", (id_m,)).fetchone()[0]
                                            if isinstance(date_adhesion_membre, str):
                                                date_adhesion_membre = date.fromisoformat(date_adhesion_membre)
                                            commentaire_archive = f"Transféré vers {paroisse_dest[1]} / {equipe_dest}"
                                            c.execute("""INSERT INTO archives 
                                                (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id)
                                                VALUES (?, 'Transféré', ?, ?, ?, ?, ?, ?, ?, ?)""",
                                                (id_m, date_adhesion_membre, date.today(), commentaire_archive,
                                                st.session_state['user_id'], st.session_state['username'], 'paroisse', pid, eid))
                                            c.execute("UPDATE membres SET paroisse_id=?, equipe_id=? WHERE id=?", 
                                                    (nouvelle_paroisse_id, nouvelle_equipe_id, id_m))
                                            commit_and_sync()
                                            st.success(f"Membre transféré vers {paroisse_dest[1]} / {equipe_dest}")
                                        st.session_state['open_form_par'] = None
                                        st.rerun()
            
            # Export Excel
            if membres:
                st.markdown("---")
                st.markdown("### 📊 Export des données")
                df_export = pd.DataFrame([(m[1], m[2], m[3], m[7], m[4], m[6]) for m in membres], 
                                        columns=["Matricule", "Nom", "Prénom", "N° méditation", "WhatsApp", "Date adhésion"])
                output = io.BytesIO()
                try:
                    with pd.ExcelWriter(output, engine=None) as writer:
                        df_export.to_excel(writer, sheet_name=f"Membres_{choix}", index=False)
                    output.seek(0)
                    st.download_button(
                        "📥 Exporter les membres (Excel)", 
                        data=output, 
                        file_name=f"membres_{choix}_{nom_paroisse}_{date.today()}.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"export_membres_par_{choix}_{date.today()}"
                    )
                except Exception as e:
                    st.error(f"Erreur export: {e}")

    # Statistiques
    elif menu == "Statistiques":
        st.markdown(f'<h2 style="color:#1A237E;">📊 Statistiques de {nom_paroisse}</h2>', unsafe_allow_html=True)
        nb_eq = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
        nb_m = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("Équipes", nb_eq)
        col2.metric("Membres actifs", nb_m)
    
    # Abonnements (Paroisse) - Version hiérarchisée comme Diocèse
    elif menu == "Abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 Gestion des abonnements - {nom_paroisse}</h2>', unsafe_allow_html=True)
        
        # Initialisation des états
        if 'show_equipe_abos_par' not in st.session_state:
            st.session_state['show_equipe_abos_par'] = None
        
        annee_debut = st.number_input("Année de début de la période", min_value=2020, max_value=date.today().year, value=date.today().year-1, step=1)
        periode_aff = f"Sept {annee_debut} – Sept {annee_debut+1}"
        st.write(f"**Période :** {periode_aff}")
        
        # Statistiques de la paroisse
        total_membres = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0]
        payes = c.execute("SELECT COUNT(*) FROM abonnements a JOIN membres m ON a.membre_id=m.id WHERE m.paroisse_id=? AND a.annee_debut=? AND a.statut='paye'", (pid, annee_debut)).fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("📊 Total membres actifs", total_membres)
        col2.metric("✅ Abonnements enregistrés", payes, delta=f"{payes/total_membres*100:.0f}%" if total_membres else "0%")
        
        st.markdown("---")
        st.markdown("### 👥 Équipes")
        
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
        
        for eq in equipes:
            eid_eq, nom_eq = eq
            
            stats_eq = c.execute("""
                SELECT COUNT(m.id) as total,
                    SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes
                FROM membres m
                LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=?
                WHERE m.equipe_id=? AND m.statut='actif'
            """, (annee_debut, annee_debut, eid_eq)).fetchone()
            
            total_eq = stats_eq[0] or 0
            payes_eq = stats_eq[1] or 0
            pourcent_eq = f"{(payes_eq/total_eq*100):.0f}%" if total_eq > 0 else "0%"
            
            with st.expander(f"📌 {nom_eq} - {total_eq} membre(s) - {payes_eq} à jour ({pourcent_eq})"):
                if st.button(f"📋 Voir les détails", key=f"abos_par_voir_eq_{eid_eq}"):
                    if st.session_state['show_equipe_abos_par'] == eid_eq:
                        st.session_state['show_equipe_abos_par'] = None
                    else:
                        st.session_state['show_equipe_abos_par'] = eid_eq
                    st.rerun()
                
                if st.session_state.get('show_equipe_abos_par') == eid_eq:
                    membres_eq = c.execute("""
                        SELECT m.id, m.nom, m.prenom, m.matricule, 
                            a.type_abonnement, a.date_paiement, a.montant
                        FROM membres m
                        LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=? AND a.statut='paye'
                        WHERE m.equipe_id=? AND m.statut='actif'
                        ORDER BY m.nom
                    """, (annee_debut, eid_eq)).fetchall()
                    
                    abonnes = [m for m in membres_eq if m[4] == 'abonnement']
                    reabonnes = [m for m in membres_eq if m[4] == 'reabonnement']
                    non_inscrits = [m for m in membres_eq if m[4] is None]

                    tab1, tab2, tab3 = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
                    
                    with tab1:
                        st.write(f"**Période :** {periode_aff}")
                        if abonnes:
                            data = [{"N°": i+1, "Nom": a[1], "Prénom": a[2], "Matricule": a[3], "Date paiement": a[5], "Montant": f"{a[6]} FCFA"} for i, a in enumerate(abonnes)]
                            df_abonnes = pd.DataFrame(data)
                            # ✅ CORRECTION : On met l'index Pandas à 1 au lieu de 0
                            df_abonnes.index = df_abonnes.index + 1
                            st.dataframe(df_abonnes, use_container_width=True)
                            
                            output = io.BytesIO()
                            try:
                                with pd.ExcelWriter(output, engine=None) as writer:
                                    # Pour l'export Excel, on garde index=False pour ne pas avoir la colonne d'index en double
                                    pd.DataFrame(data).to_excel(writer, sheet_name=f"Abonnes_{nom_eq}", index=False)
                                output.seek(0)
                                st.download_button(f"📥 Exporter les abonnés", data=output,
                                                file_name=f"abonnes_{nom_eq}_{nom_paroisse}_{annee_debut} - {annee_debut+1}.xlsx",
                                                key=f"export_abos_par_eq_{eid_eq}_{annee_debut}")
                            except Exception as e:
                                st.error(f"Erreur export: {e}")
                        else:
                            st.info("Aucun abonnement")
                    
                    with tab2:
                        st.write(f"**Période :** {periode_aff}")
                        if reabonnes:
                            data = [{"N°": i+1, "Nom": r[1], "Prénom": r[2], "Matricule": r[3], "Date paiement": r[5], "Montant": f"{r[6]} FCFA"} for i, r in enumerate(reabonnes)]
                            df_reabonnes = pd.DataFrame(data)
                            # ✅ CORRECTION : On met l'index Pandas à 1 au lieu de 0
                            df_reabonnes.index = df_reabonnes.index + 1
                            st.dataframe(df_reabonnes, use_container_width=True)
                            
                            output = io.BytesIO()
                            try:
                                with pd.ExcelWriter(output, engine=None) as writer:
                                    pd.DataFrame(data).to_excel(writer, sheet_name=f"Reabonnes_{nom_eq}", index=False)
                                output.seek(0)
                                st.download_button(f"📥 Exporter les réabonnés", data=output,
                                                file_name=f"reabonnes_{nom_eq}_{nom_paroisse}_{annee_debut} - {annee_debut+1}.xlsx",
                                                key=f"export_reabos_par_eq_{eid_eq}_{annee_debut}")
                            except Exception as e:
                                st.error(f"Erreur export: {e}")
                        else:
                            st.info("Aucun réabonnement")
                    
                    with tab3:
                        if non_inscrits:
                            # ✅ AMÉLIORATION : Affichage sous forme de tableau numéroté au lieu de tirets
                            data_non_inscrits = [{"N°": i+1, "Nom": n[1], "Prénom": n[2], "Matricule": n[3]} for i, n in enumerate(non_inscrits)]
                            df_non_inscrits = pd.DataFrame(data_non_inscrits)
                            df_non_inscrits.index = df_non_inscrits.index + 1
                            st.dataframe(df_non_inscrits, use_container_width=True)
                        else:
                            st.success("✓ Tous les membres sont à jour")    

    # Suivi consultatif Paroisse
    elif menu == "📌 Suivi":
        st.markdown(f'<h2 style="color:#1A237E;">📌 Suivi et Agenda - {nom_paroisse}</h2>', unsafe_allow_html=True)
        tab_avenir, tab_passe = st.tabs(["📅 Agenda - A venir", "📝 Séances réalisées"])

        with tab_avenir:
            # Formulaire d'ajout
            ajouter_evenement_agenda(paroisse_id=pid, auteur_nom=st.session_state['username'])
            st.markdown("---")
            # Vue globale (Paroisse + Équipes enfants + Diocèse)
            afficher_agenda_complet_universel(paroisse_id=pid)

        with tab_passe:
            st.subheader("📊 Historique des présences (Lecture seule)")
            equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
            if equipes:
                eq_dict = {eq[1]: eq[0] for eq in equipes}
                choix_eq = st.selectbox("Sélectionnez une équipe", list(eq_dict.keys()), key="suivi_hist_par_eq")
                eid_select = eq_dict[choix_eq]
                
                types_evenements = ["Tous", "Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage"]
                filtre_type = st.selectbox("Filtrer par type", types_evenements, key="filtre_hist_par")
                afficher_historique_suivi(eid_select, filtre_type)
            else:
                st.info("Aucune équipe créée.")

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
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=f"Membres_{nom_paroisse}", index=False)
            output.seek(0)
            st.download_button("📥 Télécharger Excel", data=output, file_name=f"membres_{nom_paroisse}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("Aucun membre actif")
    
    # Archives (lecture seule)
    elif menu == "Archives":
        st.markdown(f'<h2 style="color:#1A237E;">📦 Archives de la paroisse {nom_paroisse}</h2>', unsafe_allow_html=True)
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
                duree = (date.fromisoformat(a[5]) - date.fromisoformat(a[4])).days // 365 if a[4] and a[5] else 0
                with st.expander(f"{icone} {a[1]} {a[2]} ({a[0]}) – {situation_affichee} – {a[5]}"):
                    st.write(f"Ajouté par : {a[8]}")
                    st.write(f"Équipe : {a[7]}")
                    if a[4] and a[5]:
                        st.write(f"Période : Sept {a[4].year} – Sept {a[5].year} ({duree} an(s))")
                    if a[6]:
                        st.write(f"Commentaire : {a[6]}")

# ==================== ÉQUIPE ====================
elif st.session_state['role'] == 'equipe':
    eid = st.session_state['equipe_id']
    equipe_info = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (eid,)).fetchone()
    nom_equipe = equipe_info[0] if equipe_info else "Mon équipe"
    
    menu = st.sidebar.radio("Navigation", [
        "Mon équipe", "Mes membres", "Abonnements", "📌 Suivi", "WhatsApp", "Archives"])

    # ✅ Nettoyage du session_state au changement de menu (pour éviter les formulaires qui restent ouverts)
    if st.session_state.get('last_menu') != menu:
        for key in ['modif_membre_id', 'archiver_membre_id', 'confirmer_suppr_id', 'modif_abo_id']:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state['last_menu'] = menu

    # Mon équipe
    if menu == "Mon équipe":
        # ... (la suite de votre code)
        st.markdown(f'<h2 style="color:#1A237E;">👥 {nom_equipe}</h2>', unsafe_allow_html=True)
        eq = c.execute("SELECT responsable, bureau FROM equipes WHERE id=?", (eid,)).fetchone()
        if eq:
            st.write(f"**Responsable :** {eq[0]}")
            st.write(f"**Bureau :** {eq[1]}")
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchone()[0]
            st.metric("Effectif", f"{nb}/10")
            
            # ✅ Ajout du bouton de modification
            with st.expander("✏️ Modifier les informations"):
                nouveau_respo = st.text_input("Nouveau responsable", value=eq[0] or "")
                nouveau_bureau = st.text_area("Nouveau bureau", value=eq[1] or "")
                if st.button("💾 Enregistrer les modifications", key="update_equipe"):
                    if nouveau_respo:
                        c.execute("UPDATE equipes SET responsable=?, bureau=? WHERE id=?", (nouveau_respo, nouveau_bureau, eid))
                        commit_and_sync()
                        st.success("Informations de l'équipe mises à jour ! ✅")
                        st.rerun()
                    else:
                        st.error("Le nom du responsable est obligatoire.")    

    # Mes membres (Équipe) - Version fluidifiée
    elif menu == "Mes membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres de {nom_equipe}</h2>', unsafe_allow_html=True)
        
        # Initialisation des états
        if 'open_form_eq' not in st.session_state:
            st.session_state['open_form_eq'] = None
        
        # Récupérer le nom de la paroisse
        paroisse_nom = c.execute("SELECT p.nom FROM paroisses p JOIN equipes e ON p.id = e.paroisse_id WHERE e.id=?", (eid,)).fetchone()[0]
        
        nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut=?", (eid, 'actif')).fetchone()[0]
        st.info(f"{nb}/10 membres")
        
        # Formulaire d'ajout
        if nb < 10:
            if st.button("➕ Ajouter un membre", key="btn_ajout_eq"):
                if st.session_state['open_form_eq'] == "ajout":
                    st.session_state['open_form_eq'] = None
                else:
                    st.session_state['open_form_eq'] = "ajout"
                st.rerun()
            
            if st.session_state.get('open_form_eq') == "ajout":
                with st.container():
                    st.markdown("---")
                    st.markdown("#### ➕ Nouveau membre")
                    with st.form("form_ajout_eq"):
                        col1, col2 = st.columns(2)
                        with col1:
                            nom = st.text_input("Nom")
                            prenom = st.text_input("Prénom")
                            naissance = st.date_input("Date de naissance", min_value=date(1940,1,1), max_value=date.today())
                        with col2:
                            whatsapp = st.text_input("WhatsApp")
                            numero_meditation = st.text_input("N° méditation", max_chars=2)
                            photo = st.file_uploader("Photo", type=['jpg','png','jpeg'])
                            date_adhesion = st.date_input("Date d'adhésion", min_value=date(1940,1,1), max_value=date.today(), value=date.today())
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("❌ Annuler"):
                                st.session_state['open_form_eq'] = None
                                st.rerun()
                        with col2:
                            if st.form_submit_button("✅ Ajouter"):
                                if nom and prenom:
                                    existant = c.execute("SELECT id FROM membres WHERE nom=? AND prenom=? AND date_naissance=? AND statut=?", 
                                                    (nom, prenom, naissance, 'actif')).fetchone()
                                    if existant:
                                        st.error("Membre déjà actif")
                                    else:
                                        matricule = generer_matricule_unique()
                                        paroisse_id = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()[0]
                                        c.execute("""INSERT INTO membres 
                                            (matricule, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id, statut, numero_meditation) 
                                            VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                            (matricule, nom, prenom, naissance, whatsapp, date_adhesion, paroisse_id, eid, 'actif', numero_meditation))
                                        mid = c.lastrowid
                                        if photo:
                                            chemin = sauvegarder_photo(photo, matricule)
                                            c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, mid))
                                        commit_and_sync()
                                        st.session_state['open_form_eq'] = None
                                        st.success(f"Ajouté ! Matricule: {matricule}")
                                        st.rerun()
                                else:
                                    st.error("Le nom et le prénom sont requis.")
        
        # Liste des membres
        st.markdown("---")
        membres = c.execute("""
            SELECT id, matricule, nom, prenom, whatsapp, photo_path, date_adhesion, numero_meditation 
            FROM membres 
            WHERE equipe_id=? AND statut=? 
            ORDER BY nom
        """, (eid, 'actif')).fetchall()
        
        for m in membres:
            id_m, matricule, nom, prenom, whatsapp, photo_path, date_adhesion, num_med = m
            
            with st.expander(f"{nom} {prenom} - {matricule}" + (f" - N° {num_med}" if num_med else "")):
                col1, col2 = st.columns([3,1])
                col1.write(f"💬 WhatsApp: {whatsapp}")
                col1.write(f"📅 Adhésion: {date_adhesion}")
                if photo_path:
                    col1.image(photo_path, width=80)
                
                with col2:
                    if st.button("✏️ Modifier", key=f"eq_btn_mod_{id_m}"):
                        if st.session_state['open_form_eq'] == f"mod_{id_m}":
                            st.session_state['open_form_eq'] = None
                        else:
                            st.session_state['open_form_eq'] = f"mod_{id_m}"
                        st.rerun()
                    if st.button("📦 Archiver", key=f"eq_btn_arch_{id_m}"):
                        if st.session_state['open_form_eq'] == f"arch_{id_m}":
                            st.session_state['open_form_eq'] = None
                        else:
                            st.session_state['open_form_eq'] = f"arch_{id_m}"
                        st.rerun()
                    if st.button("🗑️ Supprimer", key=f"eq_btn_del_{id_m}"):
                        st.session_state['delete_membre_id'] = id_m
                        st.rerun()
                
                # Formulaire de modification
                if st.session_state.get('open_form_eq') == f"mod_{id_m}":
                    st.markdown("---")
                    st.markdown("#### ✏️ Modification")
                    membre_data = c.execute("SELECT nom, prenom, whatsapp, photo_path, numero_meditation FROM membres WHERE id=?", (id_m,)).fetchone()
                    if membre_data:
                        with st.form(f"form_mod_eq_{id_m}"):
                            new_nom = st.text_input("Nom", value=membre_data[0])
                            new_prenom = st.text_input("Prénom", value=membre_data[1])
                            new_whatsapp = st.text_input("WhatsApp", value=membre_data[2])
                            new_num_med = st.text_input("N° méditation", value=membre_data[4] or "", max_chars=2)
                            new_photo = st.file_uploader("Nouvelle photo", type=['jpg','png','jpeg'])
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("❌ Annuler"):
                                    st.session_state['open_form_eq'] = None
                                    st.rerun()
                            with col2:
                                if st.form_submit_button("💾 Enregistrer"):
                                    c.execute("UPDATE membres SET nom=?, prenom=?, whatsapp=?, numero_meditation=? WHERE id=?", 
                                            (new_nom, new_prenom, new_whatsapp, new_num_med, id_m))
                                    if new_photo:
                                        if membre_data[3] and os.path.exists(membre_data[3]):
                                            os.remove(membre_data[3])
                                        chemin = sauvegarder_photo(new_photo, matricule)
                                        c.execute("UPDATE membres SET photo_path=? WHERE id=?", (chemin, id_m))
                                    commit_and_sync()
                                    st.session_state['open_form_eq'] = None
                                    st.success("Membre modifié")
                                    st.rerun()
                
                # Formulaire d'archivage
                elif st.session_state.get('open_form_eq') == f"arch_{id_m}":
                    st.markdown("---")
                    st.markdown("#### 📦 Archivage")
                    with st.form(f"form_arch_eq_{id_m}"):
                        situation = st.radio("Situation", ["Déplacé", "Radié", "Défunt"])
                        col1, col2 = st.columns(2)
                        with col1:
                            annee_debut_arch = st.number_input("Année de début (Sept)", min_value=2000, max_value=date.today().year+5, value=date.today().year, step=1)
                        with col2:
                            annee_fin_arch = st.number_input("Année de fin (Sept)", min_value=2000, max_value=date.today().year+10, value=date.today().year+1, step=1)
                        commentaire = st.text_area("Commentaire")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("❌ Annuler"):
                                st.session_state['open_form_eq'] = None
                                st.rerun()
                        with col2:
                            if st.form_submit_button("✅ Archiver"):
                                if annee_fin_arch <= annee_debut_arch:
                                    st.error("L'année de fin doit être après l'année de début.")
                                else:
                                    date_debut_arch = date(annee_debut_arch, 9, 1)
                                    date_fin_arch = date(annee_fin_arch, 9, 1)
                                    paroisse_id = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()[0]
                                    archiver_membre(id_m, situation, date_debut_arch, date_fin_arch, commentaire,
                                                    st.session_state['user_id'], st.session_state['username'], 'equipe', paroisse_id, eid)
                                    st.session_state['open_form_eq'] = None
                                    st.success("Membre archivé")
                                    st.rerun()
        
        # Gestion de la suppression
        if 'delete_membre_id' in st.session_state:
            del_id = st.session_state['delete_membre_id']
            membre_del = c.execute("SELECT nom, prenom, photo_path FROM membres WHERE id=?", (del_id,)).fetchone()
            if membre_del:
                st.warning(f"⚠️ Supprimer définitivement {membre_del[0]} {membre_del[1]} ?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Oui, supprimer"):
                        if membre_del[2]:
                            supprimer_photo(membre_del[2])
                        c.execute("DELETE FROM membres WHERE id=?", (del_id,))
                        c.execute("DELETE FROM abonnements WHERE membre_id=?", (del_id,))
                        commit_and_sync()
                        del st.session_state['delete_membre_id']
                        st.success("Membre supprimé")
                        st.rerun()
                with col2:
                    if st.button("❌ Annuler"):
                        del st.session_state['delete_membre_id']
                        st.rerun()
        
        # Export Excel
        if membres:
            st.markdown("---")
            st.markdown("### 📊 Export des données")
            df_export = pd.DataFrame([(m[1], m[2], m[3], m[7], m[4], m[6]) for m in membres], 
                                    columns=["Matricule", "Nom", "Prénom", "N° méditation", "WhatsApp", "Date adhésion"])
            output = io.BytesIO()
            try:
                with pd.ExcelWriter(output, engine=None) as writer:
                    df_export.to_excel(writer, sheet_name=f"Membres_{nom_equipe}", index=False)
                output.seek(0)
                st.download_button(
                    "📥 Exporter les membres (Excel)", 
                    data=output, 
                    file_name=f"membres_{nom_equipe}_{paroisse_nom}_{date.today()}.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"export_membres_eq_{eid}_{date.today()}"
                )
            except Exception as e:
                st.error(f"Erreur export: {e}")
    
    # Abonnements
    elif menu == "Abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 Gestion des abonnements - {nom_equipe}</h2>', unsafe_allow_html=True)
        annee_debut = st.number_input("Année de début de la période", min_value=2020,
                                       max_value=date.today().year + 1, value=date.today().year, step=1)
        st.write(f"**Période :** {periode_affichage(annee_debut)}")
        membres = c.execute("SELECT id, nom, prenom, matricule FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom",
                            (eid,)).fetchall()
        
        for m in membres:
            deja = verifier_abonnement(m[0], annee_debut)
            if deja:
                # Récupération du type et du montant actuel
                abo_info = c.execute("SELECT type_abonnement, montant FROM abonnements WHERE membre_id=? AND annee_debut=?",
                                     (m[0], annee_debut)).fetchone()
                type_ = abo_info[0] if abo_info else "abonnement"
                montant_ = abo_info[1] if abo_info else 0
                type_affiche = "Abonnement" if type_ == "abonnement" else "Réabonnement"
                
                # Affichage avec le bouton Modifier
                col_info, col_btn = st.columns([4, 1])
                with col_info:
                    st.info(f"{m[1]} {m[2]} ({m[3]}) – ✅ {type_affiche} ({montant_} FCFA)")
                with col_btn:
                    if st.button("✏️", key=f"mod_abo_{m[0]}_{annee_debut}"):
                        st.session_state['modif_abo_id'] = m[0]
                        st.rerun()
            else:
                with st.expander(f"{m[1]} {m[2]} ({m[3]}) – ❌ Non enregistré"):
                    type_abo, montant = widget_type_abonnement("eq", m[0], annee_debut)
                    if st.button("Enregistrer", key=f"btn_eq_{m[0]}_{annee_debut}"):
                        enregistrer_abonnement(m[0], annee_debut, montant, type_abo)
                        st.success(f"{type_abo} enregistré")
                        st.rerun()

        # --- Formulaire de Modification d'Abonnement ---
        if 'modif_abo_id' in st.session_state:
            mod_id = st.session_state['modif_abo_id']
            membre_info = c.execute("SELECT nom, prenom, matricule FROM membres WHERE id=?", (mod_id,)).fetchone()
            abo_info = c.execute("SELECT type_abonnement, montant FROM abonnements WHERE membre_id=? AND annee_debut=?",
                                 (mod_id, annee_debut)).fetchone()
            
            if membre_info and abo_info:
                st.markdown("---")
                st.markdown(f"### ✏️ Modifier l'abonnement de {membre_info[1]} {membre_info[0]}")
                
                with st.form(f"modif_abo_form_{mod_id}"):
                    # Pré-remplissage avec les valeurs actuelles
                    index_type = 0 if abo_info[0] == "abonnement" else 1
                    new_type = st.radio("Type", ["📝 Abonnement", "🔄 Réabonnement"],
                                        index=index_type, horizontal=True, key=f"mod_type_{mod_id}")
                    
                    # ✅ CORRECTION : On force la conversion en 'int' pour éviter l'erreur de type numérique
                    montant_actuel = int(abo_info[1]) if abo_info[1] is not None else 0
                    
                    new_montant = st.number_input("Montant (FCFA)", min_value=0, 
                                                   value=montant_actuel, step=500, key=f"mod_mont_{mod_id}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        # ✅ Bouton de soumission bien présent
                        if st.form_submit_button("💾 Mettre à jour", use_container_width=True):
                            type_str = "abonnement" if "Abonnement" in new_type else "reabonnement"
                            enregistrer_abonnement(mod_id, annee_debut, new_montant, type_str)
                            del st.session_state['modif_abo_id']
                            st.success("Abonnement modifié ✅")
                            st.rerun()
                    with col2:
                        # ✅ Bouton de soumission bien présent
                        if st.form_submit_button("🗑️ Supprimer cet abonnement", use_container_width=True):
                            c.execute("DELETE FROM abonnements WHERE membre_id=? AND annee_debut=?", (mod_id, annee_debut))
                            commit_and_sync()
                            del st.session_state['modif_abo_id']
                            st.warning("Abonnement supprimé.")
                            st.rerun()
                    with col3:
                        # ✅ Bouton de soumission bien présent
                        if st.form_submit_button("❌ Annuler", use_container_width=True):
                            del st.session_state['modif_abo_id']
                            st.rerun()

        st.markdown("---")
        tab_liste = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
        with tab_liste[0]:
            abonnes = c.execute('''SELECT m.nom, m.prenom, m.matricule, a.date_paiement, a.montant
                                   FROM membres m
                                   JOIN abonnements a ON m.id=a.membre_id
                                   WHERE m.equipe_id=? AND a.annee_debut=? AND a.type_abonnement='abonnement' AND a.statut='paye'
                                   ORDER BY m.nom''', (eid, annee_debut)).fetchall()
            if abonnes:
                data = [{"N°": i+1, "Nom": a[0], "Prénom": a[1], "Matricule": a[2], "Date paiement": a[3], "Montant": f"{a[4]} FCFA"} for i, a in enumerate(abonnes)]
                df = pd.DataFrame(data)
                df.index = df.index + 1
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Aucun abonné pour cette période.")
        with tab_liste[1]:
            reabonnes = c.execute('''SELECT m.nom, m.prenom, m.matricule, a.date_paiement, a.montant
                                     FROM membres m
                                     JOIN abonnements a ON m.id=a.membre_id
                                     WHERE m.equipe_id=? AND a.annee_debut=? AND a.type_abonnement='reabonnement' AND a.statut='paye'
                                     ORDER BY m.nom''', (eid, annee_debut)).fetchall()
            if reabonnes:
                data = [{"N°": i+1, "Nom": r[0], "Prénom": r[1], "Matricule": r[2], "Date paiement": r[3], "Montant": f"{r[4]} FCFA"} for i, r in enumerate(reabonnes)]
                df = pd.DataFrame(data)
                df.index = df.index + 1
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Aucun réabonné pour cette période.")
        with tab_liste[2]:
            non_inscrits = c.execute('''SELECT m.nom, m.prenom, m.matricule
                                        FROM membres m
                                        WHERE m.equipe_id=? AND m.statut='actif' AND m.id NOT IN (
                                            SELECT a.membre_id FROM abonnements a WHERE a.annee_debut=? AND a.statut='paye'
                                        ) ORDER BY m.nom''', (eid, annee_debut)).fetchall()
            if non_inscrits:
                data = [{"N°": i+1, "Nom": n[0], "Prénom": n[1], "Matricule": n[2]} for i, n in enumerate(non_inscrits)]
                df = pd.DataFrame(data)
                df.index = df.index + 1
                st.dataframe(df, use_container_width=True)
            else:
                st.success("🎉 Tous les membres sont à jour !")

    # Suivi des présences et Agenda
    elif menu == "📌 Suivi":
        st.markdown(f'<h2 style="color:#1A237E;">📌 Suivi et Agenda - {nom_equipe}</h2>', unsafe_allow_html=True)
        
        # Les deux onglets demandés
        tab_avenir, tab_passe = st.tabs(["📅 Agenda - A venir", "📝 Séances réalisées"])
        
        # ==========================================
        # ONGLET 1 : AGENDA - A VENIR
        # ==========================================
        with tab_avenir:
            # 1. Formulaire d'ajout
            ajouter_evenement_agenda(equipe_id=eid, auteur_nom=st.session_state['username'])
            st.markdown("---")
            # 2. Vue globale (Équipe + Paroisse parente + Diocèse)
            afficher_agenda_complet_universel(equipe_id=eid)

        # ==========================================
        # ONGLET 2 : SÉANCES RÉALISÉES
        # ==========================================
        with tab_passe:
            types_evenements = ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage"]
            membres_actifs = c.execute("SELECT id, nom, prenom FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eid,)).fetchall()
            
            if not membres_actifs:
                st.warning("Aucun membre actif dans l'équipe pour le moment.")
            else:
                with st.expander("📝 Enregistrer / Modifier une séance", expanded=False):
                    col_sel1, col_sel2, col_sel3 = st.columns(3)
                    with col_sel1:
                        date_event = st.date_input("📅 Date de l'événement", value=date.today(), key="date_suivi_eq")
                    with col_sel2:
                        type_event = st.selectbox("⛪ Type d'événement", types_evenements, key="type_suivi_eq")
                    with col_sel3:
                        lieu_event = st.text_input("📍 Lieu de la rencontre", key="lieu_suivi_eq")
                    
                    event = c.execute("SELECT id, lieu FROM evenements WHERE equipe_id=? AND date_evenement=? AND type_evenement=?", 
                                      (eid, date_event, type_event)).fetchone()
                    event_id = None
                    if event:
                        event_id = event[0]
                        if not lieu_event and event[1]:
                            st.info(f"📍 Lieu enregistré précédemment : {event[1]}")
                    
                    with st.form("form_suivi_presences"):
                        st.markdown(f"**Statut des membres pour le {date_event.strftime('%d/%m/%Y')} ({type_event}) :**")
                        statuts = {}
                        for m in membres_actifs:
                            if event_id:
                                existing = c.execute('''SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=?''', (m[0], event_id)).fetchone()
                                default_statut = existing[0] if existing else "absent"
                            else:
                                default_statut = "absent"
                            statuts[m[0]] = st.radio(
                                f"{m[1]} {m[2]}", 
                                ["present", "excuse", "absent"], 
                                format_func=lambda x: {"present": "✅ Présent", "excuse": "⚠️ Excusé", "absent": "❌ Absent"}[x],
                                index=["present", "excuse", "absent"].index(default_statut),
                                key=f"radio_{m[0]}_{date_event}_{type_event}",
                                horizontal=True
                            )
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            submitted = st.form_submit_button("💾 Enregistrer les présences", use_container_width=True)
                        with col_btn2:
                            clear = st.form_submit_button("🗑️ Effacer cette séance", use_container_width=True)
                        
                        if submitted:
                            if event_id:
                                c.execute("UPDATE evenements SET lieu=? WHERE id=?", (lieu_event, event_id))
                            else:
                                c.execute("INSERT INTO evenements (equipe_id, type_evenement, date_evenement, lieu) VALUES (?, ?, ?, ?)", (eid, type_event, date_event, lieu_event))
                                event_id = c.lastrowid
                            c.execute("DELETE FROM suivi_presences WHERE evenement_id=?", (event_id,))
                            for m_id, statut in statuts.items():
                                c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (m_id, event_id, statut))
                            commit_and_sync()
                            st.success("Présences enregistrées avec succès ! ✅")
                            st.rerun()

                        if clear:
                            if event_id:
                                c.execute("DELETE FROM suivi_presences WHERE evenement_id=?", (event_id,))
                                c.execute("DELETE FROM evenements WHERE id=?", (event_id,))
                                commit_and_sync()
                                st.warning("Séance effacée.")
                                st.rerun()

            st.markdown("---")
            st.subheader("📊 Historique et Statistiques")
            filtre_type = st.selectbox("Filtrer par type d'événement", ["Tous"] + ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage"], key="filtre_hist_eq")
            afficher_historique_suivi(eid, filtre_type) 
        
    # WhatsApp
    elif menu == "WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Communications WhatsApp - {nom_equipe}</h2>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🎂 Anniversaires", "📢 Rappels réabonnement"])
        with tab1:
            afficher_anniversaires_whatsapp()
        with tab2:
            annee_rappel = st.number_input("Année de début", min_value=2020, max_value=date.today().year+1, value=date.today().year, step=1, key="rappel_equipe")
            afficher_rappels_reabonnement_whatsapp(annee_rappel, equipe_id=eid)
    
    # Archives
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
                            c.execute("UPDATE membres SET statut='archive' WHERE id=?", (membre_choisi[0],))
                            paroisse_id = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()[0]
                            c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id)
                                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                      (membre_choisi[0], situation, date_debut_obj, date_fin_obj, commentaire,
                                       st.session_state['user_id'], st.session_state['username'], 'equipe', paroisse_id, eid))
                            commit_and_sync()
                            st.success(f"✅ {membre_choisi[1]} {membre_choisi[2]} archivé.")
                            st.rerun()
        
        if archives_equipe:
            st.subheader("✏️ Gérer les archives de votre équipe")
            for arch in archives_equipe:
                arch_id, nom, prenom, matricule, situation, date_debut_raw, date_fin_raw, commentaire, membre_id = arch
                try:
                    if isinstance(date_debut_raw, str):
                        date_debut = date.fromisoformat(date_debut_raw)
                    else:
                        date_debut = date_debut_raw
                    if isinstance(date_fin_raw, str):
                        date_fin = date.fromisoformat(date_fin_raw)
                    else:
                        date_fin = date_fin_raw
                except:
                    date_debut = None
                    date_fin = None
                if date_debut and date_fin:
                    duree = (date_fin - date_debut).days // 365
                    annee_debut_aff = date_debut.year
                    annee_fin_aff = date_fin.year
                else:
                    duree = 0
                    annee_debut_aff = "?"
                    annee_fin_aff = "?"
                situation_affichee = afficher_situation(situation)
                with st.expander(f"{nom} {prenom} ({matricule}) – {situation_affichee} – {duree} an(s) - Sept {annee_debut_aff} – Sept {annee_fin_aff}"):
                    with st.form(f"edit_arch_{arch_id}"):
                        new_situation = st.selectbox("Situation", ["Déplacé", "Radié", "Défunt"],
                                                     index=["Déplacé","Radié","Défunt"].index(situation) if situation in ["Déplacé","Radié","Défunt"] else 0)
                        col1, col2 = st.columns(2)
                        with col1:
                            new_annee_debut = st.number_input("Année début (Sept)", min_value=2000, max_value=date.today().year+5,
                                                               value=date_debut.year if date_debut else date.today().year, step=1)
                        with col2:
                            new_annee_fin = st.number_input("Année fin (Sept)", min_value=2000, max_value=date.today().year+10,
                                                            value=date_fin.year if date_fin else date.today().year+1, step=1)
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
                                    commit_and_sync()
                                    st.success("Archive modifiée")
                                    st.rerun()
                        with col2:
                            if situation in ("Déplacé", "Radié"):
                                if st.form_submit_button("🔄 Réintégrer (devient actif)"):
                                    c.execute("UPDATE membres SET statut='actif' WHERE id=?", (membre_id,))
                                    c.execute("DELETE FROM archives WHERE id=?", (arch_id,))
                                    commit_and_sync()
                                    st.success(f"{nom} {prenom} a été réintégré(e).")
                                    st.rerun()
                            else:
                                st.info("Un défunt ne peut pas être réintégré.")
        else:
            st.info("Aucune archive pour cette équipe.")
            
