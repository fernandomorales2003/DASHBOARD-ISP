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
    return fields

def update_plan(uid, nuevo_plan):
    fields = get_user_doc(uid)
    email = fields["email"].get("stringValue", "") if fields and "email" in fields else ""
    data = {
        "fields": {
            "email": {"stringValue": email},
            "plan": {"stringValue": nuevo_plan},
            "fecha_registro": fields.get("fecha_registro", {"integerValue": int(time.time())})
        }
    }
    firestore_request("PATCH", f"users/{uid}", data)
    return True

# =====================================
# MÉTRICAS
# =====================================
def save_metrics(uid, year, month, clientes, arpu, churn, mc, cac):
    period = f"{year}-{month:02d}"
    path = f"tenants/{uid}/metrics/{period}"

    existing = firestore_request("GET", path)
    if existing and "fields" in existing:
        st.info(f"ℹ️ Reescribiendo datos del período {period} (ya existía en Firestore).")

    data = {
        "fields": {
            "period": {"stringValue": period},
            "clientes": {"integerValue": int(clientes)},
            "arpu": {"doubleValue": arpu},
            "churn": {"doubleValue": churn},
            "mc": {"doubleValue": mc},
            "cac": {"doubleValue": cac},
            "created_at": {"integerValue": int(time.time())}
        }
    }
    firestore_request("PATCH", path, data)

def load_metrics(uid):
    r = firestore_request("GET", f"tenants/{uid}/metrics")
    if not r or "documents" not in r:
        return pd.DataFrame()
    rows = []
    for doc in r["documents"]:
        f = doc["fields"]
        rows.append({
            "period": f.get("period", {}).get("stringValue", "N/A"),
            "clientes": int(f.get("clientes", {}).get("integerValue", 0)),
            "arpu": float(f.get("arpu", {}).get("doubleValue", 0)),
            "churn": float(f.get("churn", {}).get("doubleValue", 0)),
            "mc": float(f.get("mc", {}).get("doubleValue", 0)),
            "cac": float(f.get("cac", {}).get("doubleValue", 0))
        })
    return pd.DataFrame(rows).sort_values("period")

# =====================================
# PROYECCIÓN PRECISA
# =====================================
def proyectar_mes_a_mes(clientes_ini, churn_pct, arpu, mc_pct, months):
    churn_dec = churn_pct / 100.0
    mc_dec = mc_pct / 100.0
    clientes_mes, ingresos_mes, ingresos_netos_mes, perdidos_mes, ingresos_perdidos_mes = [], [], [], [], []

    c = float(clientes_ini)
    for _ in range(months):
        c_next = c * (1 - churn_dec)
        perdidos = c - c_next
        ingreso_m = c * arpu
        ingreso_neto_m = ingreso_m * mc_dec
        ingreso_perdido_m = perdidos * arpu

        clientes_mes.append(c_next)
        ingresos_mes.append(ingreso_m)
        ingresos_netos_mes.append(ingreso_neto_m)
        perdidos_mes.append(perdidos)
        ingresos_perdidos_mes.append(ingreso_perdido_m)
        c = c_next

    return {
        "clientes_mes": clientes_mes,
        "ingresos_mes": ingresos_mes,
        "ingresos_netos_mes": ingresos_netos_mes,
        "perdidos_mes": perdidos_mes,
        "ingresos_perdidos_mes": ingresos_perdidos_mes,
        "total_ingresos": sum(ingresos_mes),
        "total_ingresos_netos": sum(ingresos_netos_mes),
        "total_perdidos": sum(perdidos_mes),
        "total_ingresos_perdidos": sum(ingresos_perdidos_mes),
        "clientes_finales": clientes_mes[-1] if clientes_mes else clientes_ini,
    }

# =====================================
# DASHBOARD FREE
# =====================================
def mostrar_dashboard_free(uid):
    st.header("🌱 Dashboard ISP — Versión FREE")
    st.markdown("Cargá tus métricas mensuales para ver cómo impactan en tu negocio.")

    now = datetime.now()
    st.subheader("📅 Carga mensual")
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    with c1:
        year = st.selectbox("Año", list(range(2018, now.year + 1)), index=now.year - 2018)
    with c2:
        month = st.selectbox("Mes", list(range(1, 13)), index=now.month - 1)
    with c3:
        clientes = st.number_input("Clientes", 0, 200000, 1000, 10)
    with c4:
        arpu = st.number_input("ARPU (USD)", 0.0, 1000.0, 16.0, 0.1)
    with c5:
        churn = st.number_input("CHURN (%)", 0.01, 50.0, 2.0, 0.01)
    with c6:
        mc = st.number_input("MC (%)", 1.0, 100.0, 60.0, 0.1)
    with c7:
        cac = st.number_input("CAC (USD)", 0.0, 1000.0, 10.0, 0.1)

    selected_date = datetime(year, month, 1)
    if selected_date > datetime(now.year, now.month, 1):
        st.error("⚠️ No se pueden cargar datos de meses futuros.")
        st.stop()

    if st.button("💾 Guardar mes"):
        save_metrics(uid, year, month, clientes, arpu, churn, mc, cac)
        st.success(f"✅ Datos guardados o actualizados ({year}-{month:02d})")
        st.rerun()

    df = load_metrics(uid)
    if df.empty:
        st.warning("Cargá tus primeros datos para ver los resultados.")
        return

    df["ltv"] = (df["arpu"] * (df["mc"] / 100)) / (df["churn"] / 100)
    df["ebitda"] = df["clientes"] * df["arpu"] * (df["mc"] / 100)
    last = df.iloc[-1]

    st.subheader("📊 Indicadores actuales")
    cols = st.columns(6)
    cols[0].metric("Clientes", f"{last['clientes']:,}")
    cols[1].metric("ARPU", f"${last['arpu']:.2f}")
    cols[2].metric("CHURN", f"{last['churn']:.2f}%")
    cols[3].metric("MC", f"{last['mc']:.1f}%")
    cols[4].metric("CAC", f"${last['cac']:.2f}")
    cols[5].metric("EBITDA", f"${last['ebitda']:,.0f}")

    st.markdown("### 💸 Costo real por cliente perdido")
    st.metric("Costo real por cliente perdido", f"${last['ltv']:,.0f}")

    st.subheader("🔮 Proyección visual precisa")
    col_sel, col_btn = st.columns([2, 1])
    horizonte = col_sel.selectbox("Horizonte de proyección", [6, 12, 24], index=0)
    if col_btn.button("Calcular proyección"):
        res = proyectar_mes_a_mes(
            last["clientes"], last["churn"], last["arpu"], last["mc"], horizonte
        )
        clientes_ini = last["clientes"]
        st.markdown(f"## 📅 Proyección a {horizonte} meses")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f"<h2 style='color:#e63946;'>📉 {res['total_perdidos']:.0f}</h2>"
                f"<p style='font-size:15px;'>Clientes perdidos</p>"
                f"<p style='color:gray;'>Clientes actuales: {clientes_ini:,.0f}</p>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"<h2 style='color:#f3722c;'>💔 ${res['total_ingresos_perdidos']:,.0f}</h2>"
                f"<p style='font-size:15px;'>Ingresos perdidos</p>"
                f"<p style='color:gray;'>Ingresos netos actuales: ${res['total_ingresos_netos']:,.0f}</p>",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"<h2 style='color:#00cc83;'>📈 {res['clientes_finales']:.0f}</h2>"
                f"<p style='font-size:15px;'>Clientes finales</p>"
                f"<p style='color:gray;'>Total proyección {horizonte} meses</p>",
                unsafe_allow_html=True,
            )

        # Gráfico pérdidas
        meses = list(range(1, horizonte + 1))
        df_loss = pd.DataFrame({
            "Mes": meses,
            "Clientes perdidos": res["perdidos_mes"],
            "Ingresos perdidos": res["ingresos_perdidos_mes"],
        }).melt(id_vars="Mes", var_name="Tipo", value_name="Valor")
        chart = (
            alt.Chart(df_loss)
            .mark_line(point=True)
            .encode(
                x=alt.X("Mes:Q"),
                y=alt.Y("Valor:Q"),
                color="Tipo:N",
                tooltip=["Mes", "Tipo", "Valor"]
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)

# =====================================
# LOGIN
# =====================================
st.title("📊 Dashboard ISP — Acceso")

mode = st.sidebar.radio("Acción", ["Iniciar sesión", "Registrar usuario"])
with st.sidebar.form("auth_form"):
    email = st.text_input("Correo electrónico")
    password = st.text_input("Contraseña", type="password")
    submitted = st.form_submit_button("Continuar")
    if submitted:
        if mode == "Registrar usuario":
            r = sign_up(email, password)
        else:
            r = sign_in(email, password)
        if "error" in r:
            st.sidebar.error(r["error"]["message"])
        else:
            store_session(r)
            ensure_user_doc(r["localId"], r["email"])
            st.sidebar.success("✅ Bienvenido.")
            st.rerun()

if st.sidebar.button("🔑 Restaurar contraseña"):
    if email:
        reset_password(email)
        st.sidebar.success("📧 Correo de recuperación enviado.")
    else:
        st.sidebar.warning("Ingresá tu correo antes.")

if "auth" not in st.session_state:
    st.stop()

uid = st.session_state["auth"]["uid"]
email = st.session_state["auth"]["email"]
is_admin = (email == st.secrets["ADMIN"]["email"])
if is_admin:
    st.sidebar.success("👑 Modo administrador activo")
else:
    st.sidebar.info(f"Usuario: {email}")

if is_admin:
    st.header("👥 Panel de administración")
    users = list_auth_users()
    for u in users:
        doc = ensure_user_doc(u["uid"], u["email"])
        plan = doc.get("plan", {}).get("stringValue", "free")
        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
        c1.markdown(f"**{u['email']}** — Plan `{plan}` — UID `{u['uid']}`")
        if c2.button("Free", key=f"f_{u['uid']}"): update_plan(u["uid"], "free"); st.rerun()
        if c3.button("Pro", key=f"p_{u['uid']}"): update_plan(u["uid"], "pro"); st.rerun()
        if c4.button("Premium", key=f"x_{u['uid']}"): update_plan(u["uid"], "premium"); st.rerun()
        if c5.button("Reset", key=f"r_{u['uid']}"):
            reset_password(u["email"]); st.success(f"📧 Reset enviado a {u['email']}")
else:
    mostrar_dashboard_free(uid)
