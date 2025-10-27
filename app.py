import streamlit as st
import pyrebase

# ==========================
# 🔧 CONFIGURACIÓN FIREBASE
# ==========================
firebaseConfig = {
    "apiKey": st.secrets["apiKey"],
    "authDomain": st.secrets["authDomain"],
    "projectId": st.secrets["projectId"],
    "storageBucket": st.secrets["storageBucket"],
    "messagingSenderId": st.secrets["messagingSenderId"],
    "appId": st.secrets["appId"],
    "measurementId": st.secrets["measurementId"]
}

# Inicializar conexión con Firebase
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

# ==========================
# 🎨 INTERFAZ STREAMLIT
# ==========================
st.set_page_config(page_title="Dashboard ISP", layout="centered")

st.title("📊 Dashboard ISP")
st.markdown("Sistema de métricas e indicadores financieros para ISPs.")

# Sidebar: login / registro
menu = st.sidebar.selectbox("Acción", ["🔑 Iniciar Sesión", "📝 Crear Cuenta"])

email = st.text_input("Correo electrónico")
password = st.text_input("Contraseña", type="password")

# ==========================
# 🔐 LOGIN
# ==========================
if menu == "🔑 Iniciar Sesión":
    if st.button("Ingresar"):
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.session_state["user"] = email
            st.success(f"✅ Bienvenido {email}")
        except Exception as e:
            st.error("❌ Error al iniciar sesión. Verifica los datos.")

# ==========================
# 📝 REGISTRO
# ==========================
elif menu == "📝 Crear Cuenta":
    if st.button("Registrarse"):
        try:
            user = auth.create_user_with_email_and_password(email, password)
            st.success("✅ Usuario creado correctamente. Ahora podés ingresar.")
        except Exception as e:
            st.error("❌ Error al crear usuario. Puede que ya exista o la contraseña sea débil.")

# ==========================
# 👤 SESIÓN ACTIVA
# ==========================
if "user" in st.session_state:
    st.sidebar.success(f"Sesión activa: {st.session_state['user']}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()

    # ==========================
    # 🧭 CONTENIDO DEL DASHBOARD
    # ==========================
    st.subheader("📈 Panel principal")
    st.markdown("""
    Bienvenido al panel del **Dashboard ISP**.  
    Aquí podrás visualizar tus **métricas financieras**, como:
    - ARPU  
    - CHURN  
    - LTV  
    - Margen de Contribución  
    """)

    # Ejemplo de métrica (para test)
    st.metric(label="ARPU Promedio", value="$15.8 USD")
    st.metric(label="CHURN Mensual", value="1.8 %")
    st.metric(label="LTV Promedio", value="$845 USD")
else:
    st.warning("🔒 Inicia sesión para acceder al Dashboard.")
