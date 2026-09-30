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
html, body, [class*="css"]  { font-size: 20px !important; }
.stButton button { font-size: 22px !important; height: 3.2em; padding: 0.4em 1em; }
h1 { font-size: 3em !important; }
h3 { font-size: 1.7em !important; }
.stTextInput input, .stTextArea textarea, .stSelectbox div { font-size: 20px !important; }
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