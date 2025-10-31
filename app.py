import os
import time
import json
import requests
import streamlit as st
import pandas as pd
import altair as alt
import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore
from datetime import datetime

# ====================================
# CONFIG GENERAL
# ====================================
st.set_page_config(page_title="Dashboard ISP", layout="wide")

# ====================================
# FIREBASE ADMIN (FIRESTORE)
# ====================================
def init_firebase_admin():
    if not firebase_admin._apps:
        sa = json.loads(json.dumps(dict(st.secrets["FIREBASE"])))
        cred = credentials.Certificate(sa)
        firebase_admin.initialize_app(cred)

@st.cache_resource(ttl=3600)
def get_db():
    """Conecta a Firestore usando project_id explícito (evita error de entorno)."""
    init_firebase_admin()
    project_id = st.secrets["FIREBASE"]["project_id"]
    os.environ["GCLOUD_PROJECT"] = project_id
    return firestore.Client(project=project_id)

# ====================================
# FIREBASE AUTH REST
# ====================================
def endpoints():
    api_key = st.secrets["FIREBASE_WEB"]["apiKey"]
    base_auth = "https://identitytoolkit.googleapis.com/v1"
    base_secure = "https://securetoken.googleapis.com/v1"
    return {
        "sign_in": f"{base_auth}/accounts:signInWithPassword?key={api_key}",
        "sign_up": f"{base_auth}/accounts:signUp?key={api_key}",
        "refresh": f"{base_secure}/token?key={api_key}",
    }

def sign_up(email, password):
    r = requests.post(endpoints()["sign_up"], json={"email": email, "password": password, "returnSecureToken": True}, timeout=10)
    return r.json()

def sign_in(email, password):
    r = requests.post(endpoints()["sign_in"], json={"email": email, "password": password, "returnSecureToken": True}, timeout=10)
    return r.json()

def refresh_token(refresh_token):
    r = requests.post(endpoints()["refresh"], data={"grant_type": "refresh_token", "refresh_token": refresh_token}, timeout=10)
    return r.json()

def store_session(res):
    st.session_state["auth"] = {
        "id_token": res.get("idToken"),
        "refresh_token": res.get("refreshToken"),
        "uid": res.get("localId"),
        "email": res.get("email"),
        "expires_at": time.time() + int(res.get("expiresIn", "3600")) - 30,
    }

def ensure_session():
    if "auth" not in st.session_state:
        return
    auth = st.session_state["auth"]
    if time.time() < auth.get("expires_at", 0):
        return
    data = refresh_token(auth["refresh_token"])
    if "error" in data:
        st.session_state.pop("auth", None)
        st.warning("Sesión expirada. Iniciá sesión nuevamente.")
        return
    st.session_state["auth"]["id_token"] = data.get("id_token")
    st.session_state["auth"]["refresh_token"] = data.get("refresh_token", auth["refresh_token"])
    st.session_state["auth"]["expires_at"] = time.time() + int(data.get("expires_in", "3600")) - 30

# ====================================
# FIRESTORE HELPERS
# ====================================
def save_metrics(uid, period, arpu, churn, mc, cac, clientes):
    db = get_db()
    dref = db.collection("tenants").document(uid).collection("metrics").document(period)
    data = {
        "period": period,
        "arpu": float(arpu),
        "churn": float(churn),
        "mc": float(mc),
        "cac": float(cac),
        "clientes": int(clientes),
        "created_at": int(time.time())
    }
    for i in range(3):
        try:
            dref.set(data, merge=True)
            return
        except Exception as e:
            time.sleep(1.5)
    raise RuntimeError("No se pudo guardar después de varios intentos.")

def load_metrics(uid):
    db = get_db()
    docs = db.collection("tenants").document(uid).collection("metrics").stream()
    rows = [doc.to_dict() for doc in docs]
    rows = sorted(rows, key=lambda x: x.get("period", ""))
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["period","arpu","churn","mc","cac","clientes"])

# ====================================
# CÁLCULOS
# ====================================
def compute_derived(df):
    if df.empty:
        return df
    df = df.copy()
    df["churn_dec"] = df["churn"] / 100
    df["mc_dec"] = df["mc"] / 100
    df["ltv"] = (df["arpu"] * df["mc_dec"]) / df["churn_dec"]
    df["ltv_cac"] = df["ltv"] / df["cac"]
    df["arpu_var"] = df["arpu"].pct_change() * 100
    return df

# ====================================
# LOGIN UI
# ====================================
st.title("📊 Dashboard ISP — Métricas Dinámicas (modo diagnóstico)")

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
            st.sidebar.error(r["error"]["message"]) if "error" in r else st.sidebar.success("Usuario creado.")
        else:
            r = sign_in(email, password)
            if "error" in r:
                st.sidebar.error(r["error"]["message"])
            else:
                store_session(r)
                st.sidebar.success(f"Bienvenido {r.get('email')}")

ensure_session()

# ====================================
# DASHBOARD PRINCIPAL (debug)
# ====================================
if "auth" in st.session_state:
    uid = st.session_state["auth"]["uid"]
    st.sidebar.success(f"Sesión activa: {st.session_state['auth']['email']}")

    st.subheader("🧪 Diagnóstico de Firestore")

    # 🔍 Test conexión a Firestore
    if st.button("🔍 Test Firestore conexión"):
        try:
            db = get_db()
            st.write("✅ Firestore inicializado correctamente:", db)
            test_ref = db.collection("tenants").document(uid)
            st.write("📄 Path de prueba:", test_ref.path)
            st.success("Conexión a Firestore OK.")
        except Exception as e:
            st.error(f"❌ Error al conectar con Firestore: {e}")

    # ====================================
    # FORMULARIO DE CARGA
    # ====================================
    now = datetime.now()
    c1, c2 = st.columns(2)
    with c1:
        year = st.selectbox("Año", list(range(2018, now.year + 1)), index=now.year - 2018)
    with c2:
        month = st.selectbox("Mes", ["%02d" % m for m in range(1, 13)], index=now.month - 1)
    period = f"{year}-{month}"

    if datetime(year, int(month), 1) > datetime(now.year, now.month, 1):
        st.error("❌ No se pueden cargar períodos futuros.")
        st.stop()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        arpu = st.number_input("ARPU (USD)", 0.0, 1000.0, 16.0, 0.1)
    with c2:
        churn = st.number_input("CHURN (%)", 0.01, 50.0, 2.0, 0.01)
    with c3:
        mc = st.number_input("MC (%)", 1.0, 100.0, 60.0, 0.1)
    with c4:
        cac = st.number_input("CAC (USD)", 0.0, 10000.0, 150.0, 1.0)
    with c5:
        clientes = st.number_input("Clientes actuales", 1, 100000, 1000, 10)

    if st.button("Guardar/Actualizar mes"):
        try:
            st.write("Intentando guardar:", period, arpu, churn, mc, cac, clientes)
            db = get_db()
            ref = db.collection("tenants").document(uid).collection("metrics").document(period)
            ref.set({
                "period": period,
                "arpu": float(arpu),
                "churn": float(churn),
                "mc": float(mc),
                "cac": float(cac),
                "clientes": int(clientes),
                "created_at": int(time.time())
            })
            st.success(f"✅ Datos guardados correctamente ({period})")
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")

    # ====================================
    # LECTURA Y DEBUG DE DATAFRAME
    # ====================================
    df = load_metrics(uid)
    st.write("📂 DataFrame leído desde Firestore:")
    st.dataframe(df)

    if df.empty:
        st.warning("⚠️ No hay datos para graficar. Verificá si se guardaron en Firestore.")
        st.stop()

    # ====================================
    # GRAFICOS (solo si hay datos)
    # ====================================
    df = compute_derived(df)
    last = df.iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ARPU", f"${last['arpu']:.2f}", f"{last['arpu_var']:.1f}% vs mes anterior")
    c2.metric("CHURN", f"{last['churn']:.2f}%")
    c3.metric("LTV", f"${last['ltv']:.0f}")
    c4.metric("LTV/CAC", f"{last['ltv_cac']:.2f}x")

    st.markdown("### 📊 Gráficos de evolución")
    chart_arpu = alt.Chart(df).mark_line(point=True).encode(x="period:N", y="arpu:Q").properties(title="Evolución ARPU")
    chart_clientes = alt.Chart(df).mark_line(point=True, color="green").encode(x="period:N", y="clientes:Q").properties(title="Clientes actuales")
    st.altair_chart(chart_arpu, use_container_width=True)
    st.altair_chart(chart_clientes, use_container_width=True)

else:
    st.info("🔒 Iniciá sesión o registrate para acceder al dashboard.")
