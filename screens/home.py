import streamlit as st

def render_home():
    st.markdown("<h1 style='text-align:center;'>🏥 MediKiosk</h1>", unsafe_allow_html=True)

    if st.session_state.role is None:
        st.markdown("### Who are you?")
        col1, col2 = st.columns(2)
        if col1.button("🧑 I am a Patient", use_container_width=True):
            st.session_state.role = "patient"
            st.session_state.step = 1
            st.rerun()
        if col2.button("👨‍⚕️ I am a Doctor", use_container_width=True):
            st.session_state.role = "doctor"
            st.session_state.step = "login"
            st.rerun()
        st.stop()