import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth
import json
import streamlit as st

st.write("🔍 Keys visibles en st.secrets:", list(st.secrets.keys()))

# =============================
# 🔧 CONFIGURACIÓN FIREBASE ADMIN
# =============================
try:
    cred = credentials.Certificate(st.secrets["FIREBASE"])
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    st.sidebar.success("✅ Conectado con Firebase correctamente")
except Exception as e:
    st.error("❌ Error al conectar con Firebase. Verifica tus Secrets.")
    st.stop()

# =============================
# 🎨 CONFIGURACIÓN GENERAL STREAMLIT
# =============================
st.set_page_config(page_title="Dashboard ISP", layout="centered")

st.title("📊 Dashboard ISP")
st.markdown("Sistema de métricas financieras para ISPs con autenticación Firebase 🔐")

# =============================
# 🔐 LOGIN / REGISTRO DE USUARIOS
# =============================

menu = st.sidebar.selectbox("Acción", ["Iniciar sesión", "Registrar usuario"])
email = st.text_input("Correo electrónico")
password = st.text_input("Contraseña", type="password")

if menu == "Registrar usuario":
    if st.button("Crear cuenta"):
        try:
            user = auth.create_user(email=email, password=password)
            st.success(f"✅ Usuario {email} creado correctamente.")
        except Exception as e:
            st.error(f"❌ Error al crear usuario: {e}")

elif menu == "Iniciar sesión":
    if st.button("Iniciar sesión"):
        try:
            # Nota: Firebase Admin no permite login directo con password (solo manejo de cuentas).
            # Para login real de usuarios finales deberíamos usar Firebase REST API o Pyrebase.
            user = auth.get_user_by_email(email)
            st.session_state["user"] = email
            st.success(f"✅ Bienvenido {email}")
        except Exception as e:
            st.error("❌ Usuario no encontrado o error de autenticación.")

# =============================
# 👤 DASHBOARD ISP (SOLO USUARIOS LOGUEADOS)
# =============================
if "user" in st.session_state:
    st.sidebar.success(f"Sesión activa: {st.session_state['user']}")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.clear()
        st.rerun()

    st.subheader("📈 Panel de Métricas")
    st.write("Bienvenido al panel del Dashboard ISP.")
    st.write("Aquí podrás visualizar tus indicadores financieros clave:")

    # Ejemplo simple de métricas
    st.metric(label="ARPU Promedio", value="$15.80 USD")
    st.metric(label="CHURN Mensual", value="1.8 %")
    st.metric(label="LTV Promedio", value="$845 USD")
else:
    st.warning("🔒 Inicia sesión para acceder al panel del Dashboard ISP.")
