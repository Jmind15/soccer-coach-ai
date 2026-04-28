import streamlit as st
import google.generativeai as genai
import re
import time
from fpdf import FPDF # fpdf2 pour le support UTF-8 nativement
import io
import os # Pour récupérer la clé API de Render

# --- CONFIGURATION API (SÉCURISÉE) ---
# N'écrivez jamais votre clé API ici.
# Ce code va chercher la clé de manière sécurisée selon la plateforme.
API_KEY = None

# Plan A : Pour Streamlit Cloud
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
# Plan B : Pour Render (ou local .env)
elif "GEMINI_API_KEY" in os.environ:
    API_KEY = os.environ["GEMINI_API_KEY"]

if not API_KEY:
    st.error("⚠️ Clé API non configurée.")
    st.info("""
    **Comment configurer la clé API de manière sécurisée :**
    - **Streamlit Cloud :** Dans 'Advanced Settings > Secrets', ajoutez: `GEMINI_API_KEY = "VotreClefICI"`
    - **Render :** Dans 'Environment Variables', ajoutez Key: `GEMINI_API_KEY`, Value: `VotreClefICI`
    - **Local :** Créez un fichier `.env` ou un dossier `.streamlit/secrets.toml`
    """)
    st.stop()

genai.configure(api_key=API_KEY)

# Initialisation des modèles
model_text = genai.GenerativeModel('gemini-3-flash-preview')
model_img = genai.GenerativeModel('gemini-3.1-flash-image-preview') 

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Coach AI Pro - U13+",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style pour l'interface (Mobile & Web Friendly)
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; font-weight: bold; }
    .stDownloadButton>button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #28a745; color: white; }
    .workshop-block { border: 1px solid #ddd; border-radius: 12px; padding: 20px; margin-bottom: 25px; background-color: #f9f9f9; }
    @media (max-width: 600px) {
        .block-container { padding: 1rem; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- GESTION DE L'ÉTAT (SESSION STATE) ---
if 'full_session_plan' not in st.session_state:
    st.session_state.full_session_plan = ""
if 'workshops_data' not in st.session_state:
    st.session_state.workshops_data = []

# --- SIDEBAR : PARAMÈTRES ---
with st.sidebar:
    st.title("⚙️ Configuration")
    nb_joueurs = st.number_input("Nombre de joueurs", min_value=2, max_value=40, value=12)
    
    objectifs = [
        "Maîtrise Technique (Option B)",
        "Finition & Sang-froid",
        "Dribble & Percussion 1v1",
        "Transition Rapide (Attaque/Défense)",
        "Jeu de Possession",
        "Pressing & Récupération",
        "Défense de Zone",
        "Sortie de balle sous pression",
    ]
    focus = st.selectbox("Objectif principal", objectifs)
    
    st.divider()
    gen_all = st.button("🚀 GÉNÉRER LA SÉANCE")

# --- FONCTIONS UTILITAIRES ---

def generer_image_atelier(prompt_visuel):
    try:
        img_resp = model_img.generate_content(prompt_visuel)
        if img_resp.candidates and img_resp.candidates[0].content.parts:
            for part in img_resp.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    return part.inline_data.data
        return None
    except Exception:
        return None

def decouper_seance(texte_complet, num_players):
    pattern = r"(\d+\.\s*[^:\n]+):"
    segments = re.split(pattern, texte_complet)
    
    workshops = []
    if len(segments) > 1:
        st.session_state.full_session_plan = segments[0]

        for i in range(1, len(segments), 2):
            titre = segments[i].strip()
            texte = segments[i+1].strip() if i+1 < len(segments) else ""
            
            img_prompt = f"""
            A professional 2D soccer tactical diagram, top-down view, set on a green pitch. 
            Drill: '{titre}'.
            It MUST depict exactly {num_players} players (colored icons) 
            arranged specifically for this drill: {texte[:200]}...
            Include clear cones, goals, ball movement arrows.
            """
            
            workshop = {
                'titre': titre,
                'texte': texte,
                'img_prompt': img_prompt,
                'img_bytes': None
            }
            workshops.append(workshop)
            
    return workshops

def creer_pdf_seance(intro, ateliers, obj, joueurs):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, f"Séance de Soccer : {obj}", ln=True, align='C')
    pdf.set_font("Helvetica", 'I', 12)
    pdf.cell(0, 10, f"Effectif: {joueurs} joueurs", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Helvetica", size=11)
    # Remplacement basique des Markdown pour le PDF
    pdf.multi_cell(0, 6, intro.replace("**", "").replace("*", "-"))
    pdf.ln(10)
    
    for workshop in ateliers:
        pdf.add_page()
        pdf.set_font("Helvetica", 'B', 14)
        pdf.set_text_color(0, 123, 255) # Bleu
        pdf.cell(0, 10, workshop['titre'], ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=11)
        pdf.ln(2)
        pdf.multi_cell(0, 6, workshop['texte'].replace("**", "").replace("*", "-"))
        pdf.ln(5)
        if workshop['img_bytes']:
            img_file = io.BytesIO(workshop['img_bytes'])
            try:
                pdf.image(img_file, x=30, w=150)
                pdf.ln(5)
            except Exception:
                pass
    return bytes(pdf.output())

# --- LOGIQUE DE GÉNÉRATION ---
if gen_all:
    st.session_state.full_session_plan = ""
    st.session_state.workshops_data = [] 
    
    with st.spinner(f"Génération pour {nb_joueurs} joueurs..."):
        prompt_txt = f"""
        Coach expert UEFA. Crée une séance de soccer structurée pour {nb_joueurs} joueurs U13+.
        Objectif : {focus}.
        Structure: 1. Échauffement Dynamique:, 2. Atelier Technique:, 3. Jeu Tactique:, 4. Match à thème:.
        Décris précisément la mise en place pour {nb_joueurs} joueurs. Markdown français.
        """
        try:
            response_text = model_text.generate_content(prompt_txt).text
            st.session_state.workshops_data = decouper_seance(response_text, nb_joueurs)
            
            if st.session_state.workshops_data:
                progress_bar = st.progress(0)
                for i, workshop in enumerate(st.session_state.workshops_data):
                    workshop['img_bytes'] = generer_image_atelier(workshop['img_prompt'])
                    progress_bar.progress((i + 1) / len(st.session_state.workshops_data))
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"Erreur texte : {e}")

# --- ZONE PRINCIPALE ---
st.title("⚽ Coach AI Pro")

if st.session_state.workshops_data:
    if st.session_state.full_session_plan:
        st.markdown(st.session_state.full_session_plan)
        st.divider()
    for workshop in st.session_state.workshops_data:
        st.markdown(f'<div class="workshop-block">', unsafe_allow_html=True)
        col_txt, col_img = st.columns([3, 2])
        with col_txt:
            st.subheader(workshop['titre'])
            st.markdown(workshop['texte'])
        with col_img:
            if workshop['img_bytes']:
                st.image(workshop['img_bytes'])
        st.markdown('</div>', unsafe_allow_html=True)
    st.divider()
    st.subheader("📥 Exporter la séance")
    try:
        pdf_bytes = creer_pdf_seance(st.session_state.full_session_plan, st.session_state.workshops_data, focus, nb_joueurs)
        st.download_button(label="Télécharger en PDF (UTF-8)", data=pdf_bytes, file_name=f"seance_{focus}.pdf", mime="application/pdf")
    except Exception as e:
        st.error(f"Erreur PDF : {e}")
else:
    st.info("👋 Bienvenue Coach ! Configurez la séance à gauche.")

# --- FOOTER ---
st.caption("Mobile-Friendly | Gemini 3 & 3.1 & FPDF2")
