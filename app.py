import os
import time
import json
import requests
import streamlit as st
import pandas as pd
import altair as alt
import firebase_admin
from firebase_admin import credentials
from datetime import datetime

st.set_page_config(page_title="Dashboard ISP — Login & Planes", layout="wide")

# =====================================
# FIREBASE ADMIN INIT
# =====================================
def init_firebase_admin():
    if not firebase_admin._apps:
        sa = json.loads(json.dumps(dict(st.secrets["FIREBASE"])))
        cred = credentials.Certificate(sa)
        firebase_admin.initialize_app(cred)

# =====================================
# FIRESTORE REST HELPER
# =====================================
def firestore_request(method, path, data=None):
    init_firebase_admin()
    project_id = st.secrets["FIREBASE"]["project_id"]
    base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
    url = f"{base_url}/{path}"
    headers = {"Content-Type": "application/json"}
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        elif method == "PATCH":
            r = requests.patch(url, headers=headers, json=data, timeout=10)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=data, timeout=10)
        else:
            return None
        if r.status_code not in (200, 201):
            st.error(f"❌ Firestore error {r.status_code}: {r.text}")
            return None
        return r.json()
    except Exception as e:
        st.error(f"❌ Error de conexión Firestore REST: {e}")
        return None

# =====================================
# FIREBASE AUTH REST API
# =====================================
def endpoints():
    api_key = st.secrets["FIREBASE_WEB"]["apiKey"]
    base_auth = "https://identitytoolkit.googleapis.com/v1"
    return {
        "sign_in": f"{base_auth}/accounts:signInWithPassword?key={api_key}",
        "sign_up": f"{base_auth}/accounts:signUp?key={api_key}",
    }

def sign_in(email, password):
    return requests.post(endpoints()["sign_in"], json={"email": email, "password": password, "returnSecureToken": True}).json()

def sign_up(email, password):
    return requests.post(endpoints()["sign_up"], json={"email": email, "password": password, "returnSecureToken": True}).json()

def store_session(res):
    st.session_state["auth"] = {
        "id_token": res.get("idToken"),
        "uid": res.get("localId"),
        "email": res.get("email")
    }

# =====================================
# LOGIN / REGISTRO
# =====================================
st.title("📊 Dashboard ISP — Acceso seguro")

mode = st.sidebar.radio("Acción", ["Iniciar sesión", "Registrar usuario"])
with st.sidebar.form("auth_form"):
    email = st.text_input("Correo electrónico")
    password = st.text_input("Contraseña", type="password")
    submitted = st.form_submit_button("Continuar")

    if submitted:
        if not email or not password:
            st.sidebar.error("Completá email y contraseña.")
        elif mode == "Registrar usuario":
            r = sign_up(email, password)
            if "error" in r:
                st.sidebar.error(r["error"]["message"])
            else:
                store_session(r)
                # Crear documento en Firestore
                uid = r["localId"]
                firestore_request("PATCH", f"users/{uid}", {
                    "fields": {
                        "email": {"stringValue": email},
                        "plan": {"stringValue": "free"},
                        "fecha_registro": {"integerValue": int(time.time())}
                    }
                })
                st.sidebar.success("✅ Usuario creado. Plan FREE asignado.")
        else:
            r = sign_in(email, password)
            if "error" in r:
                st.sidebar.error(r["error"]["message"])
            else:
                store_session(r)
                st.sidebar.success(f"Bienvenido {r.get('email')}")

if "auth" not in st.session_state:
    st.stop()

uid = st.session_state["auth"]["uid"]
email = st.session_state["auth"]["email"]

# =====================================
# OBTENER PLAN DEL USUARIO
# =====================================
r = firestore_request("GET", f"users/{uid}")
plan = "free"
if r and "fields" in r:
    plan = r["fields"].get("plan", {}).get("stringValue", "free")

st.sidebar.markdown(f"🧾 **Plan actual:** `{plan.upper()}`")

# =====================================
# FUNCIONALIDAD SEGÚN PLAN
# =====================================
if plan == "free":
    st.header("🌱 Versión FREE")
    st.info("Accedé a métricas básicas: ARPU, CHURN, LTV y Clientes.")
elif plan == "pro":
    st.header("🚀 Versión PRO")
    st.success("Accedés a todos los indicadores financieros y proyecciones.")
elif plan == "premium":
    st.header("💎 Versión PREMIUM")
    st.success("Acceso completo: métricas, comparativas, alertas y multiusuario.")

st.markdown("---")

# =====================================
# SIMULACIÓN DE DASHBOARD POR PLAN
# =====================================
if plan == "free":
    st.metric("ARPU", "$16.00", "+2% vs mes anterior")
    st.metric("CHURN", "2.5%")
    st.metric("Clientes actuales", "1,250")
    st.metric("LTV", "$350.00")
    st.warning("🔒 Funcionalidades avanzadas disponibles en PRO o PREMIUM")

elif plan == "pro":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ARPU", "$18.00", "+3%")
    c2.metric("CHURN", "1.8%")
    c3.metric("LTV", "$500.00")
    c4.metric("LTV/CAC", "3.2x")
    st.altair_chart(
        alt.Chart(pd.DataFrame({"period": ["Ago", "Sep", "Oct"], "ARPU": [15, 16, 18]}))
        .mark_line(point=True)
        .encode(x="period", y="ARPU"), use_container_width=True
    )

elif plan == "premium":
    st.markdown("### 📈 Dashboard Integral")
    c1, c2, c3 = st.columns(3)
    c1.metric("Disponibilidad de red", "99.95%")
    c2.metric("Tiempo medio de reparación", "2.3h")
    c3.metric("Rentabilidad neta", "32%")
    st.altair_chart(
        alt.Chart(pd.DataFrame({"Mes": list(range(1, 13)), "Clientes": [1000 + i*25 for i in range(12)]}))
        .mark_line(point=True, color="#4fb4ca")
        .encode(x="Mes", y="Clientes"), use_container_width=True
    )

# =====================================
# BOTONES DE UPGRADE
# =====================================
st.markdown("---")
if plan == "free":
    st.info("🚀 Pasá a PRO y desbloqueá indicadores de rentabilidad y proyecciones.")
elif plan == "pro":
    st.info("💎 Actualizá a PREMIUM para comparar redes, zonas y alertas automáticas.")
