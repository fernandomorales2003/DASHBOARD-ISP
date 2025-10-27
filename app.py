import streamlit as st
import json
import os

# Intenta cargar firebase config desde st.secrets (Streamlit Cloud)
if "apiKey" in st.secrets:
    firebase_config = {
        "apiKey": st.secrets["apiKey"],
        "authDomain": st.secrets["authDomain"],
        "projectId": st.secrets["projectId"],
        "storageBucket": st.secrets["storageBucket"],
        "messagingSenderId": st.secrets["messagingSenderId"],
        "appId": st.secrets["appId"]
    }
else:
    # Para pruebas locales: cargar firebase_config.json si existe
    if os.path.exists("firebase_config.json"):
        with open("firebase_config.json", "r") as f:
            firebase_config = json.load(f)
    else:
        firebase_config = None

st.title("Demo Dashboard ISP")

if not firebase_config:
    st.warning("No se encontró configuración de Firebase. Para deploy subí las claves a Streamlit Secrets o creá firebase_config.json localmente.")
else:
    st.write("Firebase configurado correctamente (datos cargados).")
    # Aquí inicializar pyrebase / firebase_admin según lo que uses
    # import pyrebase
    # firebase = pyrebase.initialize_app(firebase_config)
    # auth = firebase.auth()

# Ejemplo simple de pantalla (sustituir por tu lógica)
st.subheader("Prueba de interfaz")
arpu = st.number_input("ARPU (USD)", value=16.0)
churn = st.number_input("CHURN (%)", value=2.0)
mc = st.number_input("MC (%)", value=60.0)
cac = st.number_input("CAC (USD)", value=150.0)

if st.button("Calcular LTV"):
    churn_rate = churn / 100
    mc_rate = mc / 100
    if churn_rate <= 0:
        st.error("Churn debe ser > 0")
    else:
        ltv = (arpu * mc_rate) / churn_rate
        st.success(f"LTV estimado: {ltv:.2f} USD")
