import streamlit as st
import json
from config import DOCTORS
from core.ai_engine import safe_generate, get_translated_instruction
from core.voice import voice_input_widget, speak_once
from core.utils import render_nicely, compress_image_to_base64
from firebase_admin import firestore


STEP_PROGRESS = {1: 0.2, 2: 0.4, "2b": 0.6, 3: 0.8, 4: 1.0}
STEP_LABELS = {1: "Step 1 of 5: Your Details", 2: "Step 2 of 5: Tell Us What's Wrong",
               "2b": "Step 3 of 5: Follow-up Questions", 3: "Step 4 of 5: Documents",
               4: "Step 5 of 5: Done!"}

def render_patient_flow(db):
    current = st.session_state.step
    if current in STEP_PROGRESS:
        st.progress(STEP_PROGRESS[current], text=STEP_LABELS[current])

    if current == 1:
        _screen1_details()
    if current == 2:
        _screen2_speak()
    if current == "2b":
        _screen2b_followup()
    if current == 3:
        _screen3_documents(db)
    if current == 4:
        _screen4_thankyou()


def _screen1_details():
    st.markdown("### 📝 Please fill in your details")
    name = st.text_input("Full name")
    age = st.number_input("Age", min_value=0, max_value=120, step=1)
    gender = st.selectbox("Gender", ["Select", "Male", "Female", "Other"])
    phone = st.text_input("Phone number")
    doctor_choice = st.selectbox("Which doctor are you here to see?", ["Select"] + list(DOCTORS.keys()))
    language = st.selectbox("Preferred language", ["English", "Hindi", "Tamil", "Bengali", "Marathi", "Telugu"])

    if st.button("Continue →", use_container_width=True):
        if name and gender != "Select" and doctor_choice != "Select":
            st.session_state.patient_info = {
                "name": name, "age": age, "gender": gender,
                "phone": phone, "assigned_doctor": doctor_choice,
                "language": language,
            }
            st.session_state.step = 2
            st.rerun()
        else:
            st.warning("Please fill in your name, gender, and choose a doctor before continuing.")


def _screen2_speak():
    patient_language = st.session_state.patient_info["language"]
    instruction = get_translated_instruction(
        "screen2",
        "Please tell us what is wrong. Tap the microphone and speak, or type your answer.",
        patient_language,
    )
    st.markdown("### 🎤 Tell us what's wrong")
    st.info(instruction)
    speak_once("screen2_instr", instruction, patient_language)

    if "chief_complaint" not in st.session_state:
        st.session_state.chief_complaint = ""

    result = voice_input_widget("mic_step2", patient_language)
    if result:
        st.session_state.chief_complaint = result

    typed = st.text_area("Or type here:", value=st.session_state.chief_complaint)

    if st.button("Continue →", use_container_width=True) and typed:
        st.session_state.chief_complaint = typed
        st.session_state.qa_history = []
        st.session_state.step = "2b"
        st.rerun()


def _screen2b_followup():
    st.markdown("### 🤖 A few quick follow-up questions")
    patient_language = st.session_state.patient_info["language"]

    SYSTEM_PROMPT = f"""You are a calm, simple clinical intake assistant.
    The patient said (translated to English): "{st.session_state.chief_complaint}".
    The patient's preferred language is: {patient_language}.

    Ask ONE short, simple follow-up question at a time (onset, location, severity,
    what makes it better/worse). No medical jargon. Write the question text itself
    in {patient_language}, using very simple everyday words.

    Always reply with STRICT JSON only, nothing else, in exactly this shape:
    {{"status": "QUESTION", "question": "the question written in {patient_language}"}}

    If the patient mentions a RED FLAG symptom (crushing chest pain, breathlessness,
    sudden weakness, coughing blood, severe bleeding, unconsciousness), reply with:
    {{"status": "RED_FLAG", "question": ""}}

    After about 4 questions, reply with:
    {{"status": "COMPLETE", "question": ""}}
    """

    if not st.session_state.qa_history:
        resp = safe_generate(SYSTEM_PROMPT)
        st.session_state.qa_history.append({"role": "ai", "text": resp.text})

    last_raw = st.session_state.qa_history[-1]["text"]
    try:
        cleaned = last_raw.replace("```json", "").replace("```", "").strip()
        last_parsed = json.loads(cleaned)
    except Exception:
        last_parsed = {"status": "QUESTION", "question": last_raw}

    if last_parsed.get("status") == "RED_FLAG":
        st.error("🚨 Please go to the Emergency desk immediately.")
        st.stop()
    elif last_parsed.get("status") == "COMPLETE":
        st.session_state.step = 3
        st.rerun()
    else:
        question_text = last_parsed.get("question", "")
        st.write(f"**AI:** {question_text}")
        speak_once(f"q_{len(st.session_state.qa_history)}", question_text, patient_language)

        voice_answer = voice_input_widget(f"mic_qa_{len(st.session_state.qa_history)}", patient_language)
        typed_answer = st.text_input("Or type your answer:", value=voice_answer or "")

        if st.button("Submit") and typed_answer:
            st.session_state.qa_history.append({"role": "patient", "text": typed_answer})
            convo = "\n".join(f"{m['role']}: {m['text']}" for m in st.session_state.qa_history)
            resp = safe_generate(SYSTEM_PROMPT + f"\nConversation so far:\n{convo}\nAsk next question or finish.")
            st.session_state.qa_history.append({"role": "ai", "text": resp.text})
            st.rerun()


def _screen3_documents(db):
    st.markdown("### 📄 Do you have old prescriptions or lab reports? (optional)")

    if "prescription_data" not in st.session_state:
        st.session_state.prescription_data = None
    if "document_base64" not in st.session_state:
        st.session_state.document_base64 = None

    tab_upload, tab_camera = st.tabs(["📁 Upload a saved photo", "📷 Scan with camera"])
    uploaded = None
    with tab_upload:
        file_upload = st.file_uploader("Upload a photo", type=["jpg", "jpeg", "png"])
        if file_upload:
            uploaded = file_upload
    with tab_camera:
        camera_photo = st.camera_input("Take a photo of the document")
        if camera_photo:
            uploaded = camera_photo

    if uploaded:
        from PIL import Image
        img = Image.open(uploaded)
        st.image(img, use_container_width=True)
        if st.button("Extract information"):
            with st.spinner("Reading the document..."):
                prompt = """Read this handwritten/printed medical prescription or lab report
                carefully. Extract STRICT JSON only, no markdown:
                {"document_date": "the date written on the document in DD-MM-YYYY format, or 'not found' if no date is visible",
                 "medicines": [{"name":"","dosage":"","frequency":""}],
                 "diagnoses": [],
                 "lab_values": [{"test":"","value":"","flag":"normal/abnormal"}]}
                If a field is unclear, write "unclear" for that field."""
                resp = safe_generate([prompt, img])
                try:
                    cleaned = resp.text.replace("```json", "").replace("```", "").strip()
                    st.session_state.prescription_data = json.loads(cleaned)
                    st.success("Extracted!")
                    render_nicely(st.session_state.prescription_data)
                except Exception:
                    st.write(resp.text)

            try:
                st.session_state.document_base64 = compress_image_to_base64(img)
            except Exception as e:
                st.warning(f"Could not save a copy of the document ({e}). Extracted info is still saved.")

    if st.button("Finish & Send to Doctor →", use_container_width=True):
        convo = "\n".join(f"{m['role']}: {m['text']}" for m in st.session_state.get("qa_history", []))
        summary_prompt = f"""Turn this into a clinical summary. Chief complaint:
        {st.session_state.chief_complaint}. Conversation: {convo}.
        Prior documents: {st.session_state.prescription_data}.
        Output STRICT JSON: {{"chief_complaint":"","hpi":"","medications":"",
        "summary_for_doctor":""}}"""
        resp = safe_generate(summary_prompt)
        try:
            cleaned = resp.text.replace("```json", "").replace("```", "").strip()
            summary = json.loads(cleaned)
        except Exception:
            summary = {"summary_for_doctor": resp.text}

        record = {
            **st.session_state.patient_info,
            "chief_complaint": st.session_state.chief_complaint,
            "qa_history": st.session_state.get("qa_history", []),
            "prescription_data": st.session_state.prescription_data,
            "document_base64": st.session_state.document_base64,
            "summary": summary,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
        db.collection("patients").add(record)

        st.session_state.step = 4
        st.rerun()


def _screen4_thankyou():
    st.success("✅ Thank you! Your details have been sent to your doctor.")
    st.markdown(f"Please take a seat and wait to be called for **{st.session_state.patient_info['assigned_doctor']}**.")
    if st.button("Start over"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()