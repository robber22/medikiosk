import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json

def get_db():
    if not firebase_admin._apps:
        firebase_creds = json.loads(st.secrets["FIREBASE_KEY_JSON"])
        cred = credentials.Certificate(firebase_creds)
        firebase_admin.initialize_app(cred)
    return firestore.client()