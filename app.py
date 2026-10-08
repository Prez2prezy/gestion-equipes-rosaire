import os
import streamlit as st
from streamlit.components.v1 import html as _comp_html
from database import c, commit_and_sync
from services import (hash_password, verifier_mot_de_passe,
                      migrer_hash_si_legacy, definir_mot_de_passe,
                      creer_token_session, verifier_token_session,
                      supprimer_token_session)

# --- Configuration de la page ---
st.set_page_config(page_title="Gestionnaire des Équipes du Rosaire - Diocèse de Grand-Bassam", layout="wide")

# --- INTERCEPTION DES LIENS SPECIAUX ---
params = st.query_params

# Utilisation de .get() qui est la méthode moderne et fiable de Streamlit
espace_val = params.get("espace", None)
matloc_val = params.get("matloc", None)
event_val = params.get("e", None)

if espace_val:
    # Au cas où Streamlit renvoie une liste au lieu d'une chaîne
    if isinstance(espace_val, list): espace_val = espace_val[0]
    if isinstance(matloc_val, list): matloc_val = matloc_val[0]
    
    from views.view_espace_membre import show_espace_membre
    show_espace_membre(matloc_val)
    st.stop()
    
elif event_val:
    if isinstance(event_val, list): event_val = event_val[0]
    from components import afficher_page_reponse_membre
    afficher_page_reponse_membre(event_val)
    st.stop()

# --- CSS personnalisé ---
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF !important; }
    .main > div { background-color: #FFFFFF !important; }
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #1A237E !important; }
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

    /* TITRE PRINCIPAL (h1) */
    .stMarkdown h1, .stMarkdown h1 * {
        color: #1A237E !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        font-size: clamp(1rem, 3vw, 2rem) !important;
    }

    /* TITRES DE SECTIONS (h2) */
    .stMarkdown h2 {
        color: #1A237E !important;
        font-size: 1.4rem !important;
    }

    /* SOUS-TITRES (h3) */
    .stMarkdown h3, .stMarkdown h3 * {
        color: #1A237E !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        font-size: clamp(0.8rem, 4vw, 1.2rem) !important;
        margin-bottom: 5px !important;
    }
    
    /* BLOC D'INFORMATIONS */
    .custom-info-box {
        font-size: 0.9rem;
        color: #1A237E;
        margin-bottom: 40px !important;
        line-height: 1.6;
    }

    /* Donne de l'air au bouton "Modifier" (expanders) */
    .streamlit-expander {
        margin-top: 20px !important;
    }

    /* ✅ RÉDUIRE LA TAILLE DES INDICATEURS (st.metric) */
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem !important;
    }
    
    /* RÈGLES POUR LES PETITS ÉCRANS */
    @media (max-width: 768px) {
        .stMarkdown p, .stText {
            font-size: 0.9rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)


def afficher_logo():
    # Créer le dossier s'il n'existe pas
    if not os.path.exists("images"):
        try:
            os.makedirs("images")
        except Exception:
            pass
    
    logo_path = os.path.join("images", "logo.png")
    if os.path.exists(logo_path):
        try:
            st.sidebar.image(logo_path, width="stretch")
        except Exception:
            st.sidebar.caption("⚡ Erreur de chargement du logo")
    
    st.sidebar.markdown("---\n#### 🏛️ DIOCÈSE DE GRAND-BASSAM\n---")

# --- SESSION PERSISTANTE : rester connecté malgré le rafraîchissement ---
if 'logged_in' not in st.session_state:
    _tok = st.query_params.get("t")
    if isinstance(_tok, list):
        _tok = _tok[0] if _tok else None
    if _tok:
        _user = verifier_token_session(_tok)
        if _user:
            st.session_state.update({
                'logged_in': True, 'user_id': _user[0], 'username': _user[1],
                'role': _user[3], 'diocese_id': _user[4], 'paroisse_id': _user[5],
                'equipe_id': _user[6]
            })
            # Restaurer la rubrique où l'utilisateur se trouvait avant le F5
            if _user[7]:
                _cle_menu = {"diocese": "nav_dio", "paroisse": "nav_par",
                             "equipe": "nav_eq"}.get(_user[3])
                if _cle_menu:
                    st.session_state[_cle_menu] = _user[7]
                st.session_state["_menu_sync"] = _user[7]
        else:
            # Jeton inconnu ou expiré : on le retire de l'URL
            try:
                del st.query_params["t"]
            except Exception:
                pass

# --- AUTH ---
if 'logged_in' not in st.session_state:
    afficher_logo()

    st.caption("🔒 Application réservée aux gestionnaires autorisés.")
    with st.expander("📜 Mentions Légales & Confidentialité"):
        st.markdown("""
        **Responsable de traitement :** Diocèse de Grand-Bassam.

        **Finalité :** Gestion administrative, spirituelle et logistique des membres des équipes du Rosaire (contacts, présences, abonnements, photos).

        **Données collectées :** Nom, prénom, date de naissance, numéro WhatsApp, photo d'identité.

        **Durée de conservation :** Les données sont conservées tant que le membre est actif, puis archivées. Elles sont supprimées 3 ans après le départ définitif.

        **Vos droits :** Vous pouvez demander au responsable de votre équipe de modifier ou supprimer vos informations en lui envoyant un message WhatsApp.

        *Conformément aux principes de protection des données personnelles.*
        """)

    st.sidebar.title("🔐 Connexion")

    # PARADE AUTOFILL (v2) : le gestionnaire de mots de passe remplit les champs
    # sans déclencher l'événement que Streamlit écoute. On notifie Streamlit de
    # TOUTE valeur présente au branchement (autofill déjà effectué) puis de tout
    # changement ultérieur sans événement.
    _comp_html("""
        <script>
        (function(){
          function notifier(f){
            try{
              var natif = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
              natif.call(f, f.value);
            }catch(e){}
            f.dispatchEvent(new Event('input', {bubbles:true}));
            f.dispatchEvent(new Event('change', {bubbles:true}));
          }
          var essais = 0;
          var t = setInterval(function(){
            essais++;
            try {
              var d = window.parent.document;
              var zone = d.querySelector('[data-testid="stSidebar"]') || d;
              var ins = zone.querySelectorAll('input[type="text"], input[type="password"]');
              for(var i=0;i<ins.length;i++){
                var f = ins[i];
                if(f.dataset.pf77 === undefined){
                  f.dataset.pf77 = f.value || '';
                  if(f.value){ notifier(f); }
                  f.addEventListener('input', function(){ this.dataset.pf77 = this.value; });
                } else if(f.value !== (f.dataset.pf77 || '')){
                  notifier(f);
                  f.dataset.pf77 = f.value;
                }
              }
            } catch(e) {}
            if(essais > 600){ clearInterval(t); }
          }, 300);
        })();
        </script>
    """, height=0)

    u = st.sidebar.text_input("Utilisateur", key="login_user")
    p = st.sidebar.text_input("Mot de passe", type="password", key="login_pass")
    if st.sidebar.button("Se connecter"):
        row = c.execute("SELECT id, username, password, role, diocese_id, paroisse_id, equipe_id FROM utilisateurs WHERE username=?",
                        ((u or "").strip(),)).fetchone()
        if row and verifier_mot_de_passe(p or "", row[2]):
            migrer_hash_si_legacy(row[0], row[2], p or "")
            st.session_state.update({
                'logged_in': True, 'user_id': row[0], 'username': row[1],
                'role': row[3], 'diocese_id': row[4], 'paroisse_id': row[5], 'equipe_id': row[6]
            })
            # On force le menu de navigation sur la PREMIÈRE rubrique du rôle
            _entrees = {"diocese": ("nav_dio", "🏛️ Voir diocèse"),
                        "paroisse": ("nav_par", "🏘️ Ma paroisse"),
                        "equipe": ("nav_eq", "👥 Mon équipe")}
            if row[3] in _entrees:
                _cle, _val = _entrees[row[3]]
                st.session_state[_cle] = _val
            # Session persistante : jeton dans l'URL → le rafraîchissement
            # ne déconnecte plus (30 jours, révoqué à la déconnexion)
            _menu_premier = st.session_state.get({"diocese": "nav_dio", "paroisse": "nav_par",
                                                  "equipe": "nav_eq"}.get(row[3]))
            st.query_params["t"] = creer_token_session(row[0], _menu_premier)
            st.rerun()
        else:
            st.sidebar.error("Identifiants incorrects.")

    # 🔑 Secours « mot de passe oublié » — placé APRÈS le bouton Se connecter
    _reset_token = None
    try:
        _reset_token = st.secrets.get("RESET_TOKEN")
    except Exception:
        pass
    if _reset_token:
        with st.sidebar.expander("🔑 Mot de passe oublié ?"):
            tok = st.text_input("Clé de secours", type="password", key="rst_tok")
            nu = st.text_input("Utilisateur", value="diocese", key="rst_user")
            np1 = st.text_input("Nouveau mot de passe", type="password", key="rst_pwd")
            if st.button("Réinitialiser"):
                if tok != _reset_token or not np1:
                    st.sidebar.error("Clé invalide ou mot de passe vide.")
                elif not c.execute("SELECT 1 FROM utilisateurs WHERE username=?", ((nu or "").strip(),)).fetchone():
                    st.sidebar.error("Utilisateur inconnu.")
                else:
                    c.execute("UPDATE utilisateurs SET password=? WHERE username=?",
                              (definir_mot_de_passe(np1), (nu or "").strip()))
                    commit_and_sync()
                    st.sidebar.success("Mot de passe réinitialisé ! Connectez-vous.")

    st.stop()

afficher_logo()
st.sidebar.success(f"Connecté : {st.session_state['username']}")
if st.sidebar.button("Déconnexion"):
    _tok = st.query_params.get("t")
    if isinstance(_tok, list):
        _tok = _tok[0] if _tok else None
    if _tok:
        supprimer_token_session(_tok)
    for k in list(st.session_state.keys()): del st.session_state[k]
    try:
        del st.query_params["t"]   # retire le jeton de l'URL
    except Exception:
        pass
    st.rerun()

st.markdown('<a href="#" style="text-decoration: none; color: inherit;"><h1 style="color:#1A237E; cursor: pointer;">📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE</h1></a>', unsafe_allow_html=True)
st.markdown("---")

# --- ROUTAGE MVC ---
if st.session_state['role'] == 'diocese':
    from views.view_diocese import show_diocese
    show_diocese()
elif st.session_state['role'] == 'paroisse':
    from views.view_paroisse import show_paroisse
    show_paroisse()
elif st.session_state['role'] == 'equipe':
    from views.view_equipe import show_equipe
    show_equipe()
elif st.session_state['role'] == 'communication':
    from views.view_communication import show_communication
    show_communication()
