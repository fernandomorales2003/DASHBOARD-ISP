import streamlit as st
import pyrebase
import json
import os

# Configuración desde Streamlit Secrets
firebaseConfig = {
    "apiKey": st.secrets["apiKey"],
    "authDomain": st.secrets["authDomain"],
    "projectId": st.secrets["projectId"],
    "storageBucket": st.secrets["storageBucket"],
    "messagingSenderId": st.secrets["messagingSenderId"],
    "appId": st.secrets["appId"],
    "measurementId": st.secrets["measurementId"]
}

# Inicializar Firebase
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

# Interfaz simple de login
st.title("🔐 Dashboard ISP - Login")

choice = st.sidebar.selectbox("Acción", ["Login", "Registrarse"])

email = st.text_input("Correo electrónico")
password = st.text_input("Contraseña", type="password")

if choice == "Login":
    if st.button("Ingresar"):
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.success("✅ Login exitoso")
            st.session_state["user"] = email
        except Exception as e:
            st.error(f"❌ Error de login: {e}")

elif choice == "Registrarse":
    if st.button("Crear cuenta"):
        try:
            user = auth.create_user_with_email_and_password(email, password)
            st.success("✅ Cuenta creada correctamente, ahora podés ingresar.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# Si ya hay un usuario logueado
if "user" in st.session_state:
    st.sidebar.success(f"Bienvenido {st.session_state['user']}")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.clear()
        st.rerun()


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
