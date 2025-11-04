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

st.set_page_config(page_title="Dashboard ISP — Admin + Login", layout="wide")

# =========================================================
# FIREBASE ADMIN INIT
# =========================================================
def init_firebase_admin():
    if not firebase_admin._apps:
        sa = json.loads(json.dumps(dict(st.secrets["FIREBASE"])))
        cred = credentials.Certificate(sa)
        firebase_admin.initialize_app(cred)

# =========================================================
# FIRESTORE REST HELPER
# =========================================================
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

        if r.status_code == 404:
            return None
        if r.status_code not in (200, 201):
            st.error(f"❌ Firestore error {r.status_code}: {r.text}")
            return None
        return r.json()

    except Exception as e:
        st.error(f"❌ Error Firestore REST: {e}")
        return None


# =========================================================
# AUTH REST
# =========================================================
def endpoints():
    api_key = st.secrets["FIREBASE_WEB"]["apiKey"]
    base = "https://identitytoolkit.googleapis.com/v1"
    return {
        "sign_in": f"{base}/accounts:signInWithPassword?key={api_key}",
        "sign_up": f"{base}/accounts:signUp?key={api_key}",
        "reset":   f"{base}/accounts:sendOobCode?key={api_key}",
    }

def sign_in(email, password):
    return requests.post(endpoints()["sign_in"], json={"email": email, "password": password}).json()

def sign_up(email, password):
    return requests.post(endpoints()["sign_up"], json={"email": email, "password": password}).json()

def reset_password(email):
    r = requests.post(endpoints()["reset"], json={"requestType": "PASSWORD_RESET", "email": email})
    return r.status_code == 200

def store_session(res):
    st.session_state["auth"] = {
        "uid": res.get("localId"),
        "email": res.get("email")
    }

# =========================================================
# FIRESTORE USERS
# =========================================================
def get_user_doc(uid):
    r = firestore_request("GET", f"users/{uid}")
    return r.get("fields") if (r and "fields" in r) else None

def ensure_user_doc(uid, email):
    fields = get_user_doc(uid)
    if not fields:
        firestore_request("PATCH", f"users/{uid}", {
            "fields": {
                "email": {"stringValue": email},
                "plan": {"stringValue": "free"},
                "fecha_registro": {"integerValue": int(time.time())}
            }
        })
        return {"email":{"stringValue":email},"plan":{"stringValue":"free"}}
    return fields

def update_plan(uid, new_plan):
    fields = get_user_doc(uid)
    email = fields.get("email", {}).get("stringValue", "")
    firestore_request("PATCH", f"users/{uid}", {
        "fields": {
            "email": {"stringValue": email},
            "plan": {"stringValue": new_plan},
            "fecha_registro": fields.get("fecha_registro")
        }
    })

def list_auth_users():
    init_firebase_admin()
    users_list = []
    page = auth.list_users()
    while page:
        for u in page.users:
            users_list.append({"uid": u.uid, "email": u.email})
        page = page.get_next_page()
    return users_list

# =========================================================
# FIRESTORE METRICS
# =========================================================
def save_metric(uid, period, arpu, churn, mc, cac, clientes):
    firestore_request("PATCH", f"tenants/{uid}/metrics/{period}", {
        "fields": {
            "period": {"stringValue": period},
            "arpu": {"doubleValue": arpu},
            "churn": {"doubleValue": churn},
            "mc": {"doubleValue": mc},
            "cac": {"doubleValue": cac},
            "clientes": {"integerValue": clientes},
            "created_at": {"integerValue": int(time.time())}
        }
    })

def load_metrics(uid):
    r = firestore_request("GET", f"tenants/{uid}/metrics")
    if not r or "documents" not in r:    
        return pd.DataFrame()

    rows = []
    for d in r["documents"]:
        f = d["fields"]
        rows.append({
            "period": f["period"]["stringValue"],
            "arpu": float(f["arpu"]["doubleValue"]),
            "churn": float(f["churn"]["doubleValue"]),
            "mc": float(f["mc"]["doubleValue"]),
            "cac": float(f["cac"]["doubleValue"]),
            "clientes": int(f["clientes"]["integerValue"]),
        })
    return pd.DataFrame(rows).sort_values("period")


# =========================================================
# LOGIN UI
# =========================================================
st.title("📊 Dashboard ISP")

mode = st.sidebar.selectbox("Acción", ["Iniciar sesión", "Registrar usuario"])

with st.sidebar.form("login"):
    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")
    if st.form_submit_button("Continuar"):
        r = sign_up(email, password) if mode=="Registrar usuario" else sign_in(email, password)
        if "error" in r:
            st.error(r["error"]["message"])
        else:
            store_session(r)
            ensure_user_doc(r["localId"], r["email"])
            st.success("✅ Bienvenido!")
            st.rerun()

if "auth" not in st.session_state:
    st.stop()

uid = st.session_state["auth"]["uid"]
logged_email = st.session_state["auth"]["email"]
is_admin = (logged_email == st.secrets["ADMIN"]["email"])

# =========================================================
# ADMIN PANEL
# =========================================================
if is_admin:
    st.subheader("👑 Administración de usuarios")
    users = list_auth_users()
    for u in users:
        doc = ensure_user_doc(u["uid"], u["email"])
        plan = doc["plan"]["stringValue"]
        col1, col2, col3, col4 = st.columns([4,1,1,1])
        col1.write(f"**{u['email']}** — {plan}")
        if col2.button("Free", key=f"f{u['uid']}"): update_plan(u["uid"], "free"); st.rerun()
        if col3.button("Pro", key=f"p{u['uid']}"): update_plan(u["uid"], "pro"); st.rerun()
        if col4.button("Premium", key=f"x{u['uid']}"): update_plan(u["uid"], "premium"); st.rerun()

# =========================================================
# USER DASHBOARD (FREE)
# =========================================================
st.header("🌱 Panel FREE — Métricas Financieras ISP")

fields = ensure_user_doc(uid, logged_email)
plan = fields["plan"]["stringValue"]

st.info(f"Tu plan: **{plan.upper()}**")

# ---- Input de datos mensuales ----
st.subheader("📝 Cargar datos mensuales")

now = datetime.now()
year = st.selectbox("Año", list(range(2018, now.year+1)), index=now.year-2018)
month = st.selectbox("Mes", [f"{m:02d}" for m in range(1,13)], index=now.month-1)
period = f"{year}-{month}"

arpu = st.number_input("ARPU (USD)", 0.0, 1000.0, 16.0, 0.1)
churn = st.number_input("CHURN (%)", 0.01, 50.0, 2.0, 0.01)
mc = st.number_input("MC (%)", 1.0, 100.0, 60.0, 0.1)
cac = st.number_input("CAC (USD)", 0.0, 2000.0, 150.0, 1.0)
clientes = st.number_input("Clientes actuales", 1, 200000, 1000, 10)

if st.button("Guardar mes"):
    save_metric(uid, period, arpu, churn, mc, cac, clientes)
    st.success("✅ Guardado")
    st.rerun()

df = load_metrics(uid)
if df.empty:
    st.warning("Cargá tus primeros datos!")
    st.stop()

df["churn_dec"] = df["churn"] / 100
df["mc_dec"] = df["mc"] / 100
df["ltv"] = (df["arpu"] * df["mc_dec"]) / df["churn_dec"]
df["ltv_cac"] = df["ltv"] / df["cac"]


# ---- Métricas actuales ----
last = df.iloc[-1]
c1,c2,c3,c4 = st.columns(4)
c1.metric("ARPU", f"${last['arpu']:.2f}")
c2.metric("CHURN", f"{last['churn']:.2f}%")
c3.metric("MC", f"{last['mc']:.1f}%")
c4.metric("LTV", f"${last['ltv']:.0f}")

# ---- Graficos ----
st.subheader("📈 Evolución")
st.altair_chart(
    alt.Chart(df).mark_line(point=True).encode(x="period",y="arpu").properties(title="ARPU"),
    use_container_width=True
)
st.altair_chart(
    alt.Chart(df).mark_line(point=True, color="orange").encode(x="period",y="clientes").properties(title="Clientes"),
    use_container_width=True
)

# ---- Proyecciones ----
st.subheader("🔮 Proyecciones")
col1,col2,col3 = st.columns(3)
horizons = { "6 meses":6, "1 año":12, "2 años":24 }

for label, months in horizons.items():
    if col1.button(label, key=label):
        churn = last["churn_dec"]
        clientes_ini = last["clientes"]
        arpu_val = last["arpu"]
        mc_val = last["mc_dec"]

        clientes_fin = clientes_ini * ((1 - churn) ** months)
        ingresos = ((clientes_ini + clientes_fin) / 2) * arpu_val * months
        neto = ingresos * mc_val

        st.success(f"✅ {label} proyección")
        s1,s2,s3 = st.columns(3)
        s1.metric("Clientes finales", f"{clientes_fin:,.0f}")
        s2.metric("Ingresos brutos", f"${ingresos:,.0f}")
        s3.metric("Ingresos netos", f"${neto:,.0f}")

