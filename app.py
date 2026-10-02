import streamlit as st
from core.ai_engine import init_gemini
from core.firebase_client import get_db
from screens.home import render_home
from screens.patient_screens import render_patient_flow
from screens.doctor_screens import render_doctor_flow

st.set_page_config(page_title="MediKiosk", layout="centered")

# ---------- MAKE EVERYTHING BIGGER AND EASIER TO READ ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Poppins', sans-serif !important;
    font-size: 20px !important;
}

.stApp {
    background: linear-gradient(160deg, #E8F6F3 0%, #FAFCFB 60%);
}

h1 {
    font-size: 3em !important;
    text-align: center;
    font-weight: 700 !important;
    background: linear-gradient(90deg, #0F9D8C, #1BC5A5);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

h3 {
    font-size: 1.7em !important;
    color: #1A2E35;
    font-weight: 600 !important;
}

.stButton button {
    font-size: 22px !important;
    height: 3.4em;
    padding: 0.4em 1.2em;
    border-radius: 16px !important;
    border: none !important;
    background: linear-gradient(135deg, #0F9D8C, #1BC5A5) !important;
    color: white !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(15, 157, 140, 0.35);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.stButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(15, 157, 140, 0.45);
}

.stTextInput input, .stTextArea textarea, .stNumberInput input {
    font-size: 20px !important;
    border-radius: 12px !important;
    border: 2px solid #CFE8E3 !important;
    padding: 0.6em !important;
}
.stSelectbox div[data-baseweb="select"] {
    border-radius: 12px !important;
    font-size: 20px !important;
}

.stAlert {
    border-radius: 14px !important;
    font-size: 19px !important;
}

.streamlit-expanderHeader {
    font-size: 20px !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    background-color: #F0F9F7 !important;
}
</style>
""", unsafe_allow_html=True)

init_gemini()
db = get_db()

if "role" not in st.session_state:
    st.session_state.role = None

render_home()

if st.session_state.role == "patient":
    render_patient_flow(db)

if st.session_state.role == "doctor":
    render_doctor_flow(db)