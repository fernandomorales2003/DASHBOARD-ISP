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
# Config general
# ====================================
st.set_page_config(page_title="Dashboard ISP", layout="wide")

# ====================================
# Firebase Admin (Firestore)
# ====================================
def init_firebase_admin():
    if not firebase_admin._apps:
        sa = json.loads(json.dumps(dict(st.secrets["FIREBASE"])))
        cred = credentials.Certificate(sa)
        firebase_admin.initialize_app(cred)

@st.cache_resource
def get_db():
    init_firebase_admin()
    return firestore.Client(project=st.secrets["FIREBASE"]["project_id"])

# ====================================
# REST Auth (Firebase Web API)
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
    url = endpoints()["sign_up"]
    r = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=15)
    return r.json()

def sign_in(email, password):
    url = endpoints()["sign_in"]
    r = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=15)
    return r.json()

def refresh_token(refresh_token):
    url = endpoints()["refresh"]
    r = requests.post(url, data={"grant_type": "refresh_token", "refresh_token": refresh_token}, timeout=15)
    return r.json()

def store_session(res):
    st.session_state["auth"] = {
        "id_token": res.get("idToken"),
        "refresh_token": res.get("refreshToken"),
        "uid": res.get("localId"),
        "email": res.get("email"),
        "expires_at": time.time() + int(res.get("expiresIn", "3600")) - 30
    }

def ensure_session():
    if "auth" not in st.session_state:
        return
    auth = st.session_state["auth"]
    if not auth or "refresh_token" not in auth:
        return
    if time.time() < auth.get("expires_at", 0):
        return
    data = refresh_token(auth["refresh_token"])
    if "error" in data:
        st.session_state.pop("auth", None)
        st.warning("La sesión expiró. Volvé a iniciar sesión.")
        return
    st.session_state["auth"]["id_token"] = data.get("id_token")
    st.session_state["auth"]["refresh_token"] = data.get("refresh_token", auth["refresh_token"])
    st.session_state["auth"]["expires_at"] = time.time() + int(data.get("expires_in", "3600")) - 30

# ====================================
# Firestore helpers
# ====================================
def doc_ref_for(uid: str, period: str):
    db = get_db()
    return db.collection("tenants").document(uid).collection("metrics").document(period)

def save_metrics(uid: str, period: str, arpu: float, churn_pct: float, mc_pct: float, cac: float, clientes: int):
    dref = doc_ref_for(uid, period)
    dref.set({
        "period": period,
        "arpu": float(arpu),
        "churn": float(churn_pct),
        "mc": float(mc_pct),
        "cac": float(cac),
        "clientes": int(clientes),
        "created_at": int(time.time())
    }, merge=True)

def load_metrics(uid: str):
    db = get_db()
    qs = db.collection("tenants").document(uid).collection("metrics").order_by("period").stream()
    rows = [doc.to_dict() for doc in qs]
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["period","arpu","churn","mc","cac","clientes"])

# ====================================
# Cálculos
# ====================================
def compute_derived(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["churn_dec"] = df["churn"] / 100.0
    df["mc_dec"] = df["mc"] / 100.0
    df["ltv"] = (df["arpu"] * df["mc_dec"]) / df["churn_dec"]
    df["ltv_cac"] = df["ltv"] / df["cac"]
    return df

# ====================================
# UI Login
# ====================================
st.title("📊 Dashboard ISP — Métricas Dinámicas")

mode = st.sidebar.radio("Acción", ["Iniciar sesión", "Registrar usuario"])
with st.sidebar.form("auth_form"):
    email = st.text_input("Correo electrónico")
    password = st.text_input("Contraseña", type="password")
    submitted = st.form_submit_button("Continuar")

    if submitted:
        if not email or not password:
            st.sidebar.error("Completá email y contraseña.")
        else:
            if mode == "Registrar usuario":
                r = sign_up(email, password)
                if "error" in r:
                    st.sidebar.error(r["error"]["message"])
                else:
                    st.sidebar.success("Usuario creado. Ahora podés iniciar sesión.")
            else:
                r = sign_in(email, password)
                if "error" in r:
                    st.sidebar.error(r["error"]["message"])
                else:
                    store_session(r)
                    st.sidebar.success(f"Bienvenido {r.get('email') or email}")

ensure_session()

logged = ("auth" in st.session_state) and st.session_state["auth"].get("id_token")
if logged:
    uid = st.session_state["auth"]["uid"]
    st.sidebar.success(f"Sesión: {st.session_state['auth'].get('email')}")

    # ====================================
    # Formulario de carga
    # ====================================
    st.subheader("📝 Cargar datos mensuales")
    current_year = datetime.now().year
    current_month = datetime.now().month

    c1, c2 = st.columns(2)
    with c1:
        year = st.selectbox("Año", list(range(2018, current_year + 1)), index=current_year - 2018)
    with c2:
        month = st.selectbox("Mes", ["%02d" % m for m in range(1, 13)], index=current_month - 1)
    period = f"{year}-{month}"

    # Validación
    selected_date = datetime(year, int(month), 1)
    now = datetime(datetime.now().year, datetime.now().month, 1)
    if selected_date > now:
        st.error("❌ No se pueden cargar datos de un período futuro.")
        st.stop()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        arpu = st.number_input("ARPU (USD)", min_value=0.0, value=16.0, step=0.1)
    with c2:
        churn = st.number_input("CHURN mensual (%)", min_value=0.01, max_value=50.0, value=2.0, step=0.01)
    with c3:
        mc = st.number_input("Margen de Contribución (%)", min_value=1.0, max_value=100.0, value=60.0, step=0.1)
    with c4:
        cac = st.number_input("CAC (USD)", min_value=0.0, value=150.0, step=1.0)
    with c5:
        clientes = st.number_input("Clientes actuales", min_value=1, value=1000, step=10)

    if st.button("Guardar/Actualizar mes"):
        try:
            save_metrics(uid, period, arpu, churn, mc, cac, clientes)
            st.success(f"Datos guardados para {period}.")
        except Exception as e:
            st.error(f"Error al guardar: {e}")

    # ====================================
    # Datos y KPIs
    # ====================================
    df = load_metrics(uid)
    if df.empty:
        st.info("Aún no hay datos cargados.")
        st.stop()

    df = df.sort_values("period")
    df = compute_derived(df)

    # Variación ARPU
    if len(df) > 1:
        df["arpu_var"] = df["arpu"].pct_change() * 100
    else:
        df["arpu_var"] = 0

    last = df.iloc[-1]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("ARPU", f"${last['arpu']:.2f}", f"{last['arpu_var']:.1f}% vs mes anterior")
    k2.metric("CHURN", f"{last['churn']:.2f}%")
    k3.metric("LTV", f"${last['ltv']:.0f}")
    k4.metric("LTV/CAC", f"{last['ltv_cac']:.2f}x")

    # ====================================
    # Gráficos principales
    # ====================================
    st.markdown("### 📊 Gráficos de evolución")

    # 1️⃣ Evolución del ARPU
    chart_arpu = alt.Chart(df).mark_line(point=True).encode(
        x="period:N", y="arpu:Q", tooltip=["period", "arpu", "arpu_var"]
    ).properties(title="Evolución del ARPU mensual")

    # 2️⃣ Evolución clientes actuales
    chart_clientes = alt.Chart(df).mark_line(point=True, color="green").encode(
        x="period:N", y="clientes:Q"
    ).properties(title="Cantidad de clientes actuales")

    # 3️⃣ Proyección clientes (12 meses con churn)
    churn_rate = last["churn_dec"]
    clientes_proj = [last["clientes"] * ((1 - churn_rate) ** i) for i in range(13)]
    df_proj = pd.DataFrame({
        "mes": list(range(0, 13)),
        "clientes_proyectados": clientes_proj
    })
    chart_proj = alt.Chart(df_proj).mark_line(point=True, color="orange").encode(
        x="mes:Q", y="clientes_proyectados:Q"
    ).properties(title="Proyección de clientes (12 meses)")

    # 4️⃣ LTV en función del CHURN
    churn_range = pd.Series([i/100 for i in range(1, 11)])
    df_ltv = pd.DataFrame({
        "churn": churn_range,
        "ltv": (last["arpu"] * last["mc_dec"]) / churn_range
    })
    chart_ltv = alt.Chart(df_ltv).mark_line(point=True, color="red").encode(
        x=alt.X("churn:Q", title="CHURN (%)"),
        y=alt.Y("ltv:Q", title="LTV (USD)")
    ).properties(title="LTV en función del CHURN")

    # 5️⃣ LTV/CAC relación con límite
    df_ratio = df[["period", "ltv_cac"]].copy()
    chart_ratio = alt.Chart(df_ratio).mark_line(point=True, color="purple").encode(
        x="period:N", y="ltv_cac:Q"
    )
    limit_line = alt.Chart(pd.DataFrame({"ltv_cac": [3]})).mark_rule(color="red", strokeDash=[5, 5]).encode(y="ltv_cac:Q")
    chart_ratio_final = (chart_ratio + limit_line).properties(title="Relación LTV/CAC (límite = 3x)")

    st.altair_chart(chart_arpu, use_container_width=True)
    st.altair_chart(chart_clientes, use_container_width=True)
    st.altair_chart(chart_proj, use_container_width=True)
    st.altair_chart(chart_ltv, use_container_width=True)
    st.altair_chart(chart_ratio_final, use_container_width=True)

    st.markdown("---")
    st.caption("Fórmulas:  LTV = (ARPU × MC%) / CHURN%   |   LTV/CAC = LTV ÷ CAC")

    if st.sidebar.button("Cerrar sesión"):
        st.session_state.pop("auth", None)
        st.rerun()

else:
    st.info("🔒 Iniciá sesión o registrate para acceder al dashboard.")
