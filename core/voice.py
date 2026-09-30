import streamlit as st
import io
from gtts import gTTS
from config import LANG_CODES
from core.ai_engine import transcribe_audio

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