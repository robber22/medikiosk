import streamlit as st
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import json, os, io, base64
from gtts import gTTS

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

# ---------- CONNECT TO GEMINI ----------
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ---------- CONNECT TO FIREBASE (only once) ----------
# NOTE: we do NOT use Firebase Storage (it now requires a paid Blaze plan / credit card).
# Instead, uploaded document photos are compressed and saved directly inside Firestore,
# which stays completely free.
if not firebase_admin._apps:
    firebase_creds = json.loads(st.secrets["FIREBASE_KEY_JSON"])
    cred = credentials.Certificate(firebase_creds)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------- LIST OF DOCTORS (edit these names/passwords as you like) ----------
DOCTORS = {
    "Dr. Sharma": "sharma123",
    "Dr. Verma": "verma123",
    "Dr. Iyer": "iyer123",
}

# ---------- MODELS TO TRY, IN ORDER (lite models first — much higher free daily quota) ----------
FALLBACK_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3.6-flash",
]

def safe_generate(parts):
    last_error = None
    for model_name in FALLBACK_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            return model.generate_content(parts)
        except Exception as e:
            last_error = e
            continue
    raise last_error

# ---------- REUSABLE HELPER: turn any recorded audio into English text ----------
def transcribe_audio(audio_bytes, language, extra_instruction=""):
    audio_part = {"mime_type": "audio/wav", "data": audio_bytes}
    prompt = (
        f"The patient is speaking in {language}. Listen to this audio and "
        f"write down exactly what they said, translated into simple English. "
        f"{extra_instruction} Reply with ONLY the sentence, nothing else."
    )
    resp = safe_generate([prompt, audio_part])
    return resp.text.strip()

# ---------- REUSABLE HELPER: a mic button that returns transcribed text ----------
def voice_input_widget(key, language):
    st.caption("🎤 Tap the microphone icon, speak, then tap it again to stop — it will not cut you off automatically.")
    audio_value = st.audio_input("Record your answer", key=key, label_visibility="collapsed")
    if audio_value:
        audio_bytes = audio_value.getvalue()
        st.audio(audio_bytes)
        with st.spinner("Understanding..."):
            try:
                return transcribe_audio(audio_bytes, language)
            except Exception as e:
                st.warning(f"Voice tool had an issue ({e}). Please type instead below.")
    return None

# ---------- REUSABLE HELPER: speak a sentence out loud in the patient's language ----------
LANG_CODES = {"English": "en", "Hindi": "hi", "Tamil": "ta", "Bengali": "bn", "Marathi": "mr", "Telugu": "te"}

def speak_text(text, language):
    try:
        lang_code = LANG_CODES.get(language, "en")
        tts = gTTS(text=text, lang=lang_code)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        st.audio(buf.read(), format="audio/mp3", autoplay=True)
    except Exception as e:
        st.caption(f"(Voice guidance unavailable right now: {e})")

def speak_once(key, text, language):
    flag = f"spoken_{key}"
    if not st.session_state.get(flag):
        speak_text(text, language)
        st.session_state[flag] = True

def get_translated_instruction(key, english_text, language):
    cache_key = f"instr_{key}_{language}"
    if cache_key not in st.session_state:
        if language == "English":
            st.session_state[cache_key] = english_text
        else:
            try:
                resp = safe_generate(f"Translate this into simple, everyday {language}. Reply with ONLY the translation: {english_text}")
                st.session_state[cache_key] = resp.text.strip()
            except Exception:
                st.session_state[cache_key] = english_text
    return st.session_state[cache_key]

# ---------- REUSABLE HELPER: show a dictionary as clean bullet points, not raw code ----------
def render_nicely(d):
    if not d:
        st.caption("Nothing extracted.")
        return
    for k, v in d.items():
        if v in (None, "", "unclear", []):
            continue
        label = k.replace("_", " ").title()
        if isinstance(v, list):
            if not v:
                continue
            st.markdown(f"**{label}:**")
            for item in v:
                if isinstance(item, dict):
                    line = " — ".join(str(x) for x in item.values() if x)
                    st.markdown(f"- {line}")
                else:
                    st.markdown(f"- {item}")
        else:
            st.markdown(f"**{label}:** {v}")

# ---------- REUSABLE HELPER: shrink a photo so it fits comfortably inside Firestore ----------
def compress_image_to_base64(pil_image, max_width=800, quality=60):
    img = pil_image.convert("RGB")
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

# ============================================================
# HOME SCREEN
# ============================================================
if "role" not in st.session_state:
    st.session_state.role = None

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

# ============================================================
# PATIENT PATH
# ============================================================
if st.session_state.role == "patient":

    # ---------------- Screen 1: Details form ----------------
    if st.session_state.step == 1:
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

    # ---------------- Screen 2: Speak the main problem ----------------
    if st.session_state.step == 2:
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

    # ---------------- Screen 2b: AI follow-up questions ----------------
    if st.session_state.step == "2b":
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

    # ---------------- Screen 3: Upload or scan old documents ----------------
    if st.session_state.step == 3:
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

                # Save a small compressed copy directly in the free database, so the
                # doctor can view/download it later — no paid storage service needed.
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

    # ---------------- Screen 4: Thank you ----------------
    if st.session_state.step == 4:
        st.success("✅ Thank you! Your details have been sent to your doctor.")
        st.markdown(f"Please take a seat and wait to be called for **{st.session_state.patient_info['assigned_doctor']}**.")
        if st.button("Start over"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# ============================================================
# DOCTOR PATH
# ============================================================
if st.session_state.role == "doctor":

    if st.session_state.step == "login":
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

    if st.session_state.step == "dashboard":
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

                    # Build a plain-text version of everything for the summary download button
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