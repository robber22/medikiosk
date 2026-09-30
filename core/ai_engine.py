import streamlit as st
import google.generativeai as genai
from config import FALLBACK_MODELS

def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

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

def transcribe_audio(audio_bytes, language, extra_instruction=""):
    audio_part = {"mime_type": "audio/wav", "data": audio_bytes}
    prompt = (
        f"The patient is speaking in {language}. Listen to this audio and "
        f"write down exactly what they said, translated into simple English. "
        f"{extra_instruction} Reply with ONLY the sentence, nothing else."
    )
    resp = safe_generate([prompt, audio_part])
    return resp.text.strip()

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