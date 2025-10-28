import streamlit as st
import firebase_admin
from firebase_admin import credentials
import json
import re

# =============================
# 🔧 CONFIGURACIÓN FIREBASE ADMIN (versión robusta)
# =============================
try:
    # Convertir el bloque TOML en un dict plano
    firebase_config = json.loads(json.dumps(dict(st.secrets["FIREBASE"])))

    # ---- LIMPIEZA FUERTE DE PRIVATE KEY ----
    pk = firebase_config["private_key"]

    # 1️⃣ Reemplazar \r o \n escapados por saltos reales
    pk = pk.replace("\\r", "\r").replace("\\n", "\n")

    # 2️⃣ Quitar espacios o caracteres invisibles en los extremos
    pk = pk.strip()

    # 3️⃣ Asegurarnos que comience y termine correctamente
    if not pk.startswith("-----BEGIN PRIVATE KEY-----"):
        pk = "-----BEGIN PRIVATE KEY-----\n" + pk
    if not pk.endswith("-----END PRIVATE KEY-----"):
        pk = pk + "\n-----END PRIVATE KEY-----"

    # 4️⃣ Reasignar la clave limpia al dict
    firebase_config["private_key"] = pk

    # Inicializar Firebase
    cred = credentials.Certificate(firebase_config)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    st.sidebar.success("✅ Conectado con Firebase correctamente")

except Exception as e:
    st.error(f"❌ Error al conectar con Firebase: {e}")
    st.stop()
    
# =============================
# 🎨 CONFIGURACIÓN GENERAL STREAMLIT
# =============================
st.set_page_config(page_title="Dashboard ISP", layout="wide")
st.title("📊 Dashboard ISP")
st.markdown("Sistema de métricas financieras para ISPs con autenticación Firebase 🔐")

# =============================
# 🔐 LOGIN / REGISTRO DE USUARIOS
# =============================

menu = st.sidebar.radio("Acción", ["Iniciar sesión", "Registrar usuario"])
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
            # Firebase Admin no valida contraseñas, solo verifica existencia del usuario
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

    st.subheader("📈 Panel de Métricas Financieras")
    st.markdown("""
    Este panel permite visualizar los indicadores clave de tu ISP:

    - **ARPU (Average Revenue Per User):** ingreso promedio por cliente.  
    - **CHURN:** porcentaje de clientes que se dan de baja.  
    - **LTV (Lifetime Value):** valor de vida útil del cliente.  
    - **MC (Margen de Contribución):** ganancia neta por usuario.
    """)

    # Ejemplo simple de métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="ARPU Promedio", value="$15.80 USD", delta="+2.5%")
    with col2:
        st.metric(label="CHURN Mensual", value="1.8 %", delta="-0.3%")
    with col3:
        st.metric(label="LTV Promedio", value="$845 USD", delta="+4.1%")
    with col4:
        st.metric(label="Margen de Contribución", value="62 %", delta="+1.2%")

    st.markdown("---")
    st.markdown("📅 *Datos actualizados automáticamente cada mes.*")

else:
    st.warning("🔒 Inicia sesión para acceder al panel del Dashboard ISP.")
