# ====================================================================
# views/view_communication.py — VERSION 2.0 (soumission pure)
# La cellule prépare et SOUMET ; le diocèse valide au SAS et publie.
# 6 onglets : 🙏 Prière/Méditation · 📺 Bandes défilantes · 🖼️ Affiches & B-A
# (publication simple : actualités) · 🕯️ Thème pastoral · 🎵 Musique · 📔 Journal
# Les évènements avec Réponse de Communion relèvent EXCLUSIVEMENT de l'agenda
# (canal des responsables d'équipe) — jamais de ce canal.
# Marqueurs : Ctrl+F → "VERSION 2.0", "_onglet_actualites".
# ====================================================================
import streamlit as st
import html
from datetime import date
from database import c, commit_and_sync
from services import (sauvegarder_illustration, sauvegarder_audio, sauvegarder_video,
                      envoyer_notification_telegram, get_periode_pastorale)


def _liste_paroisses():
    """Liste des paroisses pour le choix de cible (id, nom)."""
    return c.execute("SELECT id, nom FROM paroisses ORDER BY nom").fetchall()


def _assurer_table():
    """Crée la table des soumissions si absente (idempotent, sans risque)."""
    c.execute("""CREATE TABLE IF NOT EXISTS soumissions_comm (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auteur_id INTEGER, type_contenu TEXT, titre TEXT,
                    contenu_texte TEXT, image_url TEXT, fichier_url TEXT,
                    video_url TEXT, date_evenement TEXT, lieu TEXT,
                    statut TEXT DEFAULT 'attente', motif_refus TEXT,
                    date_soumission TEXT, paroisse_cible INTEGER)""")
    try:
        c.execute("SELECT paroisse_cible FROM soumissions_comm LIMIT 1")
    except Exception:
        try:
            c.execute("ALTER TABLE soumissions_comm ADD COLUMN paroisse_cible INTEGER")
        except Exception:
            pass
    commit_and_sync()


LIBELLES = {"priere": "🙏 Prière", "meditation": "📖 Méditation",
            "audio": "🎵 Musique", "annonce_defilante": "📺 Bande défilante",
            "actualite": "📰 Actualité (affiche/BA)",
            "theme_pastoral": "🕯️ Thème pastoral",
            "evenement": "📅 Évènement (historique)"}

STATUTS = {"attente": "🟡 En attente de validation du diocèse",
           "publie": "✅ Publiée par le diocèse",
           "refuse": "❌ Refusée par le diocèse"}


def _soumettre(d):
    """RÈGLE MÉTIER DÉFINITIVE : la cellule ne publie JAMAIS d'elle-même.
    L'accord du diocèse est obligatoire (sas de validation)."""
    c.execute("""INSERT INTO soumissions_comm
                 (auteur_id, type_contenu, titre, contenu_texte, image_url,
                  fichier_url, video_url, date_evenement, lieu, statut,
                  date_soumission, paroisse_cible)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'attente', ?, ?)""",
              (st.session_state.get('user_id'), d.get("type_contenu"),
               d.get("titre"), d.get("contenu_texte"), d.get("image_url"),
               d.get("fichier_url"), d.get("video_url"),
               d.get("date_evenement"), d.get("lieu"),
               date.today().isoformat(), d.get("paroisse_cible")))
    commit_and_sync()
    try:
        envoyer_notification_telegram(
            "📡 <b>Service Communication</b> — nouvelle soumission À VALIDER : "
            + html.escape(d.get("titre") or "(sans titre)"))
    except Exception:
        pass
    st.success("📨 Soumission transmise au diocèse. Rien ne sera publié sans sa validation.")


def _choisir_cible():
    """Selectbox commun « 🎯 Cible de publication » → id paroisse ou None."""
    _paroisses = _liste_paroisses()
    _opts = ["🌍 Diocèse (tous)"] + [f"🏘️ Paroisse : {p[1]}" for p in _paroisses]
    _cible_lbl = st.selectbox("🎯 Cible de publication", _opts)
    _cible = None if _cible_lbl.startswith("🌍") else _paroisses[[i for i, o in enumerate(_opts) if o == _cible_lbl][0] - 1][0]
    return _cible


def _bandeau():
    st.markdown('<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
                ' padding:18px; border-radius:15px; text-align:center; margin-bottom:15px;">'
                '<div style="color:#FFD700; font-size:1.15rem; font-weight:bold;">'
                '📡 Service Communication — Diocèse de Grand-Bassam</div>'
                '<div style="color:#e8eaf6; font-size:0.85rem; margin-top:4px;">'
                'Je prépare, le diocèse publie — chaque contenu passe par sa validation</div></div>',
                unsafe_allow_html=True)


# ---------------- 🙏 PRIÈRE / MÉDITATION ----------------
def _onglet_priere_meditation():
    with st.form("form_pm", clear_on_submit=False):
        type_pm = st.selectbox("Type de contenu", ["Prière", "Méditation"])
        titre = st.text_input("Titre")
        contenu = st.text_area("Contenu du texte")
        img = st.file_uploader("Illustration (photo — facultatif, hébergement diocèse)",
                               type=["jpg", "jpeg", "png", "webp"])
        img_lien = st.text_input("…ou lien d'image (https://... — ex. imgbb : i.ibb.co/…)")
        pdf_url = st.text_input("Lien PDF (facultatif — https://...)")
        _cible = _choisir_cible()
        if st.form_submit_button("📨 Soumettre au diocèse", type="primary"):
            if not titre.strip() or not contenu.strip():
                st.error("Le titre et le contenu sont obligatoires.")
            elif img_lien.strip() and not img_lien.strip().startswith("http"):
                st.error("Le lien d'image doit commencer par https://")
            elif pdf_url.strip() and not pdf_url.strip().startswith("http"):
                st.error("Le lien PDF doit commencer par https://")
            else:
                if img_lien.strip():
                    img_url = img_lien.strip()
                else:
                    img_url = sauvegarder_illustration(img) if img else None
                    if img and not img_url:
                        st.warning("⚠️ L'envoi du fichier a échoué (service d'hébergement momentanément indisponible). "
                                   "La soumission partira SANS image ; utilisez un lien imgbb pour en inclure une.")
                _soumettre({
                    "type_contenu": "priere" if type_pm == "Prière" else "meditation",
                    "titre": titre.strip(), "contenu_texte": contenu.strip(),
                    "image_url": img_url, "fichier_url": pdf_url.strip() or None,
                    "paroisse_cible": _cible})


# ---------------- 📺 BANDES DÉFILANTES ----------------
def _onglet_bandes():
    with st.form("form_bd", clear_on_submit=False):
        st.caption("📻 Après validation, la bande défilera dans l'entête des espaces (3 dernières actives).")
        texte_bd = st.text_area("Texte de l'annonce défilante (court et percutant)", max_chars=250)
        _portee = st.selectbox("Portée", ["🌍 Public (tous)", "👤 Membres uniquement"])
        _cible = _choisir_cible()
        if st.form_submit_button("📨 Soumettre au diocèse", type="primary"):
            if not texte_bd.strip():
                st.error("Le texte est obligatoire.")
            else:
                _soumettre({"type_contenu": "annonce_defilante",
                            "titre": "Bande défilante",
                            "contenu_texte": texte_bd.strip(),
                            "fichier_url": ("membre" if _portee.startswith("👤") else "defaut"),
                            "paroisse_cible": _cible})


# ---------------- 🖼️ AFFICHES & BANDES-ANNONCES (publication simple) ----------------
def _onglet_actualites():
    st.caption("📰 Préparez une actualité pour informer la communauté : jubilé, ordination, grande fête de paroisse… "
               "Après validation, elle rejoindra la zone « 📰 Actualités » de l'Espace de Prière. "
               "ℹ️ Si l'évènement nécessite une Réponse de Communion, il relève de l'agenda du responsable d'équipe — pas de ce canal.")
    with st.form("form_act_soum", clear_on_submit=False):
        titre_a = st.text_input("Titre (ex. : 25 ans de sacerdoce du Père X)")
        texte_a = st.text_area("Texte / informations", height=120)
        affiche_a = st.file_uploader("Affiche (photo — facultatif, hébergement diocèse)",
                                     type=["jpg", "jpeg", "png", "webp"])
        img_a_lien = st.text_input("…ou lien d'affiche (https://... — ex. imgbb : i.ibb.co/…)")
        lien_v = st.text_input("Bande-annonce — lien vidéo (https://..., facultatif)")
        fichier_v = st.file_uploader("…ou fichier vidéo (MP4 — facultatif, max ~150 Mo)", type=["mp4", "mov"])
        c1, c2 = st.columns(2)
        with c1:
            date_a = st.date_input("Date de l'évènement (facultative)", value=None)
        with c2:
            lieu_a = st.text_input("Lieu (facultatif)")
        _cible = _choisir_cible()
        if st.form_submit_button("📨 Soumettre au diocèse", type="primary"):
            if not titre_a.strip():
                st.error("Le titre est obligatoire.")
            elif not affiche_a and not img_a_lien.strip() and not lien_v.strip() and not fichier_v:
                st.error("Chargez une affiche (fichier ou lien) OU une vidéo (au moins un visuel).")
            elif img_a_lien.strip() and not img_a_lien.strip().startswith("http"):
                st.error("Le lien d'image doit commencer par https://")
            elif lien_v.strip() and not lien_v.strip().startswith("http"):
                st.error("Le lien vidéo doit commencer par https://")
            else:
                _vid = lien_v.strip() or (sauvegarder_video(fichier_v) if fichier_v else None)
                if fichier_v and not _vid:
                    st.error("L'envoi du fichier vidéo a échoué. Réessayez ou utilisez un lien.")
                else:
                    _img = img_a_lien.strip() if img_a_lien.strip() else (sauvegarder_illustration(affiche_a) if affiche_a else None)
                    _soumettre({"type_contenu": "actualite",
                                "titre": titre_a.strip(),
                                "contenu_texte": texte_a.strip() or None,
                                "image_url": _img, "video_url": _vid,
                                "date_evenement": date_a.isoformat() if date_a else None,
                                "lieu": lieu_a.strip() or None,
                                "paroisse_cible": _cible})


# ---------------- 🕯️ THÈME PASTORAL ----------------
def _onglet_theme():
    st.caption("🕯️ Préparez le thème pastoral de l'année (texte + mystère porteur + affiche facultative). Après validation, le diocèse "
               "l'activera : il s'affichera dans l'Espace de Prière (🕯️ Thème → Vue d'ensemble). "
               "Les sous-thèmes mensuels restent gérés directement par le diocèse (SAS).")
    with st.form("form_theme_soum", clear_on_submit=False):
        annee_t = st.number_input("Année de début de la période pastorale", 2020, 2060,
                                  get_periode_pastorale()[0], step=1)
        texte_t = st.text_area("Texte du thème", placeholder="Ex. : IL POSAIT DES QUESTIONS. FORCE DE LA FOI !")
        myst_t = st.number_input("Mystère porteur (1-20)", 1, 20, 5, step=1)
        affiche_t = st.file_uploader("Affiche du thème (photo — facultatif, hébergement diocèse)",
                                     type=["jpg", "jpeg", "png", "webp"])
        affiche_t_lien = st.text_input("…ou lien d'affiche (https://... — ex. imgbb : i.ibb.co/…)")
        if st.form_submit_button("📨 Soumettre le thème au diocèse", type="primary"):
            if not texte_t.strip():
                st.error("Le texte du thème est obligatoire.")
            elif affiche_t_lien.strip() and not affiche_t_lien.strip().startswith("http"):
                st.error("Le lien d'image doit commencer par https://")
            else:
                if affiche_t_lien.strip():
                    img_url = affiche_t_lien.strip()
                else:
                    img_url = sauvegarder_illustration(affiche_t) if affiche_t else None
                _soumettre({"type_contenu": "theme_pastoral",
                            "titre": f"Thème {int(annee_t)} - {int(annee_t) + 1}",
                            "contenu_texte": texte_t.strip(),
                            "image_url": img_url,
                            # Convention : date_evenement = année, lieu = mystère porteur
                            "date_evenement": str(int(annee_t)),
                            "lieu": str(int(myst_t))})


# ---------------- 🎵 MUSIQUE ----------------
def _onglet_musique():
    st.caption("🎵 Deux façons de soumettre un morceau : fichier MP3 (hébergement diocèse) OU lien "
               "(MP3 direct https://… ou vidéo YouTube https://youtu.be/…). Le lien est recommandé : "
               "aucune limite d'usage. Rappel YouTube : vidéo « non répertoriée ».")
    with st.form("form_mu", clear_on_submit=False):
        titre_mu = st.text_input("Titre du morceau")
        audio = st.file_uploader("Fichier audio (MP3 — facultatif si un lien est fourni)",
                                 type=["mp3", "wav", "m4a"])
        lien_mu = st.text_input("…ou lien audio / YouTube (https://...)")
        _cible = _choisir_cible()
        if st.form_submit_button("📨 Soumettre au diocèse", type="primary"):
            _url = None
            if not titre_mu.strip():
                st.error("Le titre est obligatoire.")
            elif audio is None and not lien_mu.strip():
                st.error("Chargez un fichier audio OU collez un lien (au moins un des deux).")
            elif lien_mu.strip() and not lien_mu.strip().startswith("http"):
                st.error("Le lien doit commencer par https://")
            else:
                if lien_mu.strip():
                    _url = lien_mu.strip()
                else:
                    _url = sauvegarder_audio(audio)
                    if not _url:
                        st.error("L'envoi du fichier a échoué (service d'hébergement momentanément indisponible). "
                                 "Collez un lien audio ou YouTube à la place.")
                if _url:
                    _soumettre({"type_contenu": "audio", "titre": titre_mu.strip(),
                                "fichier_url": _url, "paroisse_cible": _cible})


# ---------------- 📔 JOURNAL ----------------
def _onglet_journal():
    _paroisses_map = {p[0]: p[1] for p in c.execute("SELECT id, nom FROM paroisses").fetchall()}
    lignes = c.execute("""SELECT id, type_contenu, titre, statut, motif_refus,
                                 date_soumission, paroisse_cible FROM soumissions_comm
                          ORDER BY id DESC LIMIT 30""").fetchall()
    if not lignes:
        st.info("Aucune soumission pour le moment.")
    for s in lignes:
        libelle = LIBELLES.get(s[1], s[1])
        _cible_lbl = f" 🏘️ {_paroisses_map[s[6]]}" if s[6] and s[6] in _paroisses_map else ""
        entete = f"{libelle} — {s[2] or '(sans titre)'} ({s[5]}){_cible_lbl}"
        with st.expander(entete):
            st.write(STATUTS.get(s[3], s[3]))
            if s[3] == "refuse" and s[4]:
                st.error("Motif du refus : " + s[4])


# ====================================================================
# PAGE PRINCIPALE
# ====================================================================
def show_communication():
    _assurer_table()
    _bandeau()
    st.caption("📡 Tout contenu de ce canal est SOUMIS puis validé par le responsable diocésain avant publication. "
               "Les évènements avec Réponse de Communion passent exclusivement par l'agenda (canal des responsables d'équipe).")
    onglets = st.tabs(["🙏 Prière / Méditation", "📺 Bandes défilantes", "🖼️ Affiches & Bandes-annonces",
                       "🕯️ Thème pastoral", "🎵 Musique", "📔 Journal des publications"])
    with onglets[0]:
        _onglet_priere_meditation()
    with onglets[1]:
        _onglet_bandes()
    with onglets[2]:
        _onglet_actualites()
    with onglets[3]:
        _onglet_theme()
    with onglets[4]:
        _onglet_musique()
    with onglets[5]:
        _onglet_journal()
