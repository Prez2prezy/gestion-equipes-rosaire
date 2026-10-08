# ====================================================================
# views/view_diocese.py — VERSION 4.0 (reconstruction une pièce)
# Base : la version riche validée (messages flash, clés composites,
# re-SELECT Turso, PDF Cloudinary, nettoyage Cloudinary, bandes défilantes,
# graphe Fréquentation) + les acquis de session (WhatsApp responsables +
# expédition, QR paroissial dans Gérer paroisses, sceau Communication en
# onglet, migrations douces, Voir diocèse enrichi).
# RECADRAGE UTILISATEUR : « ➕ Publier du contenu » SUPPRIMÉ — tout contenu
# spirituel passe par la cellule Communication (prépare) et le sceau du
# diocèse (valide). Bandes défilantes = onglet dédié du diocèse.
# Marqueurs : Ctrl+F → "VERSION 4.0", "gerer_qr_paroissiaux" absent,
# "show_validation_communication" présent.
# ====================================================================
import os
import shutil
import html
import streamlit as st
import pandas as pd
import io
from datetime import date
from database import c, commit_and_sync, safe_migrate
from services import (hash_password, generer_mot_de_passe, safe_date, afficher_situation,
                      exporter_excel_diocese, periode_affichage, get_periode_pastorale,
                      supprimer_photo, afficher_messages_flash, lien_whatsapp, URL_ESPACE_SPIRITUEL,
                      synchroniser_menu_session, lire_menu_session)
from components import (ajouter_evenement_agenda, afficher_agenda_complet_universel,
                        afficher_whatsapp_tabs, afficher_historique_paroisse,
                        afficher_etat_presences_paroisse, _qrcode_png_bytes)


def _gestionnaire_archives_espace(texte_intro, types_contenus, prefixe):
    """v7.6.7 — Gestionnaire à coches réutilisable : liste les contenus des
    types donnés et permet une suppression MULTIPLE avec confirmation.
    Utilisé par les onglets « Prières 🙏 / Méditations 📖 » et « Musiques 🎵 »."""
    st.caption(texte_intro)
    _ph = ",".join("?" * len(types_contenus))
    _lignes = c.execute(f"""SELECT id, type_contenu, titre, date_publication, image_url, fichier_url, paroisse_cible
                            FROM espace_spirituel
                            WHERE type_contenu IN ({_ph})
                            ORDER BY type_contenu, date_publication DESC, id DESC""", types_contenus).fetchall()
    if not _lignes:
        st.info("Aucun élément dans cette catégorie.")
        return
    st.caption(f"📋 {len(_lignes)} élément(s).")
    _paroisses_map = {p[0]: p[1] for p in c.execute("SELECT id, nom FROM paroisses").fetchall()}
    _icone = {"priere": "🙏", "meditation": "📖", "audio": "🎵", "actualite": "📰"}
    _cochees = []
    for cont in _lignes:
        _cible_lbl = f" 🏘️ {_paroisses_map[cont[6]]}" if cont[6] and cont[6] in _paroisses_map else ""
        c_chk, c_txt = st.columns([1, 12])
        with c_chk:
            _coche = st.checkbox("", key=f"chk_{prefixe}_{cont[0]}")
        with c_txt:
            st.write(f"{_icone.get(cont[1], '📌')} **{cont[2] or '(sans titre)'}** — *{cont[1]}* · {cont[3]}{_cible_lbl}")
        if _coche:
            _cochees.append(cont)
    if not _cochees:
        st.session_state.pop(f"confirm_sup_{prefixe}", None)
    elif not st.session_state.get(f"confirm_sup_{prefixe}"):
        st.warning(f"⚠️ {len(_cochees)} élément(s) sélectionné(s) pour suppression.")
        if st.button("🗑️ Supprimer la sélection…", key=f"btn_sup_{prefixe}", type="primary"):
            st.session_state[f"confirm_sup_{prefixe}"] = True
            st.rerun()
    else:
        st.error("🔴 CONFIRMATION — les éléments cochés seront supprimés DÉFINITIVEMENT :")
        for cont in _cochees:
            st.write(f"• {_icone.get(cont[1], '📌')} {cont[2] or '(sans titre)'} ({cont[1]})")
        c_ok, c_ann, _r = st.columns([1.6, 1, 3])
        with c_ok:
            if st.button("✅ Oui, supprimer définitivement", key=f"btn_sup_{prefixe}_ok", type="primary"):
                for cont in _cochees:
                    for url in (cont[4], cont[5]):
                        if url and url.startswith("http"):
                            supprimer_photo(url)
                _ids = [x[0] for x in _cochees]
                _ph_del = ",".join("?" * len(_ids))
                c.execute(f"DELETE FROM espace_spirituel WHERE id IN ({_ph_del})", _ids)
                commit_and_sync()
                for cont in _cochees:
                    st.session_state.pop(f"chk_{prefixe}_{cont[0]}", None)
                st.session_state.pop(f"confirm_sup_{prefixe}", None)
                st.session_state["flash_success"] = f"{len(_ids)} élément(s) supprimé(s). 🗑️"
                st.rerun()
        with c_ann:
            if st.button("❌ Annuler", key=f"btn_sup_{prefixe}_non"):
                st.session_state.pop(f"confirm_sup_{prefixe}", None)
                st.rerun()

def show_diocese():
    d_info = c.execute("SELECT nom, responsable, bureau FROM diocese WHERE id=?", (1,)).fetchone()
    nom_dio = d_info[0] if d_info else "Diocèse"

    # Migrations douces (idempotentes, silencieuses) — v7.6.6 : via safe_migrate
    # (connexion jetable), même principe que database.py et le SAS.
    try:
        c.execute("SELECT whatsapp_responsable FROM paroisses LIMIT 1")
    except Exception:
        safe_migrate("ALTER TABLE paroisses ADD COLUMN whatsapp_responsable TEXT")
    try:
        c.execute("SELECT whatsapp_responsable FROM diocese LIMIT 1")
    except Exception:
        safe_migrate("ALTER TABLE diocese ADD COLUMN whatsapp_responsable TEXT")

    _rubriques_dio = [
        "🏛️ Voir diocèse", "🏘️ Créer paroisses", "📋 Gérer paroisses",
        "📅 Abonnements", "📌 Suivi", "🕊️ Espace spirituel", "💬 WhatsApp",
        "🔍 Rechercher matricule", "🔐 Gérer les accès", "📊 Statistiques", "📥 Export Excel",
        "📦 Archives", "🗑️ Réinitialiser"
    ]
    # Session neuve (F5) : restituer la rubrique mémorisée AVANT de dessiner
    # le menu — sinon il retombe sur la 1ʳᵉ entrée et efface la mémoire.
    if "nav_dio" in st.session_state and st.session_state["nav_dio"] not in _rubriques_dio:
        del st.session_state["nav_dio"]
    if "nav_dio" not in st.session_state:
        _rub = lire_menu_session()
        if _rub and _rub in _rubriques_dio:
            st.session_state["nav_dio"] = _rub
            st.session_state["_menu_sync"] = _rub
    menu = st.sidebar.radio("Navigation", _rubriques_dio, key="nav_dio")
    synchroniser_menu_session(menu)

    if menu == "🏛️ Voir diocèse":
        st.markdown(f'<h2 style="color:#1A237E; font-size: 1.4rem;">🏛️ {html.escape(nom_dio).upper()}</h2>', unsafe_allow_html=True)
        afficher_messages_flash()
        if d_info:
            _wa_dio_actuel = ""
            try:
                _row_dio = c.execute("SELECT whatsapp_responsable FROM diocese WHERE id=?", (1,)).fetchone()
                if _row_dio and _row_dio[0]:
                    _wa_dio_actuel = _row_dio[0]
            except Exception:
                pass
            st.markdown(f'<div class="custom-info-box"><b>Responsable diocésain :</b> {html.escape(d_info[1] or "")}<br><b>Bureau diocésain :</b> {html.escape(d_info[2] or "")}<br><b>📱 WhatsApp :</b> {_wa_dio_actuel or "Non renseigné"}</div>', unsafe_allow_html=True)
            with st.expander("✏️ Modifier les informations"):
                with st.form("form_edit_dio"):
                    c_ed1, c_ed2 = st.columns(2)
                    with c_ed1:
                        nr = st.text_input("Nouveau responsable", value=d_info[1] or "")
                        _wa_dio = st.text_input("📱 WhatsApp du responsable diocésain", value=_wa_dio_actuel)
                    with c_ed2:
                        nb = st.text_area("Nouveau bureau", value=d_info[2] or "")
                    if st.form_submit_button("💾 Enregistrer", width="stretch"):
                        c.execute("UPDATE diocese SET responsable=?, bureau=? WHERE id=?", (nr, nb, 1))
                        c.execute("UPDATE diocese SET whatsapp_responsable=? WHERE id=?", (_wa_dio.strip() or None, 1))
                        commit_and_sync()
                        st.session_state["flash_success"] = "Mis à jour ! ✅"
                        st.rerun()

    elif menu == "🏘️ Créer paroisses":
        st.markdown('<h2 style="color:#1A237E;">🏘️ Créer une paroisse</h2>', unsafe_allow_html=True)
        afficher_messages_flash()

        with st.form("creer_paroisse"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom de la paroisse")
                commune = st.text_input("Commune")
                responsable = st.text_input("Responsable")
                wa_resp = st.text_input("📱 WhatsApp du responsable (ex. 0700000000)")
            with c2:
                ville = st.text_input("Ville")
                bureau = st.text_area("Bureau")
            if st.form_submit_button("🏘️ Créer", width="stretch"):
                if nom and commune and ville and responsable:
                    if c.execute("SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=?", (nom.strip(), commune.strip(), ville.strip())).fetchone():
                        st.error("❌ Cette paroisse existe déjà !")
                    else:
                        c.execute("INSERT INTO paroisses (nom, commune, ville, responsable, bureau, whatsapp_responsable, diocese_id) VALUES (?,?,?,?,?,?,?)",
                                  (nom.strip(), commune.strip(), ville.strip(), responsable.strip(), bureau, wa_resp.strip() or None, 1))
                        # re-SELECT plutôt que lastrowid (invalide si reconnexion Turso)
                        pid = c.execute("SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=?",
                                        (nom.strip(), commune.strip(), ville.strip())).fetchone()[0]
                        username = f"paroisse_{pid}"
                        mdp = generer_mot_de_passe()
                        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id, paroisse_id) VALUES (?,?,?,?,?)",
                                  (username, hash_password(mdp), "paroisse", 1, pid))
                        commit_and_sync()
                        st.success(f"✅ Paroisse '{nom}' créée")
                        st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px;border:1px solid #c8e6c9;'>🔑 Identifiant : <code style='color:#d84315;'>{username}</code><br>🔒 Mot de passe : <code style='color:#d84315;'>{mdp}</code></div>", unsafe_allow_html=True)
                        if wa_resp.strip():
                            _msg = ("🕊️ Bénédiction !\n\n"
                                    + "La paroisse " + nom + " est enregistrée sur le Gestionnaire des Équipes du Rosaire (Diocèse de Grand-Bassam).\n\n"
                                    + "🔐 Vos identifiants de connexion (portail gestionnaire) :\n"
                                    + "👤 Utilisateur : " + username + "\n"
                                    + "🔑 Mot de passe : " + mdp + "\n"
                                    + "🌐 Le portail : " + URL_ESPACE_SPIRITUEL + "\n\n"
                                    + "🔳 Lien signé de votre Espace communautaire (à mettre sur vos affiches — le QR correspondant se télécharge dans le gestionnaire, menu Gérer paroisses) :\n"
                                    + URL_ESPACE_SPIRITUEL + "/?espace=1&p=" + str(pid) + "\n\n"
                                    + "📿 Que le Rosaire unisse votre paroisse !")
                            _wa_link = lien_whatsapp(wa_resp, _msg)
                            st.markdown("#### 📨 Expédition des identifiants")
                            st.caption("Un clic ouvre WhatsApp avec le message prêt — envoyez-le au responsable.")
                            st.markdown(f'<a href="{_wa_link}" target="_blank" class="whatsapp-link">📱 Envoyer les identifiants au responsable</a>', unsafe_allow_html=True)
                else:
                    st.error("Tous les champs sont requis")

    elif menu == "📋 Gérer paroisses":
        st.markdown('<h2 style="color:#1A237E;">📋 Consultation des paroisses</h2>', unsafe_allow_html=True)
        afficher_messages_flash()

        for state in ['show_equipes', 'show_equipiers', 'show_membres_equipe']:
            if state not in st.session_state: st.session_state[state] = None

        paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau, whatsapp_responsable FROM paroisses ORDER BY nom").fetchall()

        for p in paroisses:
            pid, nom, commune, ville, responsable, bureau, wa_resp_actuel = p
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
            nb_membres = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0]

            with st.expander(f"🏛️ {nom} ({commune} / {ville}) - {nb_equipes} équipe(s) - {nb_membres} membre(s)"):
                st.write(f"**Responsable :** {responsable}")
                st.write(f"**Bureau :** {bureau}")

                # QR signé de CETTE paroisse (traçabilité missionnaire)
                with st.expander("🔳 QR paroissial de cette paroisse"):
                    _url_signee = f"{URL_ESPACE_SPIRITUEL}/?espace=1&p={pid}"
                    st.code(_url_signee)
                    _png = _qrcode_png_bytes(_url_signee)
                    st.image(_png, width=200)
                    st.download_button("📥 Télécharger le QR (PNG)", data=_png,
                                       file_name=f"qr_paroisse_{pid}.png",
                                       key=f"qr_dl_{pid}", width="stretch")
                    st.caption("Imprimez ce QR sur les affiches de la paroisse : chaque scan est compté à son origine (fidèle anonyme).")

                # 📱 WhatsApp du responsable (édition — le responsable peut changer)
                with st.expander("📱 WhatsApp du responsable paroissial"):
                    _wa_new = st.text_input("Numéro WhatsApp", value=wa_resp_actuel or "",
                                            key=f"wa_edit_{pid}")
                    if st.button("💾 Enregistrer le numéro", key=f"wa_save_{pid}"):
                        c.execute("UPDATE paroisses SET whatsapp_responsable=? WHERE id=?",
                                  (_wa_new.strip() or None, pid))
                        commit_and_sync()
                        st.success("Numéro WhatsApp enregistré ! ✅")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👥 Voir les équipes", key=f"btn_equipes_{pid}"):
                        st.session_state['show_equipes'] = pid if st.session_state.get('show_equipes') != pid else None
                        st.session_state['show_equipiers'] = None
                        st.session_state['show_membres_equipe'] = None
                        st.rerun()
                with col2:
                    if st.button(f"👤 Voir tous les équipiers", key=f"btn_equipiers_{pid}"):
                        st.session_state['show_equipiers'] = pid if st.session_state.get('show_equipiers') != pid else None
                        st.session_state['show_equipes'] = None
                        st.session_state['show_membres_equipe'] = None
                        st.rerun()

                if st.session_state.get('show_equipes') == pid:
                    st.markdown("---")
                    st.markdown(f"#### 👥 Équipes de {nom}")
                    equipes = c.execute("SELECT id, nom_equipe, responsable, bureau FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
                    if not equipes: st.info("Aucune équipe dans cette paroisse")
                    else:
                        for eq in equipes:
                            eq_id, eq_nom, eq_resp, eq_bureau = eq
                            nb_membres_eq = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eq_id,)).fetchone()[0]
                            with st.expander(f"📌 {eq_nom} - Respo: {eq_resp} ({nb_membres_eq} membres)"):
                                st.write(f"**Bureau :** {eq_bureau}")
                                if st.button(f"📋 Voir les membres de {eq_nom}", key=f"btn_membres_eq_{eq_id}"):
                                    st.session_state['show_membres_equipe'] = eq_id if st.session_state.get('show_membres_equipe') != eq_id else None
                                    st.rerun()

                                if st.session_state.get('show_membres_equipe') == eq_id:
                                    membres_eq = c.execute("""SELECT matloc, matricule, nom, prenom, whatsapp, numero_meditation, date_adhesion
                                                            FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom""", (eq_id,)).fetchall()
                                    if not membres_eq: st.info("Aucun membre")
                                    else:
                                        df = pd.DataFrame(membres_eq, columns=["MatLoc", "Matricule", "Nom", "Prénom", "WhatsApp", "N° méditation", "Date adhésion"])
                                        df.insert(0, "N°", range(1, len(df) + 1))
                                        st.dataframe(df, hide_index=True, width="stretch")
                                        out = io.BytesIO()
                                        with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
                                        out.seek(0)
                                        st.download_button(f"📥 Exporter {eq_nom}", data=out, file_name=f"membres_{eq_nom}_{date.today()}.xlsx", key=f"export_eq_{eq_id}")

                if st.session_state.get('show_equipiers') == pid:
                    st.markdown("---")
                    st.markdown(f"#### 👤 Tous les équipiers de {nom}")
                    membres_paroisse = c.execute("""SELECT m.matloc, m.matricule, m.nom, m.prenom, m.whatsapp, m.numero_meditation, m.date_adhesion, e.nom_equipe
                                                    FROM membres m JOIN equipes e ON m.equipe_id = e.id
                                                    WHERE m.paroisse_id=? AND m.statut='actif' ORDER BY e.nom_equipe, m.nom""", (pid,)).fetchall()
                    if not membres_paroisse: st.info("Aucun membre actif")
                    else:
                        st.info(f"📊 Total : {len(membres_paroisse)} membre(s) actif(s)")
                        df = pd.DataFrame(membres_paroisse, columns=["MatLoc", "Matricule", "Nom", "Prénom", "WhatsApp", "N° méditation", "Date adhésion", "Équipe"])
                        df.insert(0, "N°", range(1, len(df) + 1))
                        st.dataframe(df, hide_index=True, width="stretch")
                        out = io.BytesIO()
                        with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
                        out.seek(0)
                        st.download_button(f"📥 Exporter les équipiers de {nom}", data=out, file_name=f"equipiers_{nom}_{date.today()}.xlsx", key=f"export_par_{pid}")

    elif menu == "📅 Abonnements":
        st.markdown('<h2 style="color:#1A237E;">📅 Suivi des abonnements (Diocèse)</h2>', unsafe_allow_html=True)

        for state in ['show_paroisse_abos', 'show_equipe_abos', 'abos_view_type']:
            if state not in st.session_state: st.session_state[state] = None

        annee_pastorale_en_cours = get_periode_pastorale()[0]
        annee_debut = st.number_input("Année de début de la période", min_value=2020, max_value=annee_pastorale_en_cours, value=annee_pastorale_en_cours, step=1)
        st.write(f"**Période :** {periode_affichage(annee_debut)}")

        total_membres = c.execute("SELECT COUNT(*) FROM membres WHERE statut='actif'").fetchone()[0]
        payes = c.execute("SELECT COUNT(*) FROM abonnements WHERE annee_debut=? AND statut='paye'", (annee_debut,)).fetchone()[0]

        c1, c2 = st.columns(2)
        c1.metric("📊 Total membres actifs", total_membres)
        c2.metric("✅ Abonnements enregistrés", payes)

        taux = f"{payes/total_membres*100:.0f}%" if total_membres else "0%"
        st.caption(f"📊 **Taux de recouvrement global :** {taux}")
        st.markdown("---")

        for p in c.execute("SELECT id, nom FROM paroisses ORDER BY nom").fetchall():
            pid, nom_paroisse = p
            stats = c.execute("""SELECT COUNT(m.id) as total, SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes
                                FROM membres m LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=?
                                WHERE m.paroisse_id=? AND m.statut='actif'""", (annee_debut, annee_debut, pid)).fetchone()
            total_par, payes_par = stats[0] or 0, stats[1] or 0
            pourcent = f"{(payes_par/total_par*100):.0f}%" if total_par > 0 else "0%"

            with st.expander(f"🏛️ {nom_paroisse} - {total_par} membre(s) - {payes_par} à jour ({pourcent})"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👥 Voir les équipes", key=f"abos_btn_equipes_{pid}"):
                        st.session_state['show_paroisse_abos'] = pid if not (st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'equipes') else None
                        st.session_state['abos_view_type'] = 'equipes'; st.session_state['show_equipe_abos'] = None; st.rerun()
                with col2:
                    if st.button(f"👤 Voir tous les équipiers", key=f"abos_btn_membres_{pid}"):
                        st.session_state['show_paroisse_abos'] = pid if not (st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'membres') else None
                        st.session_state['abos_view_type'] = 'membres'; st.session_state['show_equipe_abos'] = None; st.rerun()

                if st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'equipes':
                    st.markdown("---"); st.markdown(f"#### 👥 Équipes de {nom_paroisse}")
                    for eq in c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall():
                        eid, eq_nom = eq
                        stats_eq = c.execute("""SELECT COUNT(m.id) as total, SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes
                                              FROM membres m LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=?
                                              WHERE m.equipe_id=? AND m.statut='actif'""", (annee_debut, annee_debut, eid)).fetchone()
                        total_eq, payes_eq = stats_eq[0] or 0, stats_eq[1] or 0
                        pourcent_eq = f"{(payes_eq/total_eq*100):.0f}%" if total_eq > 0 else "0%"
                        with st.expander(f"📌 {eq_nom} - {total_eq} membre(s) - {payes_eq} à jour ({pourcent_eq})"):
                            if st.button(f"📋 Voir les détails", key=f"abos_voir_eq_{eid}"):
                                st.session_state['show_equipe_abos'] = eid if st.session_state.get('show_equipe_abos') != eid else None; st.rerun()
                            if st.session_state.get('show_equipe_abos') == eid:
                                membres_eq = c.execute("""SELECT m.id, m.nom, m.prenom, m.matricule, a.type_abonnement, a.date_paiement, a.montant
                                                        FROM membres m LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=? AND a.statut='paye'
                                                        WHERE m.equipe_id=? AND m.statut='actif' ORDER BY m.nom""", (annee_debut, eid)).fetchall()
                                abonnes, reabonnes, non_inscrits = [], [], []
                                for m in membres_eq:
                                    if m[4] == 'abonnement': abonnes.append(m)
                                    elif m[4] == 'reabonnement': reabonnes.append(m)
                                    else: non_inscrits.append(m)

                                t1, t2, t3 = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
                                with t1:
                                    if abonnes:
                                        df = pd.DataFrame(abonnes, columns=["ID", "Nom", "Prénom", "Matricule", "Type", "Date", "Montant"])[["Nom", "Prénom", "Matricule", "Date", "Montant"]]
                                        df["Montant"] = df["Montant"].apply(lambda x: f"{x or 0} FCFA")
                                        st.dataframe(df, hide_index=True, width="stretch")
                                    else: st.info("Aucun abonnement enregistré")
                                with t2:
                                    if reabonnes:
                                        df = pd.DataFrame(reabonnes, columns=["ID", "Nom", "Prénom", "Matricule", "Type", "Date", "Montant"])[["Nom", "Prénom", "Matricule", "Date", "Montant"]]
                                        df["Montant"] = df["Montant"].apply(lambda x: f"{x or 0} FCFA")
                                        st.dataframe(df, hide_index=True, width="stretch")
                                    else: st.info("Aucun réabonnement enregistré")
                                with t3:
                                    if non_inscrits:
                                        for n in non_inscrits: st.write(f"- {n[1]} {n[2]} ({n[3] or '—'})")
                                    else: st.success("✅ Tous les membres sont à jour")

                if st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'membres':
                    st.markdown("---"); st.markdown(f"#### 👤 Tous les équipiers de {nom_paroisse}")
                    membres_paroisse = c.execute("""SELECT m.id, m.nom, m.prenom, m.matricule, m.whatsapp, e.nom_equipe, a.type_abonnement, a.date_paiement, a.montant
                                                    FROM membres m JOIN equipes e ON m.equipe_id = e.id
                                                    LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=? AND a.statut='paye'
                                                    WHERE m.paroisse_id=? AND m.statut='actif' ORDER BY e.nom_equipe, m.nom""", (annee_debut, pid)).fetchall()
                    if not membres_paroisse: st.info("Aucun membre actif")
                    else:
                        abonnes_par, reabonnes_par, non_inscrits_par = [], [], []
                        for m in membres_paroisse:
                            if m[6] == 'abonnement': abonnes_par.append(m)
                            elif m[6] == 'reabonnement': reabonnes_par.append(m)
                            else: non_inscrits_par.append(m)
                        st.info(f"📊 Total : {len(membres_paroisse)} - ✅ {len(abonnes_par)} abonnés - 🔄 {len(reabonnes_par)} réabonnés - ❌ {len(non_inscrits_par)} non enregistrés")
                        t1, t2, t3 = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
                        with t1:
                            if abonnes_par:
                                df = pd.DataFrame(abonnes_par, columns=["ID", "Nom", "Prénom", "Matricule", "WhatsApp", "Équipe", "Type", "Date", "Montant"])[["Nom", "Prénom", "Matricule", "WhatsApp", "Équipe", "Date", "Montant"]]
                                df["Montant"] = df["Montant"].apply(lambda x: f"{x or 0} FCFA")
                                st.dataframe(df, hide_index=True, width="stretch")
                            else: st.info("Aucun abonnement")
                        with t2:
                            if reabonnes_par:
                                df = pd.DataFrame(reabonnes_par, columns=["ID", "Nom", "Prénom", "Matricule", "WhatsApp", "Équipe", "Type", "Date", "Montant"])[["Nom", "Prénom", "Matricule", "WhatsApp", "Équipe", "Date", "Montant"]]
                                df["Montant"] = df["Montant"].apply(lambda x: f"{x or 0} FCFA")
                                st.dataframe(df, hide_index=True, width="stretch")
                            else: st.info("Aucun réabonnement")
                        with t3:
                            if non_inscrits_par:
                                for n in non_inscrits_par: st.write(f"- {n[1]} {n[2]} ({n[3] or '—'}) - {n[5]}")
                            else: st.success("✅ Tous les membres sont à jour")

    elif menu == "📌 Suivi":
        st.markdown(f'<h2 style="color:#1A237E;">📌 Suivi et Agenda - {nom_dio}</h2>', unsafe_allow_html=True)

        tab_avenir, tab_passe, tab_etat = st.tabs(["📅 Agenda", "📝 Vie de prière des paroisses", "📊 Engagement spirituel"])

        with tab_avenir:
            ajouter_evenement_agenda(diocese_id=1, auteur_nom=st.session_state.get('username'))
            st.markdown("---")
            afficher_agenda_complet_universel(diocese_id=1)

        with tab_passe:
            paroisses = c.execute("SELECT id, nom, commune FROM paroisses").fetchall()
            if paroisses:
                par_dict = {f"{p[1]} ({p[2]})": p[0] for p in paroisses}
                choix_par = st.selectbox("Sélectionnez la paroisse", list(par_dict.keys()), key="suivi_hist_dio_par")
                pid_select = par_dict[choix_par]

                from services import TYPES_EVENEMENTS
                filtre_type = st.selectbox("Filtrer par type d'évènement", ["Tous"] + TYPES_EVENEMENTS, key="filtre_hist_dio")

                afficher_historique_paroisse(paroisse_id=pid_select, filtre_type=filtre_type)
            else:
                st.info("Aucune paroisse créée.")

        with tab_etat:
            paroisses2 = c.execute("SELECT id, nom, commune FROM paroisses").fetchall()
            if paroisses2:
                par_dict2 = {f"{p[1]} ({p[2]})": p[0] for p in paroisses2}
                choix_par2 = st.selectbox("Sélectionnez la paroisse pour le bilan", list(par_dict2.keys()), key="etat_hist_dio_par")
                pid_select2 = par_dict2[choix_par2]

                afficher_etat_presences_paroisse(paroisse_id=pid_select2)
            else:
                st.info("Aucune paroisse créée.")

    elif menu == "🕊️ Espace spirituel":
        st.markdown('<h2 style="color:#1A237E;">🕊️ Gestion de l\'Espace Spirituel</h2>', unsafe_allow_html=True)
        st.caption("Le Service Communication prépare les contenus — VOUS seul publiez (onglet 📡). "
                   "Le thème pastoral et les bandes défilantes se gèrent ici. "
                   "Ce qui est validé rejoint l'Espace de Prière : évangélisation élargie, membres et visiteurs.")
        afficher_messages_flash()

        tab_com, tab_manage = st.tabs(["📡 Communication", "📋 Contenu existant"])

        with tab_com:
            st.caption("🕯️ Le SAS : la cellule Communication prépare et soumet — VOUS seul validez et publiez. "
                       "Chaque contenu validé rejoint sa zone dédiée de l'Espace de Prière. "
                       "En bas du SAS : vos outils de gestion du thème (activation, sous-thèmes, liens).")
            from views.view_communication_validation import show_validation_communication
            show_validation_communication()

        with tab_manage:
            t_bandes, t_pm, t_mu, t_autres = st.tabs(["📺 Bandes défilantes actives", "Prières 🙏 / Méditations 📖", "Musiques 🎵", "📦 Autres contenus"])

            with t_bandes:
                st.caption("Maximum 3 bandes actives — seules les plus récentes s'affichent dans l'entête des espaces. "
                           "Les bandes sont soumises par le Service Communication puis validées au SAS (📡).")
                bandes_actives = c.execute("""SELECT id, contenu_texte, fichier_url, date_publication, paroisse_cible FROM espace_spirituel
                                              WHERE type_contenu='annonce_defilante'
                                              ORDER BY date_publication DESC, id DESC""").fetchall()
                if not bandes_actives:
                    st.info("Aucune bande défilante active.")
                else:
                    if len(bandes_actives) >= 3:
                        st.warning(f"⚠️ {len(bandes_actives)} bandes actives : seules les 3 plus récentes s'affichent dans l'entête. Supprimez les anciennes.")
                    _paroisses_map = {p[0]: p[1] for p in c.execute("SELECT id, nom FROM paroisses").fetchall()}
                    for b in bandes_actives:
                        etiquette = "🌐 Partout" if b[2] != 'membre' else "👤 Membres seuls"
                        _cible_lbl = f" • 🏘️ {_paroisses_map[b[4]]}" if b[4] and b[4] in _paroisses_map else ""
                        c_txt, c_infos, c_btn = st.columns([4, 2, 1])
                        with c_txt:
                            st.write(f"📺 {b[1]}")
                        with c_infos:
                            st.caption(f"{etiquette}{_cible_lbl} • {b[3]}")
                        with c_btn:
                            if st.button("🗑️", key=f"del_defil_{b[0]}"):
                                c.execute("DELETE FROM espace_spirituel WHERE id=?", (b[0],))
                                commit_and_sync()
                                st.rerun()

            with t_pm:
                _gestionnaire_archives_espace(
                    "Gestion DÉDIÉE des Prières 🙏 et Méditations 📖 — exactement ce que voit "
                    "l'utilisateur dans sa rubrique 📖 Archives. Cochez puis supprimez en un "
                    "seul clic (avec confirmation).",
                    ("priere", "meditation"), "pm")

            with t_mu:
                _gestionnaire_archives_espace(
                    "Gestion DÉDIÉE des Musiques 🎵 — fichiers audio ET vidéos YouTube "
                    "publiés dans la sous-rubrique 🎵 Musiques. Cochez puis supprimez en un "
                    "seul clic (avec confirmation).",
                    ("audio",), "mu")

            with t_autres:
                # v7.6.6 — DEMANDE 5 & 6 : les archives (prières, méditations,
                # musiques, actualités) NE PASSENT PLUS ICI (onglet 📖 Archives).
                # Ce gestionnaire ne garde que les contenus divers, avec coches.
                st.caption("Contenus DIVERS (hors archives, hors bandes défilantes). "
                           "Prières, méditations, musiques et actualités : voir l'onglet 📖 Archives.")
                contenus = c.execute("""SELECT id, type_contenu, titre, date_publication, image_url, fichier_url, paroisse_cible
                                        FROM espace_spirituel
                                        WHERE type_contenu NOT IN ('annonce_defilante','priere','meditation','audio','actualite')
                                        ORDER BY date_publication DESC, id DESC""").fetchall()
                if not contenus:
                    st.info("Aucun contenu divers. Les prières, méditations, musiques et actualités "
                            "sont gérées dans l'onglet 📖 Archives.")
                else:
                    _paroisses_map = {p[0]: p[1] for p in c.execute("SELECT id, nom FROM paroisses").fetchall()}
                    _coches_autres = []
                    for cont in contenus:
                        _cible_lbl = f" 🏘️ {_paroisses_map[cont[6]]}" if cont[6] and cont[6] in _paroisses_map else ""
                        c_chk, c_txt = st.columns([1, 12])
                        with c_chk:
                            _coche = st.checkbox("", key=f"chk_autre_{cont[0]}")
                        with c_txt:
                            st.write(f"📌 **{cont[2] or '(sans titre)'}** — *{cont[1]}* · {cont[3]}{_cible_lbl}")
                        if _coche:
                            _coches_autres.append(cont)
                    if not _coches_autres:
                        st.session_state.pop("confirm_sup_autres", None)
                    elif not st.session_state.get("confirm_sup_autres"):
                        st.warning(f"⚠️ {len(_coches_autres)} élément(s) sélectionné(s) pour suppression.")
                        if st.button("🗑️ Supprimer la sélection…", key="btn_sup_autres", type="primary"):
                            st.session_state["confirm_sup_autres"] = True
                            st.rerun()
                    else:
                        st.error("🔴 CONFIRMATION — les éléments cochés seront supprimés DÉFINITIVEMENT :")
                        for cont in _coches_autres:
                            st.write(f"• 📌 {cont[2] or '(sans titre)'} ({cont[1]})")
                        c_ok2, c_ann2, _r2 = st.columns([1.6, 1, 3])
                        with c_ok2:
                            if st.button("✅ Oui, supprimer définitivement", key="btn_sup_autres_ok", type="primary"):
                                for cont in _coches_autres:
                                    for url in (cont[4], cont[5]):
                                        if url and url.startswith("http"):
                                            supprimer_photo(url)
                                _ids2 = [x[0] for x in _coches_autres]
                                _ph2 = ",".join("?" * len(_ids2))
                                c.execute(f"DELETE FROM espace_spirituel WHERE id IN ({_ph2})", _ids2)
                                commit_and_sync()
                                for cont in _coches_autres:
                                    st.session_state.pop(f"chk_autre_{cont[0]}", None)
                                st.session_state.pop("confirm_sup_autres", None)
                                st.session_state["flash_success"] = f"{len(_ids2)} élément(s) supprimé(s). 🗑️"
                                st.rerun()
                        with c_ann2:
                            if st.button("❌ Annuler", key="btn_sup_autres_non"):
                                st.session_state.pop("confirm_sup_autres", None)
                                st.rerun()

    elif menu == "💬 WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Messages WhatsApp - {nom_dio}</h2>', unsafe_allow_html=True)
        afficher_whatsapp_tabs(equipe_id=None, paroisse_id=None)

    elif menu == "🔍 Rechercher matricule":
        st.markdown('<h2 style="color:#1A237E;">🔍 Recherche par matricule</h2>', unsafe_allow_html=True)
        matricule = st.text_input("Matricule (MatLoc ou Matricule)")
        if matricule.strip():
            m = c.execute('''SELECT m.matloc, m.matricule, m.nom, m.prenom, m.whatsapp, p.nom, e.nom_equipe, m.photo_path
                             FROM membres m
                             LEFT JOIN paroisses p ON m.paroisse_id = p.id
                             LEFT JOIN equipes e ON m.equipe_id = e.id
                             WHERE (m.matloc = ? OR m.matricule = ?) AND m.statut = 'actif' ''',
                          (matricule.upper().strip(), matricule.upper().strip())).fetchone()
            if m:
                st.success("Membre trouvé")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**{m[2]} {m[3]}** - MatLoc: {m[0]} | Matricule: {m[1] or '—'}")
                    st.write(f"💬 WhatsApp: {m[4] or 'Non renseigné'}")
                    st.markdown(f"🏘️ **Paroisse :** {m[5] or 'Non assignée'}  \n👥 **Équipe :** {m[6] or 'Non assignée'}")
                with col2:
                    if m[7]:
                        try: st.image(m[7], width=100)
                        except Exception: pass
            else:
                st.error("Non trouvé ou membre archivé")

    elif menu == "🔐 Gérer les accès":
        st.markdown('<h2 style="color:#1A237E;">🔐 Gestion des accès</h2>', unsafe_allow_html=True)
        afficher_messages_flash()
        st.markdown("### 🏘️ Paroisses")
        for p in c.execute("SELECT id, nom, responsable FROM paroisses").fetchall():
            user = c.execute("SELECT id, username FROM utilisateurs WHERE paroisse_id=? AND role='paroisse'", (p[0],)).fetchone()
            if user:
                with st.expander(f"🏛️ {p[1]} - {p[2]}"):
                    st.write(f"**Identifiant :** `{user[1]}`")
                    if st.button(f"🔄 Réinitialiser le mot de passe", key=f"reset_par_{p[0]}"):
                        nouveau = generer_mot_de_passe()
                        c.execute("UPDATE utilisateurs SET password=? WHERE id=?", (hash_password(nouveau), user[0]))
                        commit_and_sync()
                        st.session_state['new_pwd_par'] = {'user': user[1], 'pwd': nouveau}

                    if st.session_state.get('new_pwd_par') and st.session_state['new_pwd_par']['user'] == user[1]:
                        st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px;border:1px solid #c8e6c9;'>🔑 Nouveau mot de passe pour <code>{st.session_state['new_pwd_par']['user']}</code> : <code style='color:#d84315;font-size:1.2rem;'>{st.session_state['new_pwd_par']['pwd']}</code></div>", unsafe_allow_html=True)
                        if st.button("OK, j'ai noté le mot de passe", key=f"ok_pwd_par_{p[0]}"):
                            del st.session_state['new_pwd_par']
                            st.rerun()

    elif menu == "📊 Statistiques":
        st.markdown('<h2 style="color:#1A237E;">📊 Statistiques générales</h2>', unsafe_allow_html=True)
        tab_gen, tab_freq = st.tabs(["📌 Général", "📈 Fréquentation"])
        with tab_gen:
            c1, c2, c3 = st.columns(3)
            c1.metric("🏘️ Paroisses", c.execute("SELECT COUNT(*) FROM paroisses").fetchone()[0])
            c2.metric("👥 Équipes", c.execute("SELECT COUNT(*) FROM equipes").fetchone()[0])
            c3.metric("👤 Membres actifs", c.execute("SELECT COUNT(*) FROM membres WHERE statut='actif'").fetchone()[0])
        with tab_freq:
            st.caption("Visites des 30 derniers jours (une visite = une ouverture de session).")
            from services import stats_visites_pivot
            pivot = stats_visites_pivot(30)
            if pivot.empty:
                st.info("Aucune visite enregistrée sur la période.")
            else:
                pivot = pivot.rename(columns={"communautaire": "🏘️ Communautaire", "membre": "👤 Membre"})
                st.bar_chart(pivot)
            totaux = c.execute("SELECT page, COUNT(*) FROM stats_visites GROUP BY page").fetchall()
            d1, d2 = st.columns(2)
            for nom_page, nb in totaux:
                if nom_page == "communautaire":
                    d1.metric("🌐 Total Espace communautaire", nb)
                elif nom_page == "membre":
                    d2.metric("👤 Total Espace Membre", nb)

    elif menu == "📥 Export Excel":
        st.markdown('<h2 style="color:#1A237E;">📥 Export des données</h2>', unsafe_allow_html=True)
        if c.execute("SELECT COUNT(*) FROM membres").fetchone()[0] == 0: st.warning("Aucune donnée à exporter.")
        else:
            excel_file = exporter_excel_diocese()
            st.download_button("📥 Télécharger l'export global", data=excel_file, file_name=f"export_diocese_{date.today()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

    elif menu == "📦 Archives":
        st.markdown('<h2 style="color:#1A237E; font-size: 1.4rem;">📦 Archives du diocèse</h2>', unsafe_allow_html=True)
        archives = c.execute('''SELECT m.matloc, m.matricule, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire, a.equipe_id, a.paroisse_id, a.auteur_nom
                                FROM archives a JOIN membres m ON a.membre_id = m.id ORDER BY a.date_fin DESC''').fetchall()
        if not archives: st.info("Aucune archive.")
        else:
            for a in archives:
                d1, d2 = safe_date(a[5]), safe_date(a[6])
                duree = (d2 - d1).days // 365 if d1 and d2 else 0
                eq_nom, par_nom = "N/A", "N/A"
                if a[8]:
                    eq_info = c.execute("SELECT e.nom_equipe, p.nom FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id WHERE e.id=?", (a[8],)).fetchone()
                    if eq_info: eq_nom, par_nom = eq_info[0], eq_info[1]
                elif a[9]:
                    par_info = c.execute("SELECT nom FROM paroisses WHERE id=?", (a[9],)).fetchone()
                    if par_info: par_nom = par_info[0]

                header = f"📌 {a[2]} {a[3]} ({a[0]} / {a[1] or '—'}) – {afficher_situation(a[4])} – {duree} an(s)"
                with st.expander(header):
                    st.write(f"**Paroisse :** {par_nom} | {eq_nom}")
                    st.write(f"**Ajouté par :** {a[10] or 'Inconnu'}")
                    if a[7]: st.write(f"**Commentaire :** {a[7]}")

    elif menu == "🗑️ Réinitialiser":
        st.markdown('<h2 style="color:#1A237E;">🗑️ RÉINITIALISATION COMPLÈTE</h2>', unsafe_allow_html=True)
        st.error("⚠️ ACTION IRRÉVERSIBLE ! Tout sera détruit : paroisses, équipes, membres, présences, abonnements, archives, agenda ET contenu de l'Espace Spirituel.")
        with st.expander("🔴 Cliquez pour réinitialiser"):
            confirmation = st.text_input("Tapez 'SUPPRIMER' pour confirmer")
            if confirmation == "SUPPRIMER":
                # Fichiers Cloudinary supprimés AVANT la purge SQL
                for (photo,) in c.execute("SELECT photo_path FROM membres WHERE photo_path IS NOT NULL").fetchall():
                    supprimer_photo(photo)
                for (affiche,) in c.execute("SELECT affiche_url FROM evenements WHERE affiche_url IS NOT NULL").fetchall():
                    supprimer_photo(affiche)
                for img_url, fic_url in c.execute("SELECT image_url, fichier_url FROM espace_spirituel").fetchall():
                    if img_url: supprimer_photo(img_url)
                    if fic_url: supprimer_photo(fic_url)

                if os.path.exists("photos"): shutil.rmtree("photos")

                c.execute("DELETE FROM suivi_presences")
                c.execute("DELETE FROM evenement_equipes")
                c.execute("DELETE FROM evenements")
                c.execute("DELETE FROM agenda")
                c.execute("DELETE FROM periodes_cloturees")
                c.execute("DELETE FROM abonnements")
                c.execute("DELETE FROM archives")
                c.execute("DELETE FROM espace_spirituel")
                c.execute("DELETE FROM membres")
                c.execute("DELETE FROM equipes")
                c.execute("DELETE FROM paroisses")
                c.execute("DELETE FROM utilisateurs WHERE role != 'diocese'")
                commit_and_sync()
                st.session_state["flash_success"] = "Toutes les données ont été supprimées. 🗑️"
                st.rerun()
