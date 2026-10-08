import re
import streamlit as st
import pandas as pd
import io
from datetime import date
from database import c, commit_and_sync
from services import (hash_password, generer_mot_de_passe, sauvegarder_photo, supprimer_photo,
                      archiver_membre, safe_date, afficher_situation, sans_accents, 
                      enregistrer_abonnement, verifier_abonnement, periode_affichage, 
                      generer_matricule_unique, get_periode_pastorale, lien_whatsapp, URL_ESPACE_SPIRITUEL,
                      synchroniser_menu_session, lire_menu_session)
from components import (ajouter_evenement_agenda, afficher_agenda_complet_universel, afficher_historique_suivi, 
                        afficher_whatsapp_tabs, widget_type_abonnement, afficher_etat_presences_globales)

def generer_identifiant_equipe(nom_paroisse, nom_commune, nom_equipe, paroisse_id):
    nom_propre = nom_paroisse.lower()
    motifs_exclus = [r"notre[\s\-]*dame", r"sainte?", r"st\.?", r"notre", r"dame", r"du\b", r"d'", r"l'", r"de\b"]
    for motif in motifs_exclus:
        nom_propre = re.sub(motif, "", nom_propre, flags=re.IGNORECASE)
    nom_propre = re.sub(r"[\s'\-]", "", nom_propre)
    prefixe_par = sans_accents(nom_propre[:3]) if nom_propre else "par"
    prefixe_com = sans_accents(nom_commune[:3])
    est_jeune = "jeune" in nom_equipe.lower()
    suffixe = "j" if est_jeune else "eq"
    base = f"{prefixe_par}{prefixe_com}{suffixe}"
    # Numérotation naturelle : (nombre d'équipes actuelles du même type) + 1
    if est_jeune:
        nb = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=? AND LOWER(nom_equipe) LIKE '%jeune%'", (paroisse_id,)).fetchone()[0]
    else:
        nb = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=? AND LOWER(nom_equipe) NOT LIKE '%jeune%'", (paroisse_id,)).fetchone()[0]
    n = nb + 1
    # Sécurité anti-crash : si ce numéro est déjà porté par un compte existant
    # (cas rare), on passe au suivant au lieu de provoquer une erreur SQL.
    while c.execute("SELECT 1 FROM utilisateurs WHERE username=?", (f"{base}{n}",)).fetchone():
        n += 1
    return f"{base}{n}".lower()

def get_max_membres(equipe_id):
    paroisse_info = c.execute("""
        SELECT p.nom, p.commune 
        FROM equipes e 
        JOIN paroisses p ON e.paroisse_id = p.id 
        WHERE e.id=?
    """, (equipe_id,)).fetchone()
    
    if paroisse_info:
        nom_paroisse = str(paroisse_info[0]).lower() 
        commune = str(paroisse_info[1]).lower()
        if "notre dame" in nom_paroisse and "assomption" in nom_paroisse and "koumassi" in commune:
            return 20
            
    return 12

def show_paroisse():
    pid = st.session_state['paroisse_id']
    # Migration douce : WhatsApp responsable PAROISSE + DIOCÈSE (idempotent,
    # silencieux — couvre aussi une base où le diocèse ne s'est pas encore
    # connecté depuis l'ajout de la colonne)
    for _tbl in ("paroisses", "diocese"):
        try:
            c.execute(f"SELECT whatsapp_responsable FROM {_tbl} LIMIT 1")
        except Exception:
            try:
                c.execute(f"ALTER TABLE {_tbl} ADD COLUMN whatsapp_responsable TEXT")
                commit_and_sync()
            except Exception:
                pass
    p_info = c.execute("SELECT nom, commune, ville, responsable, bureau, whatsapp_responsable FROM paroisses WHERE id=?", (pid,)).fetchone()
    if not p_info:
        st.error("Paroisse introuvable temporairement. Veuillez actualiser la page (F5).")
        return
    nom_p = p_info[0]
    
    _rubriques_par = ["🏘️ Ma paroisse", "👥 Mes équipes", "👤 Membres", "📊 Statistiques",
                      "📅 Abonnements", "📌 Suivi", "💬 WhatsApp", "📥 Export Excel", "📦 Archives"]
    if "nav_par" in st.session_state and st.session_state["nav_par"] not in _rubriques_par:
        del st.session_state["nav_par"]
    if "nav_par" not in st.session_state:
        _rub = lire_menu_session()
        if _rub and _rub in _rubriques_par:
            st.session_state["nav_par"] = _rub
            st.session_state["_menu_sync"] = _rub
    menu = st.sidebar.radio("Navigation", _rubriques_par, key="nav_par")
    synchroniser_menu_session(menu)

    if menu == "🏘️ Ma paroisse":
        st.markdown(f'<h2 style="color:#1A237E;">🏘️ {nom_p}</h2>', unsafe_allow_html=True)
        _affiche_wa = p_info[5] or "Non renseigné"
        st.markdown(f'<div class="custom-info-box">Commune : {p_info[1]}<br>Ville : {p_info[2]}<br><b>Responsable :</b> {p_info[3]}<br><b>Bureau :</b> {p_info[4]}<br><b>📱 WhatsApp du responsable :</b> {_affiche_wa}</div>', unsafe_allow_html=True)

        # Lien public de la paroisse (QR signé — le même que celui expédié au responsable)
        with st.expander("🔳 Mon lien & QR paroissial (pour les affiches)"):
            _url_signee = f"{URL_ESPACE_SPIRITUEL}/?espace=1&p={pid}"
            st.code(_url_signee)
            st.caption("Partagez ce lien (ou le QR téléchargeable côté diocèse, menu Gérer paroisses) sur vos affiches : chaque scan est compté à l'origine de la paroisse.")

        with st.expander("✏️ Modifier les informations"):
            c_edit1, c_edit2 = st.columns(2)
            with c_edit1:
                nr = st.text_input("Nouveau responsable", value=p_info[3])
                nwa = st.text_input("📱 WhatsApp du responsable (ex. 0700000000)", value=p_info[5] or "")
            with c_edit2:
                nb = st.text_area("Nouveau bureau", value=p_info[4])
            if st.button("💾 Enregistrer"):
                c.execute("UPDATE paroisses SET responsable=?, bureau=?, whatsapp_responsable=? WHERE id=?",
                          (nr, nb, nwa.strip() or None, pid))
                commit_and_sync(); st.success("Mis à jour !"); st.rerun()

        # NOUVEAU : Zone de réinitialisation de la paroisse
        with st.expander("⚠️ ZONE DANGEREUSE : Réinitialisation de la paroisse"):
            st.error("Cette action supprimera **définitivement** toutes les équipes, les membres et les accès de cette paroisse. Cette action est irréversible.")
            confirm_text = st.text_input("Pour confirmer, tapez le mot : SUPPRIMER")
            if st.button("🗑️ Réinitialiser la paroisse", type="secondary") and confirm_text == "SUPPRIMER":
                c.execute("DELETE FROM membres WHERE paroisse_id=?", (pid,))
                c.execute("DELETE FROM equipes WHERE paroisse_id=?", (pid,))
                c.execute("DELETE FROM utilisateurs WHERE paroisse_id=? AND role='equipe'", (pid,))
                commit_and_sync()
                st.success("Paroisse entièrement réinitialisée. Vous pouvez recréer vos équipes.")
                st.rerun()

    elif menu == "👥 Mes équipes":
        st.markdown(f'<h2 style="color:#1A237E;">👥 Équipes de {nom_p}</h2>', unsafe_allow_html=True)
        if st.button("➕ Créer une équipe"): st.session_state['show_eq_form'] = True
        if st.session_state.get('show_eq_form'):
            with st.form("f_eq"):
                nom_eq, resp, bur = st.text_input("Nom de l'équipe"), st.text_input("Responsable"), st.text_area("Bureau")
                c1, c2 = st.columns(2)
                if c1.form_submit_button("❌ Annuler"): del st.session_state['show_eq_form']; st.rerun()
                if c2.form_submit_button("✅ Créer") and nom_eq and resp:
                    doublon_resp = c.execute('SELECT e.nom_equipe, p.nom FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id WHERE e.responsable = ?', (resp,)).fetchone()
                    if doublon_resp: st.error(f"❌ Responsable déjà assigné à '{doublon_resp[0]}' ({doublon_resp[1]}).")
                    elif c.execute("SELECT id FROM equipes WHERE nom_equipe=? AND paroisse_id=?", (nom_eq, pid)).fetchone(): st.error(f"❌ Équipe '{nom_eq}' existe déjà !")
                    else:
                        identifiant = generer_identifiant_equipe(p_info[0], p_info[1], nom_eq, pid)
                        mdp = generer_mot_de_passe()
                        c.execute("INSERT INTO equipes (nom_equipe, responsable, bureau, paroisse_id) VALUES (?,?,?,?)", (nom_eq, resp, bur, pid))
                        eid = c.lastrowid
                        c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id, equipe_id) VALUES (?,?,?,?,?)", (identifiant, hash_password(mdp), "equipe", pid, eid))
                        commit_and_sync(); del st.session_state['show_eq_form']
                        st.session_state['new_equipe_info'] = {'nom': nom_eq, 'user': identifiant, 'mdp': mdp}; st.rerun()
        
        if st.session_state.get('new_equipe_info'):
            info = st.session_state['new_equipe_info']
            st.success(f"✅ '{info['nom']}' créée !")
            st.markdown(f"<div style='background:#e8f5e9;padding:20px;border-radius:10px;border:1px solid #c8e6c9;'><p><strong>🔑 Identifiant :</strong> <code style='color:#d84315;font-size:1.2rem;'>{info['user']}</code></p><p><strong>🔒 Mot de passe :</strong> <code style='color:#d84315;font-size:1.2rem;'>{info['mdp']}</code></p></div>", unsafe_allow_html=True)
            if st.button("OK"): del st.session_state['new_equipe_info']; st.rerun()

        st.markdown("---")
        for eq in c.execute("SELECT id, nom_equipe, responsable, bureau FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall():
            eq_id, eq_nom, eq_resp, eq_bur = eq
            nb_m = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eq_id,)).fetchone()[0]
            
            with st.expander(f"📌 {eq_nom} - {eq_resp} ({nb_m}/{get_max_membres(eq_id)} membres)"):
                if not st.session_state.get(f'edit_eq_par_{eq_id}'):
                    if st.button("✏️ Modifier l'équipe", key=f"btn_edit_eq_par_{eq_id}"):
                        st.session_state[f'edit_eq_par_{eq_id}'] = True
                        st.rerun()
                
                if st.session_state.get(f'edit_eq_par_{eq_id}'):
                    if st.button("🔑 Réinitialiser le mot de passe de connexion", key=f"reset_pwd_eq_par_{eq_id}"):
                        new_mdp = generer_mot_de_passe()
                        c.execute("UPDATE utilisateurs SET password=? WHERE equipe_id=? AND role='equipe'", (hash_password(new_mdp), eq_id))
                        commit_and_sync()
                        st.session_state[f'new_pwd_eq_par_{eq_id}'] = new_mdp
                    
                    if st.session_state.get(f'new_pwd_eq_par_{eq_id}'):
                        st.markdown(f"<div style='background:#fff3e0;padding:15px;border-radius:10px;border:1px solid #ffe0b2;'>🔑 Nouveau mot de passe de l'équipe : <code style='color:#d84315;font-size:1.2rem;'>{st.session_state[f'new_pwd_eq_par_{eq_id}']}</code></div>", unsafe_allow_html=True)
                        
                    with st.form(f"form_edit_eq_par_{eq_id}"):
                        new_nom = st.text_input("Nom de l'équipe", value=eq_nom, key=f"edit_nom_{eq_id}")
                        new_resp = st.text_input("Responsable", value=eq_resp, key=f"edit_resp_{eq_id}")
                        new_bur = st.text_area("Bureau", value=eq_bur, key=f"edit_bur_{eq_id}")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.form_submit_button("💾 Enregistrer"):
                                c.execute("UPDATE equipes SET nom_equipe=?, responsable=?, bureau=? WHERE id=?", (new_nom, new_resp, new_bur, eq_id))
                                commit_and_sync()
                                if f'new_pwd_eq_par_{eq_id}' in st.session_state: del st.session_state[f'new_pwd_eq_par_{eq_id}']
                                del st.session_state[f'edit_eq_par_{eq_id}']
                                st.success("Équipe et accès mis à jour !")
                                st.rerun()
                        with c2:
                            if st.form_submit_button("❌ Annuler"):
                                if f'new_pwd_eq_par_{eq_id}' in st.session_state: del st.session_state[f'new_pwd_eq_par_{eq_id}']
                                del st.session_state[f'edit_eq_par_{eq_id}']
                                st.rerun()
                else:
                    st.write(f"**Bureau :** {eq_bur}")
                    user_info = c.execute("SELECT username FROM utilisateurs WHERE equipe_id=? AND role='equipe'", (eq_id,)).fetchone()
                    if user_info: st.code(f"🔑 Connexion : {user_info[0]}")
                
                # NOUVEAU : Bouton de suppression d'équipe
                st.markdown("---")
                if nb_m == 0:
                    if st.button(f"🗑️ Supprimer définitivement l'équipe {eq_nom}", key=f"del_eq_{eq_id}", type="secondary"):
                        c.execute("DELETE FROM utilisateurs WHERE equipe_id=?", (eq_id,))
                        c.execute("DELETE FROM equipes WHERE id=?", (eq_id,))
                        commit_and_sync()
                        st.success(f"Équipe {eq_nom} supprimée.")
                        st.rerun()
                else:
                    st.info("💡 Pour supprimer cette équipe, vous devez d'abord archiver ou transférer ses membres.")
                
                if st.button(f"📋 Voir les membres de {eq_nom}", key=f"btn_membres_eq_{eq_id}"):
                    st.session_state['show_membres_equipe'] = eq_id if st.session_state.get('show_membres_equipe') != eq_id else None
                    st.rerun()
                                
                if st.session_state.get('show_membres_equipe') == eq_id:
                    mbrs = c.execute("SELECT matloc, matricule, nom, prenom, whatsapp, numero_meditation, date_adhesion FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eq_id,)).fetchall()
                    if mbrs:
                        df = pd.DataFrame(mbrs, columns=["MatLoc", "Matricule", "Nom", "Prénom", "WhatsApp", "N° méditation", "Date adhésion"]); df.index=df.index+1
                        st.dataframe(df, width="stretch")

    elif menu == "👤 Membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres - {nom_p}</h2>', unsafe_allow_html=True)        
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        if not equipes: st.warning("Créez d'abord une équipe.")
        else:
            eq_dict = {e[1]: e[0] for e in equipes}
            choix = st.selectbox("Équipe", list(eq_dict.keys()))
            eid = eq_dict[choix]
            max_m = get_max_membres(eid)
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchone()[0]
            st.info(f"{nb}/{max_m} membres")
            
            if nb < max_m and st.button("➕ Ajouter un membre"): st.session_state['form_mbr_par'] = "ajout"
            if st.session_state.get('form_mbr_par') == "ajout":
                with st.form("aj_mbr"):
                    c1, c2 = st.columns(2)
                    with c1: n, p = st.text_input("Nom"), st.text_input("Prénom")
                    dn = st.date_input("Naissance", min_value=date(1950, 1, 1), max_value=date.today())
                    with c2: w, nm = st.text_input("WhatsApp"), st.text_input("N° méd.", max_chars=2)
                    ph = st.file_uploader("Photo", ['jpg','png','webp'])
                    # COHABITATION : lien imgbb prioritaire, sinon fichier
                    ph_lien = st.text_input("…ou lien de photo (https://... — ex. imgbb : i.ibb.co/…)")
                    da = st.date_input("Date d'adhésion", min_value=date(1950, 1, 1), max_value=date.today(), value=date.today())

                    if st.form_submit_button("✅ Ajouter"):
                        if not (n and p):
                            st.error("Le nom et le prénom sont requis.")
                        elif ph_lien.strip() and not ph_lien.strip().startswith("http"):
                            st.error("Le lien de photo doit commencer par https://")
                        else:
                            mat = generer_matricule_unique()
                            c.execute("""INSERT INTO membres (matloc, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id, statut, numero_meditation, matricule) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (mat, n, p, dn.isoformat(), w, da.isoformat(), pid, eid, 'actif', nm, mat))
                            mid = c.lastrowid
                            # COHABITATION : lien imgbb prioritaire, sinon upload Cloudinary/local
                            photo_finale = ph_lien.strip() if ph_lien.strip() else (sauvegarder_photo(ph, mat) if ph else None)
                            if photo_finale:
                                c.execute("UPDATE membres SET photo_path=? WHERE id=?", (photo_finale, mid))
                            commit_and_sync(); del st.session_state['form_mbr_par']; st.success(f"Ajouté ! {mat}"); st.rerun()
            for m in c.execute("SELECT id, matloc, nom, prenom, whatsapp, photo_path, date_adhesion, numero_meditation, matricule FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchall():
                with st.expander(f"{m[2]} {m[3]} - {m[1]}"):
                    c1, c2 = st.columns([3,1])
                    c1.write(f"👥 **Équipe :** {choix}\n💬 {m[4]} | 📅 {m[6]} | Matricule: {m[8] or '-'}")
                    if m[5]: c1.image(m[5], width=80)
                    with c2:
                        if st.button("📦 Archiver", key=f"btn_arch_p_{m[0]}"): st.session_state[f'form_arch_p_{m[0]}'] = True
                    
                    if st.session_state.get(f'form_arch_p_{m[0]}'):
                        with st.form(f"fa_arch_{m[0]}"):
                            sit = st.radio("Situation", ["Transféré", "Déplacé", "Radié", "Défunt"])
                            ac1, ac2 = st.columns(2)
                            with ac1: ad = st.number_input("Année début", 2000, date.today().year, date.today().year)
                            with ac2: af = st.number_input("Année fin", 2000, date.today().year+5, date.today().year+1)
                            com = st.text_area("Commentaire")
                            
                            equipe_destination = None
                            if sit == "Transféré":
                                equipes_dispo = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? AND id != ?", (pid, eid)).fetchall()
                                if equipes_dispo:
                                    dest_dict = {e[1]: e[0] for e in equipes_dispo}
                                    dest_nom = st.selectbox("Équipe d'accueil", list(dest_dict.keys()))
                                    equipe_destination = dest_dict[dest_nom]
                                    nb_dest = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (equipe_destination,)).fetchone()[0]
                                    if nb_dest >= get_max_membres(equipe_destination): st.error(f"Impossible : l'équipe {dest_nom} est pleine.")
                                else: st.warning("Aucune autre équipe.")

                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("❌ Annuler"): del st.session_state[f'form_arch_p_{m[0]}']; st.rerun()
                            with col2:
                                if st.form_submit_button("✅ Confirmer"):
                                    if af <= ad: st.error("Année invalide.")
                                    elif sit == "Transféré" and not equipe_destination: st.error("Sélectionnez une équipe.")
                                    elif sit == "Transféré":
                                        if c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (equipe_destination,)).fetchone()[0] >= get_max_membres(equipe_destination):
                                            st.error("Impossible : l'équipe d'accueil est pleine.")
                                        else:
                                            c.execute("UPDATE membres SET statut='archive' WHERE id=?", (m[0],))
                                            c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id) VALUES (?, 'Transféré', ?, ?, ?, ?, ?, ?, ?, ?)''', (m[0], date(ad, 9, 1).isoformat(), date(af, 9, 1).isoformat(), f"Transféré vers {dest_nom}", st.session_state['user_id'], st.session_state['username'], 'paroisse', pid, eid))
                                            c.execute("UPDATE membres SET equipe_id=?, statut='actif' WHERE id=?", (equipe_destination, m[0]))
                                            commit_and_sync()
                                            del st.session_state[f'form_arch_p_{m[0]}']
                                            st.success(f"Membre transféré vers {dest_nom} !")
                                            st.rerun()
                                    else:
                                        archiver_membre(m[0], sit, ad, af, com, st.session_state['user_id'], st.session_state['username'], 'paroisse', pid, eid)
                                        del st.session_state[f'form_arch_p_{m[0]}']; st.success("Archivé !"); st.rerun()

    elif menu == "📊 Statistiques":
        st.markdown(f'<h2 style="color:#1A237E;">📊 Statistiques - {nom_p}</h2>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.metric("Équipes", c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0])
        c2.metric("Membres actifs", c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0])

    elif menu == "📅 Abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 État des abonnements - {nom_p}</h2>', unsafe_allow_html=True)
        
        annee_pastorale_en_cours = get_periode_pastorale()[0]
        annee = st.number_input("Année de début de période", min_value=2020, max_value=annee_pastorale_en_cours, value=annee_pastorale_en_cours, step=1)
        st.write(f"**Période observée :** {periode_affichage(annee)}")
        
        stats_p = c.execute('''SELECT COUNT(m.id), SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) FROM membres m LEFT JOIN abonnements a ON m.id = a.membre_id AND a.annee_debut=? WHERE m.paroisse_id=? AND m.statut='actif' ''', (annee, annee, pid)).fetchone()
        # v-pb1 — blindage : Turso peut renvoyer les agrégats en TEXTE
        total_p = int(stats_p[0]) if stats_p and stats_p[0] else 0
        payes_p = int(stats_p[1]) if stats_p and stats_p[1] else 0
        
        if total_p > 0:
            pourcent_str = str(round(payes_p / total_p * 100)) + "%"
        else:
            pourcent_str = "0%"
        
        c1, c2 = st.columns(2)
        c1.metric("Total membres (Paroisse)", total_p)
        c2.metric("Abonnements enregistrés", payes_p)
        st.caption(f"📊 **Taux de recouvrement :** {pourcent_str}")
        
        st.markdown("---")
        
        for eq in c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall():
            stats_eq = c.execute('''SELECT COUNT(m.id) as total, SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes FROM membres m LEFT JOIN abonnements a ON m.id = a.membre_id AND a.annee_debut=? WHERE m.equipe_id=? AND m.statut='actif' GROUP BY m.equipe_id''', (annee, annee, eq[0])).fetchone()
            
            if stats_eq:
                # v-pb1 — blindage identique
                total_eq = int(stats_eq[0]) if stats_eq[0] else 0
                payes_eq = int(stats_eq[1]) if stats_eq[1] else 0
                
                if total_eq > 0:
                    pourcent_eq_str = str(round(payes_eq / total_eq * 100)) + "%"
                else:
                    pourcent_eq_str = "0%"
                
                with st.expander(f"📌 {eq[1]} - {payes_eq}/{total_eq} à jour ({pourcent_eq_str})"):
                    non_payes = c.execute('''SELECT m.nom, m.prenom, m.matricule FROM membres m WHERE m.equipe_id=? AND m.statut='actif' AND m.id NOT IN (SELECT membre_id FROM abonnements WHERE annee_debut=? AND statut='paye') ORDER BY m.nom''', (eq[0], annee)).fetchall()
                    
                    if non_payes:
                        st.write("❌ **En attente :**")
                        for np in non_payes:
                            st.write("- " + np[0] + " " + np[1] + " (`" + np[2] + "`)")
                    else: 
                        st.success("✅ Tous à jour !")

    elif menu == "📌 Suivi":
        st.markdown(f'<h2 style="color:#1A237E;">📌 Suivi et Agenda - {nom_p}</h2>', unsafe_allow_html=True)
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        
        if not equipes:
            st.warning("Aucune équipe créée dans cette paroisse. Vous ne pouvez pas gérer le suivi.")
        else:
            tab_avenir, tab_passe, tab_etat = st.tabs(["📅 Agenda", "📝 Vie de prière des équipes", "📊 Engagement spirituel"])
            
            with tab_avenir:
                ajouter_evenement_agenda(paroisse_id=pid, auteur_nom=st.session_state['username'])
                st.markdown("---")
                afficher_agenda_complet_universel(paroisse_id=pid)

            with tab_passe:
                st.markdown("### 📋 Faire le point des équipes")
                eq_dict = {eq[1]: eq[0] for eq in equipes}
                choix_eq = st.selectbox("Sélectionnez l'équipe à consulter", list(eq_dict.keys()), key="suivi_paroisse_eq")
                eid = eq_dict[choix_eq]
                
                types_evenements = ["Tous", "Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage", "Réunion", "Autre"]
                filtre_type = st.selectbox("Filtrer par type d'évènement", types_evenements, key="filtre_hist_par")
                
                afficher_historique_suivi(equipe_id=eid, filtre_type=filtre_type)
                
            with tab_etat:
                eq_dict2 = {eq[1]: eq[0] for eq in equipes}
                choix_eq2 = st.selectbox("Sélectionnez l'équipe pour voir le bilan", list(eq_dict2.keys()), key="etat_paroisse_eq")
                eid2 = eq_dict2[choix_eq2]
                afficher_etat_presences_globales(equipe_id=eid2)

    elif menu == "💬 WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Messages WhatsApp - {nom_p}</h2>', unsafe_allow_html=True)
        afficher_whatsapp_tabs(equipe_id=None)

    elif menu == "📥 Export Excel":
        st.markdown(f'<h2 style="color:#1A237E;">📥 Export des membres - {nom_p}</h2>', unsafe_allow_html=True)
        mbrs = c.execute('''SELECT m.matloc, m.nom, m.prenom, m.date_naissance, m.whatsapp, m.date_adhesion, e.nom_equipe FROM membres m JOIN equipes e ON m.equipe_id=e.id WHERE m.paroisse_id=? AND m.statut='actif' ''', (pid,)).fetchall()
        if mbrs:
            df = pd.DataFrame(mbrs, columns=["MatLoc", "Nom", "Prénom", "Naissance", "WhatsApp", "Adhésion", "Équipe"])
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
            out.seek(0); st.download_button("📥 Télécharger", out, f"membres_{nom_p}.xlsx")
    
    elif menu == "📦 Archives":
        st.markdown(f'<h2 style="color:#1A237E; font-size: 1.4rem;">📦 Archives - {nom_p}</h2>', unsafe_allow_html=True)
        archives = c.execute('''SELECT m.matloc, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire, a.equipe_id, a.auteur_nom FROM archives a JOIN membres m ON a.membre_id = m.id WHERE a.paroisse_id = ? ORDER BY a.date_fin DESC''', (pid,)).fetchall()
        if not archives: st.info("Aucune archive.")
        else:
            for a in archives:
                d1, d2 = safe_date(a[4]), safe_date(a[5])
                duree = (d2 - d1).days // 365 if d1 and d2 else 0
                eq_nom = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (a[7],)).fetchone()[0] if a[7] else "N/A"
                with st.expander(f"{a[1]} {a[2]} ({a[0]}) – {afficher_situation(a[3])} – {duree} an(s) ({eq_nom})"):
                    st.write(f"Ajouté par : {a[8] or 'Inconnu'}")
                    if a[6]: st.write(f"Commentaire : {a[6]}")
