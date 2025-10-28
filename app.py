import time
import json
import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials

# =============================
# 🔧 FIREBASE ADMIN (service account) — ya comprobado que te funciona
# =============================
def init_firebase_admin():
    if not firebase_admin._apps:
        # Convertir secrets a dict limpio
        firebase_config = json.loads(json.dumps(dict(st.secrets["FIREBASE"])))

        # Inicializar Admin SDK
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)

# =============================
# 🔑 ENDPOINTS REST AUTH
# =============================
def firebase_rest_endpoints():
    # apiKey desde secrets
    try:
        api_key = st.secrets["FIREBASE_WEB"]["apiKey"]
    except KeyError:
        st.error("Falta [FIREBASE_WEB].apiKey en tus Secrets. Agregalo en Settings → Secrets.")
        st.stop()

    base_auth = "https://identitytoolkit.googleapis.com/v1"
    base_secure = "https://securetoken.googleapis.com/v1"
    return {
        "sign_in": f"{base_auth}/accounts:signInWithPassword?key={api_key}",
        "sign_up": f"{base_auth}/accounts:signUp?key={api_key}",
        "refresh": f"{base_secure}/token?key={api_key}",
    }

# =============================
# 🧰 HELPERS: sign up / sign in / refresh
# =============================
def firebase_sign_up(email: str, password: str):
    endpoints = firebase_rest_endpoints()
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r = requests.post(endpoints["sign_up"], json=payload, timeout=15)
    return r.json()

def firebase_sign_in(email: str, password: str):
    endpoints = firebase_rest_endpoints()
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r = requests.post(endpoints["sign_in"], json=payload, timeout=15)
    return r.json()

def firebase_refresh_id_token(refresh_token: str):
    endpoints = firebase_rest_endpoints()
    payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    r = requests.post(endpoints["refresh"], data=payload, timeout=15)
    return r.json()

def store_session(auth_response: dict):
    """
    Guarda sesión en st.session_state:
    - id_token (JWT)
    - refresh_token
    - local_id (uid)
    - expires_at (epoch)
    """
    st.session_state["auth"] = {
        "id_token": auth_response.get("idToken"),
        "refresh_token": auth_response.get("refreshToken"),
        "local_id": auth_response.get("localId"),
        "email": auth_response.get("email"),
        # expiresIn llega como string de segundos
        "expires_at": time.time() + int(auth_response.get("expiresIn", "3600")) - 30,  # 30s margen
    }

def ensure_session_fresh():
    """
    Si el token expira en < 30s, lo refresca con refresh_token.
    """
    if "auth" not in st.session_state:
        return

    auth = st.session_state["auth"]
    if not auth or "refresh_token" not in auth:
        return

    if time.time() < auth.get("expires_at", 0):
        return  # aún válido

    # refrescar
    data = firebase_refresh_id_token(auth["refresh_token"])
    if "error" in data:
        # sesión inválida
        st.session_state.pop("auth", None)
        st.warning("La sesión expiró. Volvé a iniciar sesión.")
        return

    # Actualizar tokens
    st.session_state["auth"]["id_token"] = data.get("id_token")
    st.session_state["auth"]["refresh_token"] = data.get("refresh_token", auth["refresh_token"])
    st.session_state["auth"]["expires_at"] = time.time() + int(data.get("expires_in", "3600")) - 30

# =============================
# 🎨 UI
# =============================
st.set_page_config(page_title="Dashboard ISP", layout="wide")
st.title("📊 Dashboard ISP — Login con Firebase (REST Auth)")

# Inicializar Admin SDK (para futuras operaciones server-side si las necesitás)
try:
    init_firebase_admin()
    st.sidebar.success("✅ Firebase Admin inicializado")
except Exception as e:
    st.sidebar.warning(f"Firebase Admin no es requerido para el login, pero falló: {e}")

# ---- Sidebar: Login / Registro ----
mode = st.sidebar.radio("Acción", ["Iniciar sesión", "Registrar usuario"])

with st.form("auth_form", clear_on_submit=False):
    email = st.text_input("Correo electrónico")
    password = st.text_input("Contraseña", type="password")
    submitted = st.form_submit_button("Continuar")

    if submitted:
        if not email or not password:
            st.error("Completá email y contraseña.")
        else:
            if mode == "Registrar usuario":
                res = firebase_sign_up(email, password)
                if "error" in res:
                    msg = res["error"]["message"]
                    st.error(f"❌ Error al registrar: {msg}")
                else:
                    st.success("✅ Usuario creado. Ahora podés iniciar sesión.")
            else:
                res = firebase_sign_in(email, password)
                if "error" in res:
                    msg = res["error"]["message"]
                    st.error(f"❌ Error al iniciar sesión: {msg}")
                else:
                    store_session(res)
                    st.success(f"✅ Bienvenido {res.get('email') or email}")

# ---- Mantener sesión fresca ----
ensure_session_fresh()

# ---- Estado de sesión ----
if "auth" in st.session_state and st.session_state["auth"].get("id_token"):
    user_email = st.session_state["auth"].get("email") or email
    st.sidebar.success(f"Sesión: {user_email}")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.pop("auth", None)
        st.rerun()

    # =============================
    # 👤 Dashboard protegido
    # =============================
    st.subheader("📈 Panel de Métricas Financieras")
    st.markdown("""
    - **ARPU**  
    - **CHURN**  
    - **LTV**  
    - **Margen de Contribución**
    """)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ARPU", "$15.80", "+2.5%")
    col2.metric("CHURN", "1.8 %", "-0.3%")
    col3.metric("LTV", "$845", "+4.1%")
    col4.metric("MC", "62 %", "+1.2%")

else:
    st.info("🔒 Iniciá sesión o registrate para acceder al dashboard.")
