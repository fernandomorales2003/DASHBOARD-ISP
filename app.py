import os
import time
import json
import requests
import streamlit as st
import pandas as pd
import altair as alt
import firebase_admin
from firebase_admin import credentials, auth
from datetime import datetime

st.set_page_config(page_title="Dashboard ISP — Admin + FREE", layout="wide")

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
def firestore_request(method, path, data=None, params=None):
    init_firebase_admin()
    project_id = st.secrets["FIREBASE"]["project_id"]
    base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
    url = f"{base_url}/{path}"
    headers = {"Content-Type": "application/json"}
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, params=params or {}, timeout=10)
        elif method == "PATCH":
            r = requests.patch(url, headers=headers, json=data, timeout=10)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=data, timeout=10)
        else:
            return None

        if r.status_code == 404:
            st.info(f"🆕 Creando registro Firestore para usuario {path.split('/')[-1]}")
            return None
        if r.status_code not in (200, 201):
            st.error(f"❌ Firestore error {r.status_code}: {r.text}")
            return None
        return r.json()
    except Exception as e:
        st.error(f"❌ Error de conexión Firestore REST: {e}")
        return None

# =====================================
# FIREBASE AUTH REST
# =====================================
def endpoints():
    api_key = st.secrets["FIREBASE_WEB"]["apiKey"]
    base_auth = "https://identitytoolkit.googleapis.com/v1"
    return {
        "sign_in": f"{base_auth}/accounts:signInWithPassword?key={api_key}",
        "sign_up": f"{base_auth}/accounts:signUp?key={api_key}",
        "reset":   f"{base_auth}/accounts:sendOobCode?key={api_key}",
    }

def sign_in(email, password):
    return requests.post(endpoints()["sign_in"], json={"email": email, "password": password, "returnSecureToken": True}).json()

def sign_up(email, password):
    return requests.post(endpoints()["sign_up"], json={"email": email, "password": password, "returnSecureToken": True}).json()

def reset_password(email):
    if not email:
        st.error("❌ No se proporcionó email para reset.")
        return False
    r = requests.post(endpoints()["reset"], json={"requestType": "PASSWORD_RESET", "email": email})
    if r.status_code == 200:
        return True
    else:
        st.error(f"❌ Error Firebase ({r.status_code}): {r.text}")
        return False

def store_session(res):
    st.session_state["auth"] = {
        "id_token": res.get("idToken"),
        "uid": res.get("localId"),
        "email": res.get("email")
    }

# =====================================
# HELPERS ADMIN
# =====================================
def list_auth_users():
    init_firebase_admin()
    out = []
    page = auth.list_users()
    while page:
        for u in page.users:
            out.append({"uid": u.uid, "email": u.email or ""})
        page = page.get_next_page()
    return out

def get_user_doc(uid):
    r = firestore_request("GET", f"users/{uid}")
    return r.get("fields") if (r and "fields" in r) else None

def ensure_user_doc(uid, email):
    fields = get_user_doc(uid)
    if not fields:
        firestore_request("PATCH", f"users/{uid}", {
            "fields": {
                "email": {"stringValue": email or ""},
                "plan": {"stringValue": "free"},
                "fecha_registro": {"integerValue": int(time.time())}
            }
        })
        return {"email": {"stringValue": email or ""}, "plan": {"stringValue": "free"}}
    if "email" not in fields or not fields["email"].get("stringValue", ""):
        fields["email"] = {"stringValue": email or ""}
        firestore_request("PATCH", f"users/{uid}", {"fields": fields})
    return fields

def update_plan(uid, nuevo_plan):
    fields = get_user_doc(uid)
    email = fields["email"].get("stringValue", "") if fields and "email" in fields else ""
    if not email:
        try:
            u = auth.get_user(uid)
            email = u.email or ""
        except Exception:
            email = ""
    data = {
        "fields": {
            "email": {"stringValue": email},
            "plan": {"stringValue": nuevo_plan},
            "fecha_registro": fields.get("fecha_registro", {"integerValue": int(time.time())}) if fields else {"integerValue": int(time.time())}
        }
    }
    firestore_request("PATCH", f"users/{uid}", data)
    return True

# =====================================
# DASHBOARD FREE
# =====================================
def mostrar_dashboard_free():
    st.header("📊 Dashboard ISP — Versión FREE")

    st.markdown("""
    En esta versión podés visualizar el **impacto de tus indicadores principales**:
    - **ARPU:** ingreso promedio por cliente  
    - **CHURN:** tasa de baja mensual  
    - **MC:** margen de contribución  
    - **LTV:** valor de vida del cliente  
    """)

    st.sidebar.header("⚙️ Parámetros del mes actual")

    col1, col2, col3 = st.sidebar.columns(3)
    with col1:
        arpu = st.number_input("ARPU (USD)", 0.0, 1000.0, 16.0, 0.1)
    with col2:
        churn = st.number_input("CHURN (%)", 0.01, 50.0, 2.0, 0.01)
    with col3:
        mc = st.number_input("MC (%)", 1.0, 100.0, 60.0, 0.1)

    ltv = (arpu * (mc / 100)) / (churn / 100)
    st.sidebar.metric("💰 LTV (Valor de Vida)", f"${ltv:,.0f}")

    st.subheader("📈 Indicadores principales")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ARPU", f"${arpu:.2f}")
    c2.metric("CHURN", f"{churn:.2f}%")
    c3.metric("MC", f"{mc:.1f}%")
    c4.metric("LTV", f"${ltv:,.0f}")

    st.markdown("### 🔮 Proyecciones de negocio")

    col1, col2, col3 = st.columns(3)
    horizonte = None
    if col1.button("📆 Proyectar 6 meses"):
        horizonte = 6
    elif col2.button("📆 Proyectar 1 año"):
        horizonte = 12
    elif col3.button("📆 Proyectar 2 años"):
        horizonte = 24

    if horizonte:
        clientes_ini = 1000
        churn_dec = churn / 100
        mc_dec = mc / 100

        clientes_fin = clientes_ini * ((1 - churn_dec) ** horizonte)
        clientes_prom = (clientes_ini + clientes_fin) / 2
        ingresos_brutos = clientes_prom * arpu * horizonte
        ingresos_netos = ingresos_brutos * mc_dec
        vida_cliente_meses = 1 / churn_dec

        st.markdown(f"### 🧮 Proyección a {horizonte} meses")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Clientes finales", f"{clientes_fin:,.0f}", f"-{(1 - clientes_fin/clientes_ini)*100:.1f}%")
        c2.metric("Ingresos brutos", f"${ingresos_brutos:,.0f}")
        c3.metric("Ingresos netos", f"${ingresos_netos:,.0f}")
        c4.metric("Vida promedio (LTV)", f"{vida_cliente_meses:.1f} meses")

        meses = list(range(horizonte + 1))
        clientes_mes = [clientes_ini * ((1 - churn_dec) ** m) for m in meses]
        ingresos_mes = [clientes_mes[m] * arpu for m in meses]
        ltv_mes = [(arpu * mc_dec) / (churn / 100) for m in meses]

        df_proj = pd.DataFrame({"Mes": meses, "Clientes": clientes_mes, "Ingresos": ingresos_mes, "LTV": ltv_mes})
        c1, c2, c3 = st.columns(3)

        c1.altair_chart(alt.Chart(df_proj).mark_line(point=True, color="#4fb4ca")
            .encode(x="Mes:Q", y="Clientes:Q").properties(title="Evolución de Clientes"), use_container_width=True)
        c2.altair_chart(alt.Chart(df_proj).mark_line(point=True, color="#00cc83")
            .encode(x="Mes:Q", y="Ingresos:Q").properties(title="Ingresos Brutos"), use_container_width=True)
        c3.altair_chart(alt.Chart(df_proj).mark_line(point=True, color="#3260ea")
            .encode(x="Mes:Q", y="LTV:Q").properties(title="LTV estimado"), use_container_width=True)

    st.markdown("### 🧊 Analogia del ICEBERG — Visibilidad vs. Rentabilidad")
    iceberg_data = pd.DataFrame({
        "Componente": ["ARPU visible", "CHURN oculto", "MC oculto", "LTV profundo"],
        "Valor": [arpu, churn, mc, ltv],
        "Tipo": ["Visible", "Sumergido", "Sumergido", "Sumergido"]
    })
    st.altair_chart(
        alt.Chart(iceberg_data).mark_bar().encode(
            x=alt.X("Componente:N", sort=None),
            y="Valor:Q",
            color=alt.condition(alt.datum.Tipo == "Visible",
                alt.value("#4fb4ca"), alt.value("#a8c3cf")),
            tooltip=["Componente", "Valor"]
        ).properties(title="Impacto del CHURN y MC sobre el LTV (Analogia ICEBERG)"),
        use_container_width=True
    )
    st.caption("💡 Un aumento de 1 punto en el CHURN puede reducir el LTV hasta un 40%. Controlar la baja de clientes es clave.")

# =====================================
# LOGIN / REGISTRO
# =====================================
st.title("📊 Dashboard ISP — Acceso")

mode = st.sidebar.radio("Acción", ["Iniciar sesión", "Registrar usuario"])
with st.sidebar.form("auth_form"):
    email_input = st.text_input("Correo electrónico")
    password = st.text_input("Contraseña", type="password")
    submitted = st.form_submit_button("Continuar")

    if submitted:
        if not email_input or not password:
            st.sidebar.error("Completá email y contraseña.")
        elif mode == "Registrar usuario":
            r = sign_up(email_input, password)
            if "error" in r:
                st.sidebar.error(r["error"]["message"])
            else:
                store_session(r)
                uid = r["localId"]
                firestore_request("PATCH", f"users/{uid}", {
                    "fields": {
                        "email": {"stringValue": email_input},
                        "plan": {"stringValue": "free"},
                        "fecha_registro": {"integerValue": int(time.time())}
                    }
                })
                st.sidebar.success("✅ Usuario creado con plan FREE.")
        else:
            r = sign_in(email_input, password)
            if "error" in r:
                st.sidebar.error(r["error"]["message"])
            else:
                store_session(r)
                st.sidebar.success(f"Bienvenido {r.get('email')}")

if st.sidebar.button("🔑 Restaurar contraseña"):
    if email_input:
        if reset_password(email_input):
            st.sidebar.success("📧 Correo de recuperación enviado.")
        else:
            st.sidebar.error("Error al enviar el correo.")
    else:
        st.sidebar.warning("Ingresá tu correo antes.")

if "auth" not in st.session_state:
    st.stop()

uid = st.session_state["auth"]["uid"]
logged_email = st.session_state["auth"]["email"]

is_admin = (logged_email == st.secrets["ADMIN"]["email"])
if is_admin:
    st.sidebar.success("👑 Modo administrador activo")
else:
    st.sidebar.info(f"Usuario: {logged_email}")

# =====================================
# PANEL ADMINISTRADOR
# =====================================
if is_admin:
    st.header("👥 Panel de administración de usuarios")
    auth_users = list_auth_users()
    if not auth_users:
        st.warning("No hay usuarios en Firebase Auth.")
        st.stop()
    merged = []
    for u in auth_users:
        fields = ensure_user_doc(u["uid"], u["email"])
        plan = fields.get("plan", {}).get("stringValue", "free")
        merged.append({
            "uid": u["uid"], "email": u["email"], "plan": plan,
            "fecha": datetime.fromtimestamp(int(fields.get("fecha_registro", {}).get("integerValue", "0"))).strftime("%Y-%m-%d")
        })
    df_users = pd.DataFrame(merged).sort_values("email")
    st.dataframe(df_users, use_container_width=True)
else:
    fields = ensure_user_doc(uid, logged_email)
    plan = fields.get("plan", {}).get("stringValue", "free")
    if plan == "free":
        mostrar_dashboard_free()
