import streamlit as st
import base64
from config import DOCTORS
from core.utils import render_nicely


def render_doctor_flow(db):
    if st.session_state.step == "login":
        _login_screen()
    if st.session_state.step == "dashboard":
        _dashboard_screen(db)


def _login_screen():
    st.markdown("### 🔐 Doctor Login")
    username = st.selectbox("Your name", ["Select"] + list(DOCTORS.keys()))
    password = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True):
        if username != "Select" and DOCTORS.get(username) == password:
            st.session_state.doctor_name = username
            st.session_state.step = "dashboard"
            st.rerun()
        else:
            st.error("Incorrect username or password.")


def _dashboard_screen(db):
    st.markdown(f"### 👨‍⚕️ Welcome, {st.session_state.doctor_name}")
    st.markdown("#### Your patients:")

    docs = db.collection("patients").where("assigned_doctor", "==", st.session_state.doctor_name).stream()
    patients = [{**d.to_dict(), "id": d.id} for d in docs]

    if not patients:
        st.info("No patients waiting right now.")
    else:
        for p in patients:
            with st.expander(f"🧑 {p.get('name')} — Age {p.get('age')}"):
                st.write(f"**Phone:** {p.get('phone')}")
                st.write(f"**Chief complaint:** {p.get('chief_complaint')}")

                st.markdown("**AI Summary for Doctor:**")
                render_nicely(p.get("summary", {}))

                if p.get("prescription_data"):
                    st.markdown("**From uploaded document:**")
                    render_nicely(p.get("prescription_data"))

                if p.get("document_base64"):
                    img_bytes = base64.b64decode(p["document_base64"])
                    st.markdown("**Uploaded Document Photo:**")
                    st.image(img_bytes, use_container_width=True)
                    st.download_button(
                        "📥 Download Document Photo",
                        data=img_bytes,
                        file_name=f"{p.get('name','patient')}_document.jpg",
                        mime="image/jpeg",
                        key=f"dlimg_{p['id']}",
                    )

                lines = [
                    f"Patient: {p.get('name')}", f"Age: {p.get('age')}",
                    f"Gender: {p.get('gender')}", f"Phone: {p.get('phone')}",
                    "", f"Chief Complaint: {p.get('chief_complaint')}", "",
                    "--- AI Summary ---",
                ]
                for k, v in p.get("summary", {}).items():
                    if v:
                        lines.append(f"{k.replace('_',' ').title()}: {v}")
                if p.get("prescription_data"):
                    lines.append("")
                    lines.append("--- From Uploaded Document ---")
                    for k, v in p.get("prescription_data", {}).items():
                        if v:
                            lines.append(f"{k.replace('_',' ').title()}: {v}")
                summary_text = "\n".join(lines)

                st.download_button(
                    "📥 Download Summary Report",
                    data=summary_text,
                    file_name=f"{p.get('name','patient')}_summary.txt",
                    mime="text/plain",
                    key=f"dl_{p['id']}",
                )

    if st.button("Log out"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()