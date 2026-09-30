# 🏥 MediKiosk

An AI-powered clinical intake kiosk built for Indian hospital OPDs, where doctors
often get only 2–5 minutes per patient. MediKiosk lets patients describe their
symptoms by voice in their own language, answers AI-guided follow-up questions,
and scans old prescriptions — all before they even sit down with the doctor.

## Features
- No patient login — walk up and use, in Hindi, Tamil, Bengali, Marathi, Telugu, or English
- Voice-guided intake with text-to-speech questions in the patient's own language
- AI-generated adaptive follow-up questions (not a fixed script)
- Emergency red-flag detection
- Camera or file upload to digitize old prescriptions and lab reports
- Doctor login, with each doctor seeing only their own assigned patients
- Downloadable AI summary reports and document photos for doctors

## Tech Stack
- Streamlit (Python) — web app
- Google Gemini — conversational AI, document OCR, translation
- gTTS — text-to-speech in regional languages
- Firebase Firestore — shared patient/doctor database

## Project Structure
- config.py — doctors list, AI model list, language codes
- core/ — AI engine, voice, database, formatting helpers
- screens/ — home, patient flow, doctor flow
- app.py — entry point


## Team
Built by Team MAX.