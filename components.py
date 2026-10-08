import streamlit as st
import pandas as pd
import io
import html
import urllib.parse
from datetime import date, timedelta
from database import c, commit_and_sync
import qrcode
from io import BytesIO
from services import (safe_date, envoyer_notification_telegram, lien_whatsapp,
                      verifier_abonnement, periode_affichage, get_periode_pastorale,
                      est_cloture, cloturer_periode, TYPES_EVENEMENTS,
                      URL_ESPACE_SPIRITUEL, sauvegarder_illustration, supprimer_photo,
                      sauvegarder_video, sauvegarder_pdf)
from mysteres import get_theme_actif, get_sous_theme_du_mois, get_lien_mystere


def widget_type_abonnement(prefix, m_id, annee):
    type_abo = st.radio("Type", ["📝 Abonnement", "🔄 Réabonnement"], key=f"type_{prefix}_{m_id}_{annee}", horizontal=True)
    montant = st.number_input("Montant (FCFA)", min_value=0, value=5000, step=500, key=f"mont_{prefix}_{m_id}_{annee}")
    return ("abonnement" if "Abonnement" in type_abo else "reabonnement"), montant

def _qrcode_st(url, taille_px=260):
    """Génère et affiche un QR code scannable (image locale, aucun service tiers)."""
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    st.image(buffer.getvalue(), width=taille_px)


def _qrcode_png_bytes(url):
    """Retourne les octets PNG d'un QR code (pour téléchargement sur affiche)."""
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def gerer_qr_paroissiaux():
    """🔳 QR paroissiaux (diocèse) : chaque paroisse reçoit un QR SIGNÉ vers
    l'Espace communautaire (?espace=1&p=ID). L'app enregistre l'ORIGINE
    paroissiale de chaque visite — fidèle anonyme, aucune donnée personnelle
    (conforme aux mentions légales)."""
    st.markdown('<h3 style="color:#1A237E;">🔳 QR paroissiaux (traçabilité missionnaire)</h3>', unsafe_allow_html=True)
    st.caption("Chaque QR mène au même Espace communautaire, mais SIGNÉ : l'app sait "
               "quelle paroisse a émis l'affiche et compte les visites d'origine. "
               "Imprimez le QR de chaque paroisse sur SES affiches, missions et annonces.")

    paroisses = c.execute("SELECT id, nom, commune, ville FROM paroisses ORDER BY nom").fetchall()
    if not paroisses:
        st.info("Aucune paroisse enregistrée.")
        return

    options = [f"{p[1]} ({p[2] or '—'} – {p[3] or '—'})" for p in paroisses]
    if st.session_state.get("qr_par_sel") not in options:
        st.session_state.pop("qr_par_sel", None)
    choix = st.selectbox("Paroisse", options, key="qr_par_sel")
    p = paroisses[options.index(choix)]

    url_signee = f"{URL_ESPACE_SPIRITUEL}/?espace=1&p={p[0]}"
    st.code(url_signee)

    c_qr, c_info = st.columns([1, 2])
    with c_qr:
        png = _qrcode_png_bytes(url_signee)
        st.image(png, width=220)
    with c_info:
        st.download_button("📥 Télécharger le QR (PNG pour affiche)", data=png,
                           file_name=f"qr_paroisse_{p[0]}.png", key=f"qr_dl_{p[0]}",
                           width="stretch")
        message = (f"Frères et sœurs, voici l'Espace de Prière et Méditation "
                   f"de la paroisse {p[1]} (Diocèse de Grand-Bassam) :\n{url_signee}\n\n"
                   f"Bon temps de ressourcement ! 🙏")
        wa = f"https://wa.me/?text={urllib.parse.quote(message, safe=':/?=')}"
        st.markdown(f'<a href="{wa}" target="_blank" class="whatsapp-link">📱 Partager sur WhatsApp</a>', unsafe_allow_html=True)
        st.caption("💡 Ce QR se décline sur toutes les affiches de la paroisse. Les visites "
                   "scannées apparaissent dans les statistiques diocésaines (origine "
                   "paroissiale, fidèles anonymes).")


def afficher_stats_qr_paroissiaux():
    """📈 Visites par origine paroissiale (QR signés — 30 derniers jours)."""
    st.markdown("### 📈 Visites par origine paroissiale (30 jours)")
    try:
        lignes = c.execute("""SELECT pa.nom, COUNT(*) FROM visites_paroisse vp
                              JOIN paroisses pa ON vp.paroisse_id = pa.id
                              WHERE vp.date_visite >= ?
                              GROUP BY vp.paroisse_id ORDER BY COUNT(*) DESC""",
                           ((date.today() - timedelta(days=30)).isoformat(),)).fetchall()
    except Exception:
        st.caption("Aucune visite signée enregistrée pour l'instant.")
        return
    if not lignes:
        st.caption("Aucune visite signée enregistrée pour l'instant.")
        return
    total = sum(l[1] for l in lignes)
    st.write(f"**{total} visite(s) signée(s)** ces 30 derniers jours :")
    for nom, nb in lignes:
        st.write(f"• **{nom}** : {nb}")
    st.bar_chart(pd.DataFrame(lignes, columns=["Paroisse", "Visites"]).set_index("Paroisse"))

def ajouter_evenement_agenda(equipe_id=None, paroisse_id=None, diocese_id=None, auteur_nom="Système"):
    st.markdown('<h3 style="color:#1A237E;">📅 Vos évènements à venir</h3>', unsafe_allow_html=True)
    prefix = f"ag_{equipe_id}_{paroisse_id}_{diocese_id}"

    # Nettoyage DIFFÉRÉ (un del immédiat sur un widget instancié dans le même
    # run lèverait une StreamlitAPIException)
    cles_nettoyage = st.session_state.pop("nettoyage_agenda", None)
    if cles_nettoyage:
        for cle in cles_nettoyage:
            st.session_state.pop(cle, None)

    with st.expander("➕ Ajouter / Enregistrer un évènement à l'agenda"):
        with st.form(f"ajout_agenda_{prefix}"):
            c1, c2 = st.columns(2)
            with c1:
                date_ag = st.date_input("📅 Date", value=date.today() + timedelta(days=7), key=f"d_ag_{prefix}")
            with c2:
                type_ag = st.selectbox("⛪ Type", TYPES_EVENEMENTS, key=f"t_ag_{prefix}")

            lieu_ag = st.text_input("📍 Lieu", key=f"l_ag_{prefix}")
            desc_ag = st.text_area("📝 Description", key=f"desc_ag_{prefix}")
            affiche = st.file_uploader("🖼️ Affiche de l'évènement (optionnel — visible dans l'Espace de Prière)",
                                       type=["jpg", "jpeg", "png", "webp"], key=f"affiche_{prefix}")
            # v7.6.3 — COHABITATION : saisie d'un LIEN d'affiche (imgbb…) en
            # complément de l'upload. Le lien, s'il est fourni, est prioritaire.
            lien_affiche_ag = st.text_input("🔗 …ou collez un LIEN d'affiche (imgbb, etc.)",
                                            key=f"lien_aff_{prefix}",
                                            placeholder="https://i.ibb.co/...")

            equipes_invitees_ids = []
            faire_suivre_check = False

            if paroisse_id and not equipe_id and not diocese_id:
                st.markdown("**👥 Sélectionnez les équipes concernées :**")
                equipes_paroisse = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (paroisse_id,)).fetchall()
                if equipes_paroisse:
                    options_equipes = ["🤝 Toutes les équipes"] + [e[1] for e in equipes_paroisse]
                    eq_dict = {"🤝 Toutes les équipes": "ALL", **{e[1]: e[0] for e in equipes_paroisse}}
                    cle_selection = f"sel_eq_par_{prefix}"
                    if type_ag == "Prière commune" and cle_selection not in st.session_state:
                        st.session_state[cle_selection] = ["🤝 Toutes les équipes"]
                    equipes_selectionnees = st.multiselect("Équipes", options_equipes, key=cle_selection)
                    if "🤝 Toutes les équipes" in equipes_selectionnees:
                        equipes_invitees_ids = [e[0] for e in equipes_paroisse]
                    else:
                        equipes_invitees_ids = [eq_dict[nom] for nom in equipes_selectionnees]
                else:
                    st.warning("Aucune équipe créée dans cette paroisse.")

            elif equipe_id and not paroisse_id and not diocese_id:
                eq_info = c.execute("SELECT nom_equipe, paroisse_id FROM equipes WHERE id=?", (equipe_id,)).fetchone()
                if eq_info:
                    autres_equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? AND id != ?", (eq_info[1], equipe_id)).fetchall()
                    if autres_equipes:
                        st.markdown("**🔗 Co-organiser avec une autre équipe ? (Optionnel)**")
                        eq_dict_autres = {f"{e[1]}": e[0] for e in autres_equipes}
                        eq_conjointe = st.multiselect("Autre équipe", list(eq_dict_autres.keys()), key=f"sel_eq_conj_{prefix}")
                        equipes_invitees_ids = [eq_dict_autres[nom] for nom in eq_conjointe]
                    faire_suivre_check = st.checkbox("📤 Demander à la Paroisse de faire suivre au Diocèse", value=False, key=f"faire_suivre_{prefix}")

            if st.form_submit_button("📅 Enregistrer", width="stretch"):
                # COHABITATION : lien imgbb prioritaire, sinon upload Cloudinary
                url_affiche = None
                _lien = (lien_affiche_ag or "").strip()
                if _lien:
                    if _lien.startswith("http"):
                        url_affiche = _lien
                    else:
                        st.session_state["flash_warning"] = "Lien d'affiche ignoré : il doit commencer par https://"
                if not url_affiche and affiche:
                    url_affiche = sauvegarder_illustration(affiche)

                c.execute('''INSERT INTO evenements (equipe_id, paroisse_id, diocese_id, date_evenement, type_evenement, lieu, auteur_nom, affiche_url)
                             VALUES (?,?,?,?,?,?,?,?)''',
                          (equipe_id, paroisse_id, diocese_id, date_ag.isoformat(), type_ag, lieu_ag, auteur_nom, url_affiche))
                new_event_id = c.lastrowid

                if equipe_id:
                    c.execute("INSERT OR IGNORE INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (new_event_id, equipe_id))
                for eid_inv in equipes_invitees_ids:
                    c.execute("INSERT OR IGNORE INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (new_event_id, eid_inv))

                faire_suivre = 1 if (equipe_id and not paroisse_id and faire_suivre_check) else 0
                c.execute('''INSERT INTO agenda (equipe_id, paroisse_id, diocese_id, date_event, type_event, lieu, description, auteur_nom, a_faire_suivre, evenement_id)
                             VALUES (?,?,?,?,?,?,?,?,?,?)''',
                          (equipe_id, paroisse_id, diocese_id, date_ag.isoformat(), type_ag, lieu_ag, desc_ag, auteur_nom, faire_suivre, new_event_id))
                commit_and_sync()

                source = "Diocèse"
                if equipe_id:
                    eq_res = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (equipe_id,)).fetchone()
                    source = eq_res[0] if eq_res and eq_res[0] else "Équipe"
                elif paroisse_id:
                    par_res = c.execute('SELECT nom FROM paroisses WHERE id=?', (paroisse_id,)).fetchone()
                    source = f"Paroisse {par_res[0]}" if par_res and par_res[0] else "Paroisse"

                nb_invites = f" ({len(equipes_invitees_ids)} équipe(s) invitée(s))" if equipes_invitees_ids else ""
                envoyer_notification_telegram(
                    f"📅 <b>Nouvel évènement !</b>\n🏢 {html.escape(source)}{nb_invites}\n⛪ {html.escape(type_ag)}\n"
                    f"🗓 {date_ag.strftime('%d/%m/%Y')}\n📍 {html.escape(lieu_ag or '')}\n👤 {html.escape(auteur_nom)}")

                st.session_state["nettoyage_agenda"] = [f"l_ag_{prefix}", f"desc_ag_{prefix}", f"affiche_{prefix}", f"lien_aff_{prefix}"]
                st.session_state["flash_success"] = f"Évènement enregistré ! {nb_invites} ✅"
                st.rerun()

    _gerer_affiches_evenements(equipe_id, paroisse_id, diocese_id)


def _gerer_affiches_evenements(equipe_id, paroisse_id, diocese_id):
    """Interface équipe/paroisse pour les affiches des évènements DÉJÀ créés.
    Aucun échec d'upload n'est silencieux."""
    with st.expander("🖼️ Affiches des évènements à venir (Coin Affiche)"):
        cle = f"aff_{equipe_id}_{paroisse_id}_{diocese_id}"
        if equipe_id:
            evts = c.execute('''SELECT DISTINCT e.id, e.date_evenement, e.type_evenement, e.lieu, e.affiche_url
                                FROM evenements e JOIN evenement_equipes ee ON e.id=ee.evenement_id
                                WHERE ee.equipe_id=? AND e.date_evenement >= ? ORDER BY e.date_evenement ASC''',
                             (equipe_id, date.today().isoformat())).fetchall()
        elif paroisse_id:
            evts = c.execute('''SELECT DISTINCT e.id, e.date_evenement, e.type_evenement, e.lieu, e.affiche_url
                                FROM evenements e LEFT JOIN evenement_equipes ee ON e.id=ee.evenement_id
                                LEFT JOIN equipes eq ON ee.equipe_id=eq.id
                                WHERE (e.paroisse_id=? OR eq.paroisse_id=?) AND e.date_evenement >= ? ORDER BY e.date_evenement ASC''',
                             (paroisse_id, paroisse_id, date.today().isoformat())).fetchall()
        else:
            evts = c.execute('''SELECT id, date_evenement, type_evenement, lieu, affiche_url FROM evenements
                                WHERE date_evenement >= ? ORDER BY date_evenement ASC''',
                             (date.today().isoformat(),)).fetchall()

        if not evts:
            st.info("Aucun évènement à venir.")
            return

        options = {}
        for e in evts:
            if len(e) < 2:
                continue
            d = safe_date(e[1])
            label = f"{d.strftime('%d/%m/%Y') if d else '??/??/????'} - {e[2]} - {e[3] or 'lieu à définir'}" + (" 🖼️" if e[4] else " (sans affiche)")
            options[label] = e
        choix = st.selectbox("Évènement", list(options.keys()), key=f"{cle}_sel")
        evt = options[choix]

        if evt[4]:
            st.image(evt[4], width=260)
        else:
            st.caption("❌ Aucune affiche enregistrée pour cet évènement.")

        fichier = st.file_uploader("Nouvelle affiche (visible dans l'Espace de Prière)",
                                   type=["jpg", "jpeg", "png", "webp"], key=f"{cle}_up_{evt[0]}")
        # COHABITATION : lien imgbb prioritaire, sinon upload Cloudinary
        lien_affiche = st.text_input("🔗 …ou collez un LIEN d'affiche (imgbb, etc.)",
                                     key=f"{cle}_lien_{evt[0]}",
                                     placeholder="https://i.ibb.co/...")
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button("📤 Publier l'affiche", key=f"{cle}_pub_{evt[0]}", type="primary", width="stretch"):
                url = None
                _lien = (lien_affiche or "").strip()
                if _lien:
                    if _lien.startswith("http"):
                        url = _lien
                    else:
                        st.error("❌ Le lien doit commencer par https:// (ex. https://i.ibb.co/…)")
                if not url and fichier:
                    url = sauvegarder_illustration(fichier)
                if url:
                    if evt[4] and "cloudinary" in str(evt[4]): supprimer_photo(evt[4])
                    c.execute("UPDATE evenements SET affiche_url=? WHERE id=?", (url, evt[0]))
                    commit_and_sync()
                    st.session_state["flash_success"] = "Affiche publiée ! ✅"
                    st.rerun()
                elif not _lien and not fichier:
                    st.error("⚠️ Collez un lien d'image OU sélectionnez un fichier ci-dessus.")
        with c2:
            if evt[4] and st.button("🗑️ Retirer l'affiche", key=f"{cle}_del_{evt[0]}", width="stretch"):
                supprimer_photo(evt[4])
                c.execute("UPDATE evenements SET affiche_url=NULL WHERE id=?", (evt[0],))
                commit_and_sync()
                st.session_state["flash_warning"] = "Affiche retirée."
                st.rerun()


def gerer_affiches_bande_annonces():
    """Onglet DIOCÈSE : affiches (images) et bandes-annonces (YouTube / vidéo)
    des évènements à venir -> Coin Affiche de l'Espace de Prière.
    Priorité d'affichage : bande-annonce > affiche > texte."""
    st.caption("Le visuel du prochain évènement à venir apparaît dans le Coin Affiche de l'Espace de Prière (public et membres). Priorité : bande-annonce > affiche > texte.")
    evts = c.execute('''SELECT id, date_evenement, type_evenement, lieu, affiche_url, video_url
                        FROM evenements WHERE date_evenement >= ? ORDER BY date_evenement ASC''',
                     (date.today().isoformat(),)).fetchall()
    if not evts:
        st.info("Aucun évènement à venir.")
        return

    options = {}
    for e in evts:
        d = safe_date(e[1])
        badges = (" 🖼️" if e[4] else "") + (" 🎬" if e[5] else "")
        label = f"{d.strftime('%d/%m/%Y') if d else '??/??'} - {e[2]} - {e[3] or 'lieu à définir'}{badges}"
        options[label] = e

    labels = list(options.keys())
    # FIX CRITIQUE : les labels sont DYNAMIQUES (badges 🖼️/🎬 qui apparaissent
    # après chaque publication). L'ancien label mémorisé par Streamlit dans le
    # session_state n'est alors plus une option valide → StreamlitAPIException
    # à chaque affichage de l'onglet. On purge la clé si sa valeur est périmée.
    if st.session_state.get("dio_visuel_sel") not in labels:
        st.session_state.pop("dio_visuel_sel", None)
    choix = st.selectbox("Évènement", labels, key="dio_visuel_sel")
    evt = options[choix]

    etat_img, etat_vid = st.columns(2)
    if evt[4]:
        with etat_img:
            st.caption("Affiche actuelle :")
            st.image(evt[4], width=260)
    else:
        with etat_img: st.caption("Affiche actuelle : ❌ aucune")
    if evt[5]:
        with etat_vid:
            st.caption("Bande-annonce actuelle :")
    if evt[5]:
        if str(evt[5]).startswith("http"):
            st.video(evt[5])
        else:
            st.caption("🎬 Vidéo enregistrée en local — retéléversez-la depuis votre ordinateur pour l'afficher ici.")
    else:
        with etat_vid: st.caption("Bande-annonce actuelle : ❌ aucune")

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**🖼️ Affiche (image)**")
        fichier = st.file_uploader("Nouvelle affiche", type=["jpg", "jpeg", "png", "webp"], key="dio_affiche_up")
        # COHABITATION : lien imgbb prioritaire, sinon upload Cloudinary
        lien_affiche_dio = st.text_input("🔗 …ou collez un LIEN d'affiche (imgbb, etc.)",
                                         key="dio_affiche_lien", placeholder="https://i.ibb.co/...")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("📤 Publier l'affiche", key="dio_affiche_pub", type="primary", width="stretch"):
                url = None
                _lien = (lien_affiche_dio or "").strip()
                if _lien:
                    if _lien.startswith("http"):
                        url = _lien
                    else:
                        st.error("❌ Le lien doit commencer par https:// (ex. https://i.ibb.co/…)")
                if not url and fichier:
                    url = sauvegarder_illustration(fichier)
                if url:
                    if evt[4] and "cloudinary" in str(evt[4]): supprimer_photo(evt[4])
                    c.execute("UPDATE evenements SET affiche_url=? WHERE id=?", (url, evt[0]))
                    commit_and_sync()
                    st.session_state["flash_success"] = "Affiche publiée ! ✅"
                    st.rerun()
                elif not _lien and not fichier:
                    st.error("⚠️ Collez un lien d'image OU sélectionnez un fichier ci-dessus.")
        with b2:
            if evt[4] and st.button("🗑️ Retirer", key="dio_affiche_del", width="stretch"):
                supprimer_photo(evt[4])
                c.execute("UPDATE evenements SET affiche_url=NULL WHERE id=?", (evt[0],))
                commit_and_sync()
                st.session_state["flash_warning"] = "Affiche retirée."
                st.rerun()
    with col_b:
        st.markdown("**🎬 Bande-annonce**")
        url_yt = st.text_input("URL YouTube ou lien vidéo direct (optionnel)", key="dio_ba_url",
                               placeholder="https://youtu.be/… ou https://…/video.mp4")
        fichier_video = st.file_uploader("…ou fichier vidéo (MP4)", type=["mp4", "mov"], key="dio_ba_up")
        b3, b4 = st.columns(2)
        with b3:
            if st.button("📤 Publier la bande-annonce", key="dio_ba_pub", type="primary", width="stretch"):
                _cand = (url_yt or "").strip()
                video = _cand if _cand.startswith("http") else (sauvegarder_video(fichier_video) if fichier_video else None)
                if video:
                    if evt[5] and "cloudinary" in evt[5]: supprimer_photo(evt[5])
                    c.execute("UPDATE evenements SET video_url=? WHERE id=?", (video, evt[0]))
                    commit_and_sync()
                    st.session_state["flash_success"] = "Bande-annonce publiée ! ✅"
                    st.rerun()
                else:
                    st.error("Collez une URL YouTube ou chargez un fichier vidéo.")
        with b4:
            if evt[5] and st.button("🗑️ Retirer", key="dio_ba_del", width="stretch"):
                if "cloudinary" in evt[5]: supprimer_photo(evt[5])
                c.execute("UPDATE evenements SET video_url=NULL WHERE id=?", (evt[0],))
                commit_and_sync()
                st.session_state["flash_warning"] = "Bande-annonce retirée."
                st.rerun()


def afficher_agenda_complet_universel(equipe_id=None, paroisse_id=None, diocese_id=None):
    st.markdown('<h3 style="color:#1A237E;">📋 Planification des agendas</h3>', unsafe_allow_html=True)
    query = '''SELECT id, date_event, type_event, lieu, description, auteur_nom, equipe_id, paroisse_id, diocese_id, a_faire_suivre, evenement_id FROM agenda WHERE date_event >= ? '''
    params, conditions = [date.today().isoformat()], []

    if equipe_id:
        conditions.extend([
            "equipe_id = ?",
            "(paroisse_id = ? AND equipe_id IS NULL AND (a_faire_suivre IS NULL OR a_faire_suivre != 2))",
            "(diocese_id = 1 AND paroisse_id IS NULL AND equipe_id IS NULL)"
        ])
        pid = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (equipe_id,)).fetchone()
        params.extend([equipe_id, pid[0] if pid and pid[0] else -1])
    elif paroisse_id:
        conditions.extend(["(paroisse_id = ? AND equipe_id IS NULL)", "equipe_id IN (SELECT id FROM equipes WHERE paroisse_id = ?)", "(diocese_id = 1 AND paroisse_id IS NULL AND equipe_id IS NULL)"])
        params.extend([paroisse_id, paroisse_id])
    elif diocese_id:
        conditions.extend([
            "(diocese_id = ? AND paroisse_id IS NULL AND equipe_id IS NULL)",
            "paroisse_id IN (SELECT id FROM paroisses WHERE diocese_id = ?)"
        ])
        params.extend([diocese_id, diocese_id])

    if conditions: query += " AND (" + " OR ".join(conditions) + ")"
    query += " ORDER BY date_event ASC"

    items = c.execute(query, params).fetchall()
    if not items: return st.info("Aucun évènement à venir.")

    role = st.session_state.get('role')
    mon_eq = st.session_state.get('equipe_id')
    ma_par = st.session_state.get('paroisse_id')

    for item in items:
        i_date = safe_date(item[1])
        if not i_date: continue

        source_icon, source_nom = "🏛️", "Diocèse"
        if item[6]:
            eq_info = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (item[6],)).fetchone()
            if eq_info: source_nom, source_icon = f"{eq_info[0]}", "👥"
        elif item[7]:
            par_info = c.execute("SELECT nom FROM paroisses WHERE id=?", (item[7],)).fetchone()
            if par_info: source_nom, source_icon = f"Paroisse {par_info[0]}", "🏘️"

        delta = (i_date - date.today()).days
        delai = "🔴 Aujourd'hui !" if delta == 0 else "🟠 Demain" if delta == 1 else f"🟡 Dans {delta} jours" if delta <= 7 else f"🟢 Dans {delta} jours"
        icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(item[2], "📅")

        titre = f"{icone} {i_date.strftime('%d/%m/%Y')} - {item[2]} - {source_icon} {source_nom} ({delai})"
        if item[9] == 1: titre = f"🚨 {titre}"
        elif item[9] == 2: titre = f"📬 {titre}"

        with st.expander(titre):
            if item[9] == 1:
                st.markdown('''<div style="background-color: #ffebee; margin: -10px -20px 20px -20px; padding: 15px 20px; border-left: 5px solid #d32f2f; border-radius: 0 8px 8px 0;"><span style="color: #b71c1c; font-weight: bold; font-size: 1.1rem;">🚩 Demande de transmission au Diocèse</span><br><span style="color: #c62828;">L\'équipe émettrice souhaite que cette information soit validée et transmise.</span></div>''', unsafe_allow_html=True)
            elif item[9] == 2:
                st.markdown('''<div style="background-color: #e8f5e9; margin: -10px -20px 20px -20px; padding: 15px 20px; border-left: 5px solid #2e7d32; border-radius: 0 8px 8px 0;"><span style="color: #1b5e20; font-weight: bold; font-size: 1.1rem;">📬 Information validée et transmise</span><br><span style="color: #2e7d32;">Cette annonce a été jugée pertinente et remontée par le niveau paroissial.</span></div>''', unsafe_allow_html=True)

            st.write(f"**🏢 Source :** {source_icon} {source_nom}")
            st.write(f"**👤 Ajouté par :** {item[5]}")
            if item[3]: st.write(f"**📍 Lieu :** {item[3]}")
            if item[4]: st.write(f"**📝 Détails :** {item[4]}")

            # Suppression : droits propriétaire/diocèse + CASCADE complète
            peut_supprimer = (
                role == 'diocese'
                or (item[6] is not None and item[6] == mon_eq)
                or (item[6] is None and item[7] is not None and item[7] == ma_par)
            )
            if peut_supprimer:
                if st.button("🗑️ Supprimer de mon agenda", key=f"del_ag_{item[0]}"):
                    if item[10]:
                        evt_id = item[10]
                        affiche_row = c.execute("SELECT affiche_url FROM evenements WHERE id=?", (evt_id,)).fetchone()
                        if affiche_row and affiche_row[0] and "cloudinary" in str(affiche_row[0]):
                            supprimer_photo(affiche_row[0])
                        c.execute("DELETE FROM suivi_presences WHERE evenement_id=?", (evt_id,))
                        c.execute("DELETE FROM evenement_equipes WHERE evenement_id=?", (evt_id,))
                        c.execute("DELETE FROM evenements WHERE id=?", (evt_id,))
                        c.execute("DELETE FROM agenda WHERE evenement_id=?", (evt_id,))
                    else:
                        c.execute("DELETE FROM agenda WHERE id=?", (item[0],))
                    commit_and_sync()
                    st.session_state["flash_warning"] = "Annonce supprimée."
                    st.rerun()

            # WhatsApp : lien GROUPE (écran de choix, voulu) + envoi DIRECT par membre
            if item[10]:
                base_url = URL_ESPACE_SPIRITUEL
                magic_link = f"{base_url}/?e={item[10]}"
                st.markdown("---")

                message = (f"Équipier, confirme ta présence pour la {item[2]} du {i_date.strftime('%d/%m/%Y')}.\n\n"
                           f"Cliquez ici pour répondre :\n{magic_link}")
                wa_link = f"https://wa.me/?text={urllib.parse.quote(message, safe=':/?=')}"
                st.markdown(f'<a href="{wa_link}" target="_blank" class="whatsapp-link">📱 Partager le lien de réponse (groupe / diffusion)</a>', unsafe_allow_html=True)

                if equipe_id:
                    with st.expander("👤 Envoyer directement à un membre (conversation ouverte)"):
                        membres_evt = c.execute("""SELECT nom, prenom, whatsapp, matloc FROM membres
                                                   WHERE equipe_id=? AND statut='actif' ORDER BY nom""",
                                                (equipe_id,)).fetchall()
                        if not membres_evt:
                            st.caption("Aucun membre actif dans l'équipe.")
                        else:
                            st.caption("Chaque membre reçoit SON lien personnel : il arrive sur sa page, l'évènement y figure, un clic suffit pour répondre.")
                            for m in membres_evt:
                                if not m[2]:
                                    continue
                                matloc_propre = str(m[3]).upper().strip()
                                lien_perso = f"{base_url}/?espace=1&matloc={matloc_propre}"
                                msg_perso = (f"Bonjour {m[0]} {m[1]},\n\n"
                                             f"Confirme ta présence pour la {item[2]} du {i_date.strftime('%d/%m/%Y')}"
                                             f"{f' à {item[3]}' if item[3] else ''}.\n\n"
                                             f"Ta page personnelle t'attend ici (un clic suffit pour répondre) :\n{lien_perso}\n\n"
                                             f"💡 Astuce : ajoute ce lien à ton écran d'accueil (menu ⋮ → « Ajouter à l'écran d'accueil ») pour y accéder directement !\n\n"
                                             f"Si le lien ne s'ouvre pas, saisis ce code sur la page de l'évènement : {matloc_propre}")
                                wa_perso = lien_whatsapp(m[2], msg_perso)
                                c_nom, c_btn = st.columns([3, 1])
                                with c_nom:
                                    st.write(f"**{m[0]} {m[1]}**")
                                with c_btn:
                                    st.markdown(f'<a href="{wa_perso}" target="_blank" class="whatsapp-link">📱 Envoyer</a>', unsafe_allow_html=True)


            # ===== SÉPARATION : information responsable VS invitation des membres =====
            # RÈGLE 4 AFFINÉE : un évènement transmis (ou accusé de réception) est une
            # information pour le RESPONSABLE. Ce n'est qu'à son initiative (bouton
            # ci-dessous) que l'évènement devient visible des membres dans
            # "📅 Mes prochains évènements" avec Réponse de Communion.
            if role == 'equipe' and item[6] == mon_eq and item[10]:
                deja_lie = c.execute("SELECT id FROM evenement_equipes WHERE evenement_id=? AND equipe_id=?",
                                     (item[10], mon_eq)).fetchone()
                st.markdown("---")
                if deja_lie:
                    st.success("✅ Vos membres sont invités à cet évènement (visible dans leur espace, Réponse de Communion active).")
                    if st.button("↩️ Retirer l'invitation des membres", key=f"uninvite_evt_{item[0]}"):
                        c.execute("DELETE FROM evenement_equipes WHERE evenement_id=? AND equipe_id=?",
                                  (item[10], mon_eq))
                        commit_and_sync()
                        st.session_state["flash_warning"] = "Invitation retirée : l'évènement disparaît de l'espace de vos membres."
                        st.rerun()
                else:
                    st.info("ℹ️ Information réservée à votre responsabilité — vos membres ne voient pas cet évènement.")
                    if st.button("📣 Inviter mes membres à cet évènement", key=f"invite_evt_{item[0]}", type="primary"):
                        c.execute("INSERT OR IGNORE INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)",
                                  (item[10], mon_eq))
                        commit_and_sync()
                        st.session_state["flash_success"] = "Membres invités ! L'évènement apparaît dans leur espace avec la Réponse de Communion, et dans votre formulaire de saisie des présences."
                        st.rerun()



            if role == 'paroisse':
                if item[6] and not item[7] and item[9] == 1:
                    eq_nom_res = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (item[6],)).fetchone()
                    eq_nom = eq_nom_res[0] if eq_nom_res else "Équipe inconnue"

                    c_val, c_ign = st.columns(2)
                    with c_val:
                        if st.button("⬆️ Valider et faire suivre", key=f"val_fwd_{item[0]}", type="primary"):
                            desc_dio = f"📢 **Transmis par la Paroisse**\nOrigine : {eq_nom}\n\n{item[4] or ''}"
                            c.execute('''INSERT INTO agenda (diocese_id, paroisse_id, date_event, type_event, lieu, description, auteur_nom, a_faire_suivre) VALUES (1, ?, ?, ?, ?, ?, ?, 2)''',
                                      (ma_par, item[1], item[2], item[3], desc_dio, f"{st.session_state.get('username')} (Transmis)"))
                            desc_accuse = f"✅ **Accusé de réception**\nVotre demande a été validée et transmise au Diocèse par la Paroisse."
                            c.execute('''INSERT INTO agenda (equipe_id, date_event, type_event, lieu, description, auteur_nom, a_faire_suivre) VALUES (?, ?, ?, ?, ?, ?, 2)''',
                                      (item[6], item[1], item[2], item[3], desc_accuse, f"{st.session_state.get('username')} (Accusé)"))
                            c.execute("DELETE FROM agenda WHERE id=?", (item[0],))
                            commit_and_sync()
                            st.session_state["flash_success"] = "Validé ! L'équipe est notifiée et le Diocèse a reçu l'information."
                            st.rerun()

                    with c_ign:
                        st.write("")
                        if st.button("❌ Ignorer la demande", key=f"ign_fwd_{item[0]}"):
                            c.execute("DELETE FROM agenda WHERE id=?", (item[0],))
                            commit_and_sync()
                            st.session_state["flash_warning"] = "Demande ignorée."
                            st.rerun()

                elif item[8] and not item[6]:
                    st.markdown("---")
                    equipes_paroisse = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (ma_par,)).fetchall()
                    if equipes_paroisse:
                        eq_dict = {e[1]: e[0] for e in equipes_paroisse}
                        c_sel, c_btn = st.columns([2, 1])
                        with c_sel:
                            choix_eq = st.selectbox("Transmettre à l'équipe :", list(eq_dict.keys()), key=f"fwd_sel_eq_{item[0]}")
                        with c_btn:
                            st.write("")
                            if st.button("⬇️ Faire suivre", key=f"fwd_eq_{item[0]}"):
                                new_desc = f"📢 **Transmis par la Paroisse**\nOrigine : Diocèse\n\n{item[4] or ''}"
                                # RÈGLE 4 AFFINÉE : la transmission est une INFORMATION
                                # au responsable d'équipe. On copie la référence de
                                # l'évènement (item[10]) mais on ne lie PAS l'équipe
                                # (pas d'evenement_equipes) : c'est le responsable qui
                                # décidera d'inviter ses membres ou non.
                                c.execute('''INSERT INTO agenda (equipe_id, date_event, type_event, lieu, description, auteur_nom, a_faire_suivre, evenement_id) VALUES (?,?,?,?,?,?,0,?)''',
                                          (eq_dict[choix_eq], item[1], item[2], item[3], new_desc, f"{st.session_state.get('username')} (Transmis)", item[10]))
                                commit_and_sync()
                                st.session_state["flash_success"] = f"Transmis à {choix_eq} ! Le responsable décidera d'inviter ses membres."
                                st.rerun()


def afficher_historique_suivi(equipe_id, filtre_type="Tous"):
    # BASCULE : strictement passé (< aujourd'hui). Le jour même, l'évènement
    # est encore côté formulaire de saisie. Filtrage présences sur CETTE équipe.
    query = '''SELECT e.id, e.date_evenement, e.type_evenement, e.lieu,
               SUM(CASE WHEN sp.statut='physique' THEN 1 ELSE 0 END),
               SUM(CASE WHEN sp.statut='spirituel' THEN 1 ELSE 0 END),
               SUM(CASE WHEN sp.statut='a_contacter' THEN 1 ELSE 0 END)
               FROM evenements e
               JOIN evenement_equipes ee ON e.id = ee.evenement_id
               LEFT JOIN suivi_presences sp ON e.id = sp.evenement_id
                    AND sp.membre_id IN (SELECT id FROM membres WHERE equipe_id = ?)
               WHERE ee.equipe_id = ? AND e.date_evenement < ? '''
    params = [equipe_id, equipe_id, date.today().isoformat()]
    if filtre_type != "Tous":
        query += " AND e.type_evenement = ?"
        params.append(filtre_type)
    query += " GROUP BY e.id ORDER BY e.date_evenement DESC LIMIT 20"

    annee_pasto, _, _ = get_periode_pastorale()
    annee_cloturee = est_cloture('equipe', equipe_id, annee_pasto)

    for ev in c.execute(query, params).fetchall():
        d_ev = safe_date(ev[1])
        if not d_ev: continue
        nb_p, nb_e, nb_a = ev[4] or 0, ev[5] or 0, ev[6] or 0
        taux = (nb_p / (nb_p+nb_e+nb_a) * 100) if (nb_p+nb_e+nb_a) > 0 else 0
        couleur = "green" if taux >= 75 else "orange" if taux >= 50 else "red"
        icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝", "Autre": "📌"}.get(ev[2], "📅")

        with st.expander(f"{icone} {d_ev.strftime('%d/%m/%Y')} - {ev[2]} | ✅ {nb_p} ⚠️ {nb_e} ❌ {nb_a}"):
            st.markdown(f"**Taux de présence :** :{couleur}[{taux:.0f}%]")
            for statut, label in [('physique', '✅ Présents physiques'), ('spirituel', '🟡 Présents spirituels'), ('a_contacter', '⚪ Sans nouvelles')]:
                rows = c.execute('''SELECT m.nom, m.prenom FROM membres m
                                    JOIN suivi_presences sp ON m.id=sp.membre_id
                                    WHERE sp.evenement_id=? AND sp.statut=? AND m.equipe_id=?''',
                                 (ev[0], statut, equipe_id)).fetchall()
                if rows:
                    st.write(f"{label} : " + ", ".join([f"{r[0]} {r[1]}" for r in rows]))

            if not annee_cloturee:
                if st.button("✏️ Rouvrir la saisie des présences", key=f"reopen_evt_{ev[0]}"):
                    st.session_state['rouvrir_evt_id'] = ev[0]
                    st.rerun()


def afficher_whatsapp_tabs(equipe_id=None, paroisse_id=None):
    t1, t2, t3 = st.tabs(["🎂 Anniversaires", "📢 Rappels réabonnement", "📿 Espace de prière"])

    with t1:
        # Confidentialité : filtrage par équipe OU paroisse
        query = '''SELECT m.nom, m.prenom, m.whatsapp, e.nom_equipe, p.nom, m.date_naissance
                   FROM membres m JOIN equipes e ON m.equipe_id=e.id JOIN paroisses p ON m.paroisse_id=p.id
                   WHERE m.statut='actif' AND strftime('%m-%d', m.date_naissance) = ?'''
        params = [date.today().strftime('%m-%d')]
        if equipe_id:
            query += " AND m.equipe_id = ?"; params.append(equipe_id)
        elif paroisse_id:
            query += " AND m.paroisse_id = ?"; params.append(paroisse_id)
        ans = c.execute(query, params).fetchall()
        if ans:
            for a in ans:
                st.markdown(f"**🎂 {a[0]} {a[1]}** - 📍 {a[4]} / {a[3]}")
                if a[2]:
                    lien = lien_whatsapp(a[2], f"Joyeux anniversaire {a[0]} {a[1]} ! 🎉\\n\\nToute l'équipe du Rosaire vous souhaite une journée bénie.")
                    if lien: st.markdown(f'<a href="{lien}" target="_blank" class="whatsapp-link">📱 Souhaiter</a>', unsafe_allow_html=True)
                st.markdown("---")
        else: st.info("🎉 Aucun anniversaire aujourd'hui")

    with t2:
        # Défaut = année PASTORALE (pas civile) : évite les faux rappels de janvier à août
        annee_defaut = get_periode_pastorale()[0]
        annee = st.number_input("Année de début", 2020, date.today().year + 1, min(annee_defaut, date.today().year + 1), key="rappel_whats")
        query = '''SELECT m.nom, m.prenom, m.whatsapp, e.nom_equipe, p.nom FROM membres m
                   JOIN equipes e ON m.equipe_id=e.id JOIN paroisses p ON m.paroisse_id=p.id
                   WHERE m.statut='actif' AND m.id NOT IN (SELECT a.membre_id FROM abonnements a WHERE a.annee_debut=? AND a.statut='paye')'''
        params = [annee]
        if equipe_id:
            query += " AND m.equipe_id = ?"; params.append(equipe_id)
        elif paroisse_id:
            query += " AND m.paroisse_id = ?"; params.append(paroisse_id)
        query += " ORDER BY p.nom, e.nom_equipe, m.nom"
        retard = c.execute(query, params).fetchall()
        if retard:
            for m in retard:
                st.markdown(f"**❌ {m[0]} {m[1]}** - 📍 {m[4]} / {m[3]}")
                if m[2]:
                    lien = lien_whatsapp(m[2], f"Bonjour {m[0]} {m[1]},\\n\\nVotre réabonnement pour la période {periode_affichage(annee)} n'a pas été enregistré. Merci de régulariser.")
                    if lien: st.markdown(f'<a href="{lien}" target="_blank" class="whatsapp-link">📱 Rappeler</a>', unsafe_allow_html=True)
                st.markdown("---")
        else: st.success(f"🎉 Tous à jour pour {periode_affichage(annee)} !")

    with t3:
        base_url = URL_ESPACE_SPIRITUEL

        st.markdown("#### 🌐 Lien Public (Pour tout le monde)")
        st.caption("Partagez ce lien dans vos groupes familiaux ou avec des personnes intéressées par la prière.")
        lien_public = f"{base_url}/?espace=1"
        message_public = f"Frères et sœurs, voici l'Espace de Prière et Méditation du Diocèse de Grand-Bassam :\n{lien_public}\n\nBon temps de ressourcement ! 🙏"
        wa_public = f"https://wa.me/?text={urllib.parse.quote(message_public, safe=':/?=')}"
        st.markdown(f"""<a href="{wa_public}" target="_blank" class="whatsapp-link">📱 Partager l'espace public sur WhatsApp</a>""", unsafe_allow_html=True)
        st.code(lien_public)
        st.markdown("**🔳 QR code de la page d'accueil** *(pour les responsables : connexion au gestionnaire)*")
        _qrcode_st(URL_ESPACE_SPIRITUEL + "/", 180)
        st.markdown("**📱 QR code de l'Espace communautaire** *(à projeter ou imprimer)*")
        _qrcode_st(lien_public, 220)

        if equipe_id:
            st.markdown("---")
            st.markdown("#### 👤 Liens Personnalisés (Mon équipe)")
            st.caption("Envoyez à chaque membre son lien d'accès privé — la conversation s'ouvre directement chez lui.")
            membres = c.execute("SELECT nom, prenom, whatsapp, matloc FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (equipe_id,)).fetchall()
            if not membres:
                st.info("Aucun membre actif dans l'équipe.")
            else:
                for m in membres:
                    matloc_propre = str(m[3]).upper().strip()
                    lien_perso = f"{base_url}/?espace=1&matloc={matloc_propre}"
                    msg_perso = f"Bonjour {m[0]} {m[1]},\n\nVoici votre espace spirituel personnel avec les prières et le programme de votre équipe :\n{lien_perso}\n\n💡 Astuce : ouvrez ce lien, puis menu ⋮ (ou Partager sur iPhone) → « Ajouter à l'écran d'accueil » : vous créerez un raccourci direct, sans plus passer par WhatsApp !\n\nBon temps de prière ! 📿"
                    col_nom, col_btn = st.columns([3, 1])
                    with col_nom:
                        st.write(f"**{m[0]} {m[1]}** (`{matloc_propre}`)")
                    with col_btn:
                        if m[2]:
                            # lien_whatsapp(num, msg) inclut le numéro -> conversation
                            # directe (l'écran de choix n'était pas voulu ici)
                            wa_perso = lien_whatsapp(m[2], msg_perso)
                            st.markdown(f"""<a href="{wa_perso}" target="_blank" class="whatsapp-link">📱 Envoyer</a>""", unsafe_allow_html=True)
                        else:
                            st.caption("_Pas de numéro_")
                        with st.expander("🔳 QR code personnel"):
                            _qrcode_st(lien_perso, 170)
                            st.caption(f"À imprimer avec le MatLoc `{matloc_propre}`")


def enregistrer_presence_equipe(equipe_id):
    annee_pasto, debut_pasto, fin_pasto = get_periode_pastorale()
    if est_cloture('equipe', equipe_id, annee_pasto):
        st.error(f"⛔ L'année pastorale {annee_pasto} - {annee_pasto+1} est clôturée. Impossible d'ajouter ou modifier des séances.")
        return

    membres_actifs = c.execute("SELECT id, nom, prenom FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (equipe_id,)).fetchall()
    if not membres_actifs:
        st.warning("Aucun membre actif dans l'équipe pour le moment.")
        return

    # Mode correction : rouverture d'une séance passée demandée depuis l'historique
    rouvrir_id = st.session_state.get('rouvrir_evt_id')

    with st.expander("📝 Enregistrer / Modifier une séance", expanded=bool(rouvrir_id)):
        # RÈGLE DE BASCULE : seuls les évènements À VENIR sont listés
        # (>= aujourd'hui : le jour même compte encore). Exception : un évènement
        # rouvert manuellement depuis l'historique (mode correction).
        evenements_lies = c.execute('''SELECT DISTINCT e.id, e.date_evenement, e.type_evenement, e.lieu, e.auteur_nom
                                       FROM evenements e JOIN evenement_equipes ee ON e.id = ee.evenement_id
                                       WHERE ee.equipe_id = ? AND (e.date_evenement >= ? OR e.id = ?)
                                       ORDER BY e.date_evenement ASC''',
                                    (equipe_id, date.today().isoformat(), rouvrir_id if rouvrir_id else -1)).fetchall()

        options_evts = {}
        for ev in evenements_lies:
            d_ev = safe_date(ev[1])
            if d_ev:
                if rouvrir_id and ev[0] == rouvrir_id:
                    label = f"✏️ [CORRECTION] {d_ev.strftime('%d/%m/%Y')} - {ev[2]}"
                else:
                    label = f"{d_ev.strftime('%d/%m/%Y')} - {ev[2]} (Par {ev[4] or 'Mon équipe'})"
                options_evts[label] = ev[0]

        labels_evts = ["-- Créer un nouvel évènement --"] + list(options_evts.keys())
        # FIX PRÉVENTIF : avec la bascule J+1, un évènement précédemment
        # sélectionné peut disparaître des options (il passe dans l'historique)
        # → purge de la sélection périmée pour éviter la StreamlitAPIException
        if st.session_state.get("sel_evt_exist") not in labels_evts:
            st.session_state.pop("sel_evt_exist", None)
        choix_evt = st.selectbox("📋 Sélectionner un évènement à venir", labels_evts, key="sel_evt_exist")

        event_id = None
        lieu_event = ""
        date_event = date.today()
        type_event = TYPES_EVENEMENTS[0]

        if choix_evt != "-- Créer un nouvel évènement --":
            event_id = options_evts[choix_evt]
            ev_details = c.execute("SELECT date_evenement, type_evenement, lieu FROM evenements WHERE id=?", (event_id,)).fetchone()
            date_event = safe_date(ev_details[0])
            type_event = ev_details[1]
            lieu_event = ev_details[2]
            date_affichee = date_event.strftime('%d/%m/%Y') if date_event else "⚠️ illisible"
            st.info(f"📅 Date : {date_affichee} | ⛪ Type : {type_event} | 📍 Lieu : {lieu_event or 'Non défini'}")
            if rouvrir_id and event_id == rouvrir_id:
                st.warning("✏️ Mode correction : cette séance est déjà passée. Vos modifications seront enregistrées dans l'historique.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1: date_event = st.date_input("📅 Date", value=date.today(), key="date_suivi_eq")
            with c2: type_event = st.selectbox("⛪ Type", TYPES_EVENEMENTS, key="type_suivi_eq")
            with c3: lieu_event = st.text_input("📍 Lieu", key="lieu_suivi_eq")

        dernier_event_en_memoire = st.session_state.get("dernier_event_vu")
        if event_id != dernier_event_en_memoire:
            cles_a_supprimer = [k for k in st.session_state.keys() if k.startswith("radio_membre_")]
            for k in cles_a_supprimer:
                del st.session_state[k]
            st.session_state["dernier_event_vu"] = event_id

        with st.form("form_suivi_presences"):
            date_affichee = date_event.strftime('%d/%m/%Y') if date_event else "⚠️ date non définie"
            st.markdown(f"**Participation de l'équipe pour le {date_affichee} ({type_event}) :**")
            st.caption("💡 Cochez 'Présent spirituel' pour ceux qui participent à l'évènement depuis chez eux. Les réponses arrivées via les liens des membres sont déjà pré-cochées.")

            # Une seule requête au lieu d'une par membre (N+1)
            existants = {}
            if event_id:
                existants = dict(c.execute("SELECT membre_id, statut FROM suivi_presences WHERE evenement_id=?", (event_id,)).fetchall())

            statuts = {}
            for m in membres_actifs:
                db_statut = existants.get(m[0])
                if db_statut not in ("physique", "spirituel", "a_contacter"):
                    db_statut = "a_contacter"
                widget_key = f"radio_membre_{m[0]}"
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = db_statut

                statuts[m[0]] = st.radio(
                    f"{m[1]} {m[2]}",
                    ["physique", "spirituel", "a_contacter"],
                    format_func=lambda x: {"physique": "🟢 Présent physiquement", "spirituel": "🟡 Présent spirituellement (à distance)", "a_contacter": "⚪ Sans nouvelles"}[x],
                    key=widget_key,
                    horizontal=True
                )

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Enregistrer la communion", width="stretch")
            with col_btn2:
                clear = st.form_submit_button("🗑️ Effacer cette séance", width="stretch")

            if submitted:
                if event_id:
                    c.execute("UPDATE evenements SET lieu=? WHERE id=?", (lieu_event, event_id))
                else:
                    if not date_event:
                        st.session_state["flash_warning"] = "Impossible de créer l'évènement : aucune date valide."
                        st.rerun()
                    c.execute("INSERT INTO evenements (equipe_id, type_evenement, date_evenement, lieu, auteur_nom) VALUES (?, ?, ?, ?, ?)",
                              (equipe_id, type_event, date_event.isoformat(), lieu_event, st.session_state.get('username')))
                    event_id = c.lastrowid
                    c.execute("INSERT OR IGNORE INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (event_id, equipe_id))

                # Ne supprimer que les présences des membres de CETTE équipe
                c.execute('''DELETE FROM suivi_presences
                             WHERE evenement_id=?
                               AND membre_id IN (SELECT id FROM membres WHERE equipe_id=?)''',
                          (event_id, equipe_id))
                for m_id, statut in statuts.items():
                    c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (m_id, event_id, statut))
                commit_and_sync()
                st.session_state.pop('rouvrir_evt_id', None)
                st.session_state["flash_success"] = "Communion de l'équipe enregistrée avec succès ! ✅"
                st.rerun()

            if clear:
                if not event_id:
                    st.warning("Aucune séance enregistrée à effacer pour le moment.")
                else:
                    c.execute('''DELETE FROM suivi_presences
                                 WHERE evenement_id=? AND membre_id IN (SELECT id FROM membres WHERE equipe_id=?)''',
                              (event_id, equipe_id))
                    c.execute("DELETE FROM evenement_equipes WHERE evenement_id=? AND equipe_id=?", (event_id, equipe_id))
                    restantes = c.execute("SELECT COUNT(*) FROM evenement_equipes WHERE evenement_id=?", (event_id,)).fetchone()[0]
                    if restantes == 0:
                        c.execute("DELETE FROM evenements WHERE id=?", (event_id,))
                    commit_and_sync()
                    st.session_state.pop('rouvrir_evt_id', None)
                    st.session_state["flash_warning"] = "Séance effacée."
                    st.rerun()

    st.markdown("---")
    st.subheader("📊 Historique et Engagement")
    filtre_type = st.selectbox("Filtrer par type d'évènement", ["Tous"] + TYPES_EVENEMENTS, key="filtre_hist_eq")
    afficher_historique_suivi(equipe_id, filtre_type)


def afficher_etat_presences_globales(equipe_id):
    st.markdown('<h3 style="color:#1A237E;">📊 État de l\'engagement spirituel (Croisement par évènement)</h3>', unsafe_allow_html=True)

    annee_actuelle, _, _ = get_periode_pastorale()
    choix_annee = st.selectbox("Année pastorale", [annee_actuelle, annee_actuelle - 1, annee_actuelle - 2],
                               format_func=lambda x: f"Sept {x} - Août {x+1}", key="sel_annee_eq_globale")

    debut_periode = date(choix_annee, 9, 1)
    fin_periode = date(choix_annee + 1, 8, 31)

    if est_cloture('equipe', equipe_id, choix_annee):
        st.success("✅ Cette année pastorale est clôturée et archivée.")
    elif choix_annee == annee_actuelle and date.today().month in [6, 7, 8]:
        if st.button("🔒 Clôturer et archiver cette année", key="cloturer_eq"):
            cloturer_periode('equipe', equipe_id, choix_annee, st.session_state.get('username'))
            st.session_state["flash_success"] = "Année clôturée ! Les données sont figées."
            st.rerun()

    membres = c.execute("SELECT nom, prenom FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (equipe_id,)).fetchall()
    if not membres:
        return st.info("Aucun membre actif dans l'équipe.")

    # Filtre sur l'équipe du MEMBRE (les réponses des autres équipes invitées
    # polluaient les statistiques sur les évènements partagés)
    presences = c.execute('''
        SELECT m.nom, m.prenom, e.type_evenement, sp.statut
        FROM suivi_presences sp
        JOIN evenements e ON sp.evenement_id = e.id
        JOIN membres m ON sp.membre_id = m.id
        WHERE m.equipe_id = ? AND e.date_evenement >= ? AND e.date_evenement <= ?
    ''', (equipe_id, debut_periode.isoformat(), fin_periode.isoformat())).fetchall()

    if not presences:
        return st.info(f"Aucune présence enregistrée pour la période de Sept {choix_annee} à Août {choix_annee+1}.")

    df = pd.DataFrame(presences, columns=["Nom", "Prenom", "Type", "Statut"])
    df['Est_Engage'] = df['Statut'].isin(['physique', 'spirituel']).astype(int)

    stats = df.groupby(['Nom', 'Prenom', 'Type'])['Est_Engage'].agg(['sum', 'count']).reset_index()
    stats.columns = ['Nom', 'Prenom', 'Type', 'Engage', 'Total']
    stats['Taux'] = (stats['Engage'] / stats['Total'] * 100).round(1)

    pivot = stats.pivot_table(index=['Nom', 'Prenom'], columns='Type', values='Taux', aggfunc='first')
    for t in TYPES_EVENEMENTS:
        if t not in pivot.columns: pivot[t] = 0.0
    pivot = pivot[TYPES_EVENEMENTS].fillna(0)

    pivot['Taux global'] = df.groupby(['Nom', 'Prenom'])['Est_Engage'].mean() * 100
    pivot = pivot.reset_index()

    # Membres actifs sans présence inclus (affichés à 0 %)
    membres_affiches = set(zip(pivot['Nom'], pivot['Prenom']))
    lignes_manquantes = [
        {'Nom': nom, 'Prenom': prenom, **{t: 0.0 for t in TYPES_EVENEMENTS}, 'Taux global': 0.0}
        for nom, prenom in membres if (nom, prenom) not in membres_affiches
    ]
    if lignes_manquantes:
        pivot = pd.concat([pivot, pd.DataFrame(lignes_manquantes)], ignore_index=True)

    pivot['Membres'] = pivot['Nom'] + ' ' + pivot['Prenom']
    pivot = pivot.drop(columns=['Nom', 'Prenom'])
    pivot.insert(0, 'N°', range(1, len(pivot) + 1))

    colonnes_finales = ['N°', 'Membres'] + TYPES_EVENEMENTS + ['Taux global']
    pivot = pivot[colonnes_finales].round(1)

    # Taux d'équipe calculés depuis les données brutes (pas de moyenne des moyennes)
    taux_equipe = {'N°': '', 'Membres': "📊 Taux d'engagement équipe"}
    for t in TYPES_EVENEMENTS:
        sous_df = df[df['Type'] == t]
        taux_equipe[t] = round(sous_df['Est_Engage'].mean() * 100, 1) if len(sous_df) else 0.0
    taux_equipe['Taux global'] = round(df['Est_Engage'].mean() * 100, 1)

    df_affichage = pivot.copy()
    for col in TYPES_EVENEMENTS + ['Taux global']: df_affichage[col] = df_affichage[col].apply(lambda x: f"{x:.1f}%")

    df_ligne_equipe = pd.DataFrame([taux_equipe])
    for col in TYPES_EVENEMENTS + ['Taux global']: df_ligne_equipe[col] = df_ligne_equipe[col].apply(lambda x: f"{x:.1f}%")

    df_final = pd.concat([df_affichage, df_ligne_equipe], ignore_index=True)
    st.dataframe(df_final, hide_index=True, width="stretch")

    st.markdown("---")
    st.markdown("### 📥 Générer les rapports d'activité")
    df_excel_complet = pd.concat([pivot, pd.DataFrame([taux_equipe])], ignore_index=True)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.markdown("**🏢 Rapport de l'équipe**")
        out_team = io.BytesIO()
        with pd.ExcelWriter(out_team, engine='openpyxl') as w: df_excel_complet.to_excel(w, index=False, sheet_name="Bilan Equipe")
        out_team.seek(0)
        st.download_button(label="📥 Télécharger le bilan de l'équipe", data=out_team, file_name=f"bilan_equipe_Sept{choix_annee}.xlsx", key="dl_team_report", width="stretch")

    with col_btn2:
        st.markdown("**👤 Rapport individuel**")
        noms_membres = ["-- Sélectionner --"] + [f"{m[0]} {m[1]}" for m in membres]
        choix_membre = st.selectbox("Choisir un membre", noms_membres, key="select_indiv_report")
        if choix_membre != noms_membres[0]:
            df_indiv = pivot[pivot['Membres'] == choix_membre].copy()
            out_indiv = io.BytesIO()
            with pd.ExcelWriter(out_indiv, engine='openpyxl') as w: df_indiv.to_excel(w, index=False, sheet_name=f"Bilan {choix_membre.split()[0]}")
            out_indiv.seek(0)
            st.download_button(label=f"📥 Télécharger le bilan de {choix_membre.split()[0]}", data=out_indiv,
                               file_name=f"bilan_{choix_membre.replace(' ', '_')}_Sept{choix_annee}.xlsx", key="dl_indiv_report", width="stretch")


def afficher_etat_presences_paroisse(paroisse_id):
    st.markdown('<h3 style="color:#1A237E;">📊 État de l\'engagement spirituel (Vue Paroisse)</h3>', unsafe_allow_html=True)

    annee_actuelle, _, _ = get_periode_pastorale()
    choix_annee = st.selectbox("Année pastorale", [annee_actuelle, annee_actuelle - 1, annee_actuelle - 2],
                               format_func=lambda x: f"Sept {x} - Août {x+1}", key="sel_annee_par_globale")

    debut_periode = date(choix_annee, 9, 1)
    fin_periode = date(choix_annee + 1, 8, 31)

    if est_cloture('paroisse', paroisse_id, choix_annee):
        st.success("✅ Cette année pastorale est clôturée et archivée pour la paroisse.")
    elif choix_annee == annee_actuelle and date.today().month in [6, 7, 8]:
        if st.button("🔒 Clôturer et archiver cette année (Paroisse)", key="cloturer_par"):
            cloturer_periode('paroisse', paroisse_id, choix_annee, st.session_state.get('username'))
            st.session_state["flash_success"] = "Année clôturée !"
            st.rerun()

    presences = c.execute('''
        SELECT COALESCE(eq.nom_equipe, 'Événement Paroisse') as Equipe, e.type_evenement, sp.statut
        FROM suivi_presences sp
        JOIN membres m ON sp.membre_id = m.id
        JOIN evenements e ON sp.evenement_id = e.id
        LEFT JOIN evenement_equipes ee ON e.id = ee.evenement_id AND ee.equipe_id = m.equipe_id
        LEFT JOIN equipes eq ON ee.equipe_id = eq.id
        WHERE (e.paroisse_id = ? OR eq.paroisse_id = ?) AND e.date_evenement >= ? AND e.date_evenement <= ?
    ''', (paroisse_id, paroisse_id, debut_periode.isoformat(), fin_periode.isoformat())).fetchall()

    if not presences:
        return st.info(f"Aucune présence enregistrée pour la période de Sept {choix_annee} à Août {choix_annee+1}.")

    df = pd.DataFrame([p[:3] for p in presences], columns=["Equipe", "Type", "Statut"])
    df['Est_Engage'] = df['Statut'].isin(['physique', 'spirituel']).astype(int)

    stats = df.groupby(['Equipe', 'Type'])['Est_Engage'].agg(['sum', 'count']).reset_index()
    stats.columns = ['Equipe', 'Type', 'Engage', 'Total']
    stats['Taux'] = (stats['Engage'] / stats['Total'] * 100).round(1)

    pivot = stats.pivot_table(index='Equipe', columns='Type', values='Taux', aggfunc='first')
    for t in TYPES_EVENEMENTS:
        if t not in pivot.columns: pivot[t] = 0.0
    pivot = pivot[TYPES_EVENEMENTS].fillna(0)

    pivot['Taux global'] = df.groupby('Equipe')['Est_Engage'].mean().mul(100)
    pivot = pivot.reset_index()

    # Équipes sans présence incluses (affichées à 0 %)
    equipes_paroisse = [r[0] for r in c.execute(
        "SELECT nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (paroisse_id,)).fetchall()]
    equipes_affichees = set(pivot['Equipe'])
    lignes_manquantes = [
        {'Equipe': eq, **{t: 0.0 for t in TYPES_EVENEMENTS}, 'Taux global': 0.0}
        for eq in equipes_paroisse if eq not in equipes_affichees
    ]
    if lignes_manquantes:
        pivot = pd.concat([pivot, pd.DataFrame(lignes_manquantes)], ignore_index=True)

    pivot.insert(0, 'N°', range(1, len(pivot) + 1))
    colonnes_finales = ['N°', 'Equipe'] + TYPES_EVENEMENTS + ['Taux global']
    pivot = pivot[colonnes_finales].round(1)

    taux_paroisse = {'N°': '', 'Equipe': "📊 Taux d'engagement Paroisse"}
    for t in TYPES_EVENEMENTS:
        sous_df = df[df['Type'] == t]
        taux_paroisse[t] = round(sous_df['Est_Engage'].mean() * 100, 1) if len(sous_df) else 0.0
    taux_paroisse['Taux global'] = round(df['Est_Engage'].mean() * 100, 1)

    df_affichage = pivot.copy()
    for col in TYPES_EVENEMENTS + ['Taux global']: df_affichage[col] = df_affichage[col].apply(lambda x: f"{x:.1f}%")

    df_ligne_paroisse = pd.DataFrame([taux_paroisse])
    for col in TYPES_EVENEMENTS + ['Taux global']: df_ligne_paroisse[col] = df_ligne_paroisse[col].apply(lambda x: f"{x:.1f}%")

    df_final = pd.concat([df_affichage, df_ligne_paroisse], ignore_index=True)
    st.dataframe(df_final, hide_index=True, width="stretch")

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as w:
        pd.concat([pivot, pd.DataFrame([taux_paroisse])], ignore_index=True).to_excel(w, index=False, sheet_name="Bilan Paroisse")
    out.seek(0)
    st.download_button("📥 Télécharger le bilan de la paroisse", data=out,
                       file_name=f"bilan_paroisse_Sept{choix_annee}.xlsx", key="dl_par_report", width="stretch")


def afficher_historique_paroisse(paroisse_id, filtre_type="Tous"):
    # BASCULE : strictement passé (< aujourd'hui), cohérent avec l'historique équipe
    query = '''SELECT e.id, e.date_evenement, e.type_evenement, e.lieu, GROUP_CONCAT(DISTINCT eq.nom_equipe) as noms_equipes,
               COUNT(DISTINCT CASE WHEN sp.statut='physique' THEN sp.membre_id END),
               COUNT(DISTINCT CASE WHEN sp.statut='spirituel' THEN sp.membre_id END),
               COUNT(DISTINCT CASE WHEN sp.statut='a_contacter' THEN sp.membre_id END)
               FROM evenements e
               JOIN evenement_equipes ee ON e.id = ee.evenement_id
               JOIN equipes eq ON ee.equipe_id = eq.id
               LEFT JOIN suivi_presences sp ON e.id = sp.evenement_id
               WHERE eq.paroisse_id = ? AND e.date_evenement < ? '''
    params = [paroisse_id, date.today().isoformat()]
    if filtre_type != "Tous":
        query += " AND e.type_evenement = ?"
        params.append(filtre_type)
    query += " GROUP BY e.id ORDER BY e.date_evenement DESC LIMIT 20"

    for ev in c.execute(query, params).fetchall():
        d_ev = safe_date(ev[1])
        if not d_ev: continue
        nb_p, nb_e, nb_a = ev[5] or 0, ev[6] or 0, ev[7] or 0
        total = nb_p + nb_e + nb_a
        taux = (nb_p / total * 100) if total > 0 else 0
        couleur = "green" if taux >= 75 else "orange" if taux >= 50 else "red"
        icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝", "Autre": "📌"}.get(ev[2], "📅")

        with st.expander(f"{icone} {d_ev.strftime('%d/%m/%Y')} - {ev[2]} ({ev[4] or '—'}) | ✅ {nb_p} ⚠️ {nb_e} ❌ {nb_a}"):
            st.markdown(f"**Taux de présence :** :{couleur}[{taux:.0f}%]")
            for statut, label in [('physique', '✅ Présents physiques'), ('spirituel', '🟡 Présents spirituels'), ('a_contacter', '⚪ Sans nouvelles')]:
                rows = c.execute('''SELECT m.nom, m.prenom, eq.nom_equipe FROM membres m
                                    JOIN suivi_presences sp ON m.id=sp.membre_id
                                    JOIN equipes eq ON m.equipe_id=eq.id
                                    WHERE sp.evenement_id=? AND sp.statut=?''', (ev[0], statut)).fetchall()
                if rows:
                    st.write(f"{label} : " + ", ".join([f"{r[0]} {r[1]} ({r[2]})" for r in rows]))


def afficher_page_reponse_membre(event_id):
    st.caption("🔒 En saisissant votre identifiant, vous acceptez que vos données de présence soient enregistrées par les responsables de votre équipe.")
    st.markdown("<h2 style='text-align:center; color:#1A237E; font-size: 1.5rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>📿 Réponse de Communion</h2>", unsafe_allow_html=True)

    try:
        event_id = int(event_id)
    except (ValueError, TypeError):
        st.error("Lien invalide.")
        return

    evt = c.execute("SELECT type_evenement, date_evenement, lieu FROM evenements WHERE id=?", (event_id,)).fetchone()
    if not evt:
        st.error("Cet événement n'existe pas.")
        return

    date_evt = safe_date(evt[1])
    st.markdown(f"""
    <div style="background-color:#f3e5f5; padding:20px; border-radius:10px; text-align:center; margin-bottom:30px;">
        <h3 style="color:#4A148C; margin-bottom:10px;">{evt[0]}</h3>
        <p style="font-size:1.1rem; color:#1A237E; margin:5px 0;">📅 {date_evt.strftime('%d/%m/%Y') if date_evt else 'Date inconnue'}</p>
        <p style="font-size:1.1rem; color:#1A237E; margin:5px 0;">📍 {evt[2] or 'Lieu non défini'}</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.get('event_id_verifie') != event_id:
        st.session_state['membre_verifie'] = False
        st.session_state['membre_info'] = None
        st.session_state['membre_a_repondu'] = False
        st.session_state['event_id_verifie'] = event_id

    # --- ÉTAPE 1 : VÉRIFICATION ---
    if not st.session_state.get('membre_verifie', False):
        st.markdown("**Entrez votre numéro de membre (MatLoc) :**")
        col1, col2 = st.columns([2, 1])
        with col1:
            matloc_saisi = st.text_input("MatLoc", placeholder="Ex: GBA-A1B2C", label_visibility="collapsed").upper().strip()
        with col2:
            st.write("")
            bouton_verifier = st.button("Vérifier", width="stretch")

        if bouton_verifier and matloc_saisi:
            membre = c.execute("""
                SELECT m.id, m.nom, m.prenom
                FROM membres m
                JOIN evenement_equipes ee ON m.equipe_id = ee.equipe_id
                WHERE m.matloc = ? AND ee.evenement_id = ? AND m.statut = 'actif'
            """, (matloc_saisi, event_id)).fetchone()

            if not membre:
                st.error("❌ MatLoc inconnu ou vous ne faites pas partie d'une équipe invitée à cet événement.")
            else:
                st.session_state['membre_verifie'] = True
                st.session_state['membre_info'] = membre
                st.session_state['membre_matloc'] = matloc_saisi
                st.rerun()

    # --- ÉTAPE 2 : LE CHOIX ---
    else:
        membre = st.session_state.get('membre_info')
        if not membre:
            st.session_state['membre_verifie'] = False
            st.rerun()
            return

        st.success(f"Bonjour **{membre[1]} {membre[2]}** ! Comment vous joignez-vous à nous ?")

        deja_repondu = c.execute("SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=?",
                                 (membre[0], event_id)).fetchone()
        index_defaut = 1 if (deja_repondu and deja_repondu[0] == 'spirituel') else 0

        choix = st.radio(
            "Votre engagement :",
            ["physique", "spirituel"],
            format_func=lambda x: {"physique": "🟢 Je serai présent physiquement", "spirituel": "🟡 Je prierai de chez moi (Spirituel)"}[x],
            index=index_defaut,
            horizontal=False
        )

        if st.button("✅ Confirmer ma réponse", width="stretch", type="primary"):
            if deja_repondu:
                c.execute("UPDATE suivi_presences SET statut=? WHERE membre_id=? AND evenement_id=?", (choix, membre[0], event_id))
            else:
                c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (membre[0], event_id, choix))
            commit_and_sync()
            st.session_state['membre_a_repondu'] = True

        if st.session_state.get('membre_a_repondu'):
            if choix == "physique":
                st.balloons()
                st.success("À bientôt en communion physique ! 🙏")
            else:
                st.snow()
                st.success("Merci pour votre communion spirituelle, nous nous unirons à vous ! 🙏")

            # Pont vers l'Espace de Prière (avec matloc du membre)
            st.markdown("---")
            lien_espace = f"{URL_ESPACE_SPIRITUEL}/?espace=1&matloc={st.session_state.get('membre_matloc', '')}"
            st.markdown(f"""
            <div style="text-align: center; margin-top: 30px; padding: 20px; background: #f3e5f5; border-radius: 15px;">
                <p style="font-size: 1.1rem; color: #4527a0; font-weight: bold;">Découvrez les ressources de la semaine</p>
                <a href="{lien_espace}" target="_blank"
                   style="background-color: #4527a0; color: white; padding: 12px 30px; text-decoration: none; border-radius: 30px; font-weight: bold; display: inline-block; font-size: 1.1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    🕊️ Accéder à l'Espace de Prière
                </a>
            </div>
            """, unsafe_allow_html=True)


def gerer_theme_pastoral():
    """🕯️ Interface diocèse : thème annuel, 12 sous-thèmes mensuels (feuillets),
    et le lien du thème avec CHACUN des 20 mystères."""
    st.caption("Structure : un thème annuel porté par un mystère (ex. 2026-2027 : "
               "« IL POSAIT DES QUESTIONS. FORCE DE LA FOI ! » — Mystère N°5, le "
               "Recouvrement au Temple), décliné en 12 sous-thèmes mensuels, et relié "
               "à chacun des 20 mystères. Affiché dans les deux espaces et dans le "
               "livre de la dizaine.")

    # ---------- 1. THÈME ANNUEL ----------
    st.markdown("### 1️⃣ Le thème de l'année")
    themes = c.execute("SELECT id, annee_debut, texte_theme, mystere_principal, actif FROM themes_pastoraux ORDER BY annee_debut DESC").fetchall()
    if themes:
        for t in themes:
            etat = "🟢 ACTIF" if t[4] else "⚪"
            c_txt, c_act = st.columns([5, 1])
            with c_txt:
                st.write(f"**{t[1]}-{t[1]+1}** {etat} — Mystère N°{t[3] or '?'}")
                st.caption(t[2])
            with c_act:
                if not t[4] and st.button("Activer", key=f"act_theme_{t[0]}"):
                    c.execute("UPDATE themes_pastoraux SET actif=0")
                    c.execute("UPDATE themes_pastoraux SET actif=1 WHERE id=?", (t[0],))
                    commit_and_sync()
                    st.rerun()

    st.info("🕯️ Le thème de l'année est désormais SOUMIS via le canal Communication "
            "(Service Communication → 🕯️ Thème pastoral) puis activé ici, à la validation du SAS. "
            "La liste ci-dessus permet de réactiver un thème déjà enregistré.")

    st.markdown("---")

    # ---------- 2. SOUS-THÈMES MENSUELS ----------
    st.markdown("### 2️⃣ Les 12 sous-thèmes mensuels (feuillets)")
    mois_actuel, _, _ = get_periode_pastorale()
    annees_existantes = [t[1] for t in themes] or [mois_actuel]
    annee_st = st.selectbox("Année pastorale", annees_existantes, key="tp_annee_st")

    MOIS_NOMS = ["Septembre", "Octobre", "Novembre", "Décembre", "Janvier", "Février",
                 "Mars", "Avril", "Mai", "Juin", "Juillet", "Août"]

    with st.form("form_sous_theme"):
        mois_st = st.selectbox("Mois pastoral", MOIS_NOMS, key="tp_mois")
        titre_st = st.text_input("Titre du sous-thème", key="tp_st_titre")
        contenu_st = st.text_area("Contenu / développement", height=120, key="tp_st_contenu")
        img_st = st.file_uploader("Affiche / illustration du mois (photo, optionnel)",
                                  type=["jpg", "jpeg", "png", "webp"], key="tp_st_img")
        # COHABITATION : lien imgbb prioritaire, sinon upload Cloudinary
        lien_img_st = st.text_input("🔗 …ou collez un LIEN d'affiche du mois (imgbb, etc.)",
                                    key="tp_st_img_lien", placeholder="https://i.ibb.co/...")
        pdf_st = st.file_uploader("Feuillet du mois (PDF, optionnel)", type=["pdf"], key="tp_st_pdf")
        # COHABITATION PDF : lien direct (hébergeur au choix) ou upload Cloudinary
        lien_pdf_st = st.text_input("🔗 …ou collez un LIEN direct du feuillet PDF",
                                    key="tp_st_pdf_lien", placeholder="https://…/feuillet.pdf")
        if st.form_submit_button("📅 Enregistrer le sous-thème", width="stretch"):
            if not titre_st.strip():
                st.error("Le titre du sous-thème est obligatoire.")
            else:
                url_pdf = None
                _lien_pdf = (lien_pdf_st or "").strip()
                if _lien_pdf:
                    if _lien_pdf.startswith("http"):
                        url_pdf = _lien_pdf
                    else:
                        st.error("Lien PDF ignoré : il doit commencer par https://")
                if not url_pdf and pdf_st:
                    url_pdf = sauvegarder_pdf(pdf_st)
                url_img = None
                _lien_img = (lien_img_st or "").strip()
                if _lien_img:
                    if _lien_img.startswith("http"):
                        url_img = _lien_img
                    else:
                        st.error("Lien d'affiche ignoré : il doit commencer par https://")
                if not url_img and img_st:
                    url_img = sauvegarder_illustration(img_st)
                mois_num = MOIS_NOMS.index(mois_st) + 1
                existant = c.execute("SELECT id, feuillet_pdf FROM sous_themes WHERE annee_debut=? AND mois=?",
                                     (annee_st, mois_num)).fetchone()
                if existant:
                    feuillet = url_pdf if url_pdf else existant[1]
                    c.execute("""UPDATE sous_themes SET titre=?, contenu=?, feuillet_pdf=? WHERE id=?""",
                              (titre_st.strip(), contenu_st.strip(), feuillet, existant[0]))
                    if url_img:
                        c.execute("UPDATE sous_themes SET affiche_url=? WHERE id=?", (url_img, existant[0]))
                else:
                    c.execute("""INSERT INTO sous_themes (annee_debut, mois, titre, contenu, feuillet_pdf, affiche_url)
                                 VALUES (?, ?, ?, ?, ?, ?)""",
                              (annee_st, mois_num, titre_st.strip(), contenu_st.strip(), url_pdf, url_img))
                commit_and_sync()
                st.session_state["flash_success"] = f"Sous-thème de {mois_st} enregistré ! ✅"
                st.rerun()

    existants_st = c.execute("""SELECT mois, titre, feuillet_pdf, affiche_url FROM sous_themes
                                WHERE annee_debut=? ORDER BY mois""", (annee_st,)).fetchall()
    if existants_st:
        st.caption("Sous-thèmes enregistrés :")
        for s in existants_st:
            c_m, c_t, c_p, c_d = st.columns([1, 5, 1, 1])
            with c_m: st.write(f"**{MOIS_NOMS[s[0]-1]}**")
            with c_t: st.write(s[1] + (" 🖼️" if s[3] else "") + (" 📄" if s[2] else ""))
            with c_p:
                if s[2]:
                    st.markdown(f'<a href="{s[2]}" target="_blank" style="color:#b39ddb; font-size:0.85rem;">📄 Voir</a>', unsafe_allow_html=True)
            with c_d:
                if st.button("🗑️", key=f"del_st_{annee_st}_{s[0]}"):
                    c.execute("DELETE FROM sous_themes WHERE annee_debut=? AND mois=?", (annee_st, s[0]))
                    commit_and_sync()
                    st.rerun()

    st.markdown("---")

    # ---------- 3. LE LIEN AVEC LES 20 MYSTÈRES ----------
    st.markdown("### 3️⃣ Le lien du thème avec les 20 mystères")
    st.caption("Pour chaque mystère, la phrase qui relie son contenu au thème de l'année. "
               "Cet encart apparaîtra dans le livre de la dizaine, sur la page du mystère.")
    annee_lien = st.selectbox("Année pastorale", annees_existantes, key="tp_annee_lien")

    with st.form("form_lien_mystere"):
        myst_lien = st.number_input("Mystère (1-20)", min_value=1, max_value=20, value=1, step=1, key="tp_myst_lien")
        existant_lien = c.execute("SELECT texte_lien FROM theme_mystere WHERE annee_debut=? AND mystere_id=?",
                                  (annee_lien, myst_lien)).fetchone()
        valeur_initiale = existant_lien[0] if existant_lien else ""
        texte_lien = st.text_area("Texte du lien thématique",
                                  value=valeur_initiale, height=100, key="tp_lien_txt",
                                  placeholder="Ex. (mystère 5) : Comme Jésus retrouvé au Temple, "
                                              "interrogeons notre foi : que demandons-nous à Dieu cette année ?")
        if st.form_submit_button("🔗 Enregistrer le lien", width="stretch"):
            if texte_lien.strip():
                c.execute("""INSERT INTO theme_mystere (annee_debut, mystere_id, texte_lien)
                             VALUES (?, ?, ?)
                             ON CONFLICT(annee_debut, mystere_id)
                             DO UPDATE SET texte_lien=excluded.texte_lien""",
                          (annee_lien, myst_lien, texte_lien.strip()))
                commit_and_sync()
                st.session_state["flash_success"] = f"Lien du mystère N°{myst_lien} enregistré ! ✅"
                st.rerun()
            else:
                st.error("Le texte du lien est obligatoire (ou videz le champ et utilisez Supprimer).")

    liens_existants = c.execute("""SELECT mystere_id, texte_lien FROM theme_mystere
                                   WHERE annee_debut=? ORDER BY mystere_id""", (annee_lien,)).fetchall()
    if liens_existants:
        st.caption(f"{len(liens_existants)} lien(s) enregistré(s) pour {annee_lien}-{annee_lien+1} :")
        for lm in liens_existants:
            c_m, c_t, c_d = st.columns([1, 6, 1])
            with c_m: st.write(f"**N°{lm[0]}**")
            with c_t: st.caption(lm[1][:100] + ("…" if len(lm[1]) > 100 else ""))
            with c_d:
                if st.button("🗑️", key=f"del_lien_{annee_lien}_{lm[0]}"):
                    c.execute("DELETE FROM theme_mystere WHERE annee_debut=? AND mystere_id=?", (annee_lien, lm[0]))
                    commit_and_sync()
                    st.rerun()

    # --- 🧪 TEST DE NOTIFICATION TELEGRAM (v7.6.6) ---
    st.markdown("---")
    with st.expander("🧪 Test de notification Telegram"):
        st.caption("Vérifie que les messages « soumission » et « publication » repartent bien.")
        if st.button("📨 Envoyer un message de test", key="test_telegram"):
            if envoyer_notification_telegram("🧪 Message de test — notifications des Équipes du Rosaire ✅"):
                st.success("Message envoyé ! Regardez votre Telegram. 📲")
            else:
                st.error("Échec. Vérifiez (1) les secrets TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID "
                         "(Streamlit Cloud → Manage app → Settings → Secrets) et (2) les logs "
                         "(Manage app → Logs) : le motif exact de l'échec y est désormais écrit.")
