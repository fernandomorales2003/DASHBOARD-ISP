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
    return r.status_code == 200

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
    firestore_request("PATCH", f"users/{uid}", {
        "fields": {
            "email": {"stringValue": email},
            "plan": {"stringValue": nuevo_plan},
            "fecha_registro": fields.get("fecha_registro", {"integerValue": int(time.time())})
        }
    })
    return True

# =====================================
# MÉTRICAS
# =====================================
def save_metrics(uid, year, month, clientes, arpu, churn, mc, cac):
    period = f"{year}-{month:02d}"
    firestore_request("PATCH", f"tenants/{uid}/metrics/{period}", {
        "fields": {
            "period": {"stringValue": period},
            "clientes": {"integerValue": int(clientes)},
            "arpu": {"doubleValue": arpu},
            "churn": {"doubleValue": churn},
            "mc": {"doubleValue": mc},
            "cac": {"doubleValue": cac},
            "created_at": {"integerValue": int(time.time())}
        }
    })

def load_metrics(uid):
    r = firestore_request("GET", f"tenants/{uid}/metrics")
    if not r or "documents" not in r:
        return pd.DataFrame()
    data = []
    for doc in r["documents"]:
        f = doc["fields"]
        data.append({
            "period": f["period"]["stringValue"],
            "clientes": int(f.get("clientes", {}).get("integerValue", 0)),
            "arpu": float(f.get("arpu", {}).get("doubleValue", 0)),
            "churn": float(f.get("churn", {}).get("doubleValue", 0)),
            "mc": float(f.get("mc", {}).get("doubleValue", 0)),
            "cac": float(f.get("cac", {}).get("doubleValue", 0))
        })
    return pd.DataFrame(data).sort_values("period")

# =====================================
# DASHBOARD FREE
# =====================================
def mostrar_dashboard_free(uid):
    st.header("🌱 Dashboard ISP — Versión FREE")

    now = datetime.now()
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    with c1: year = st.selectbox("Año", list(range(2018, now.year + 1)), index=now.year - 2018)
    with c2: month = st.selectbox("Mes", list(range(1, 13)), index=now.month - 1)
    with c3: clientes = st.number_input("Clientes", 0, 200000, 1000, 10)
    with c4: arpu = st.number_input("ARPU (USD)", 0.0, 1000.0, 16.0, 0.1)
    with c5: churn = st.number_input("CHURN (%)", 0.01, 50.0, 2.0, 0.01)
    with c6: mc = st.number_input("MC (%)", 1.0, 100.0, 60.0, 0.1)
    with c7: cac = st.number_input("CAC (USD)", 0.0, 1000.0, 10.0, 0.1)

    if st.button("💾 Guardar mes"):
        save_metrics(uid, year, month, clientes, arpu, churn, mc, cac)
        st.success(f"✅ Datos guardados ({year}-{month:02d})")
        st.rerun()

    df = load_metrics(uid)
    if df.empty:
        st.warning("Cargá tus primeros datos para ver resultados.")
        return

    df["ltv"] = (df["arpu"] * (df["mc"] / 100)) / (df["churn"] / 100)
    df["ebitda"] = df["clientes"] * df["arpu"] * (df["mc"] / 100)
    df["margen_ebitda"] = (df["ebitda"] / (df["clientes"] * df["arpu"])) * 100
    last = df.iloc[-1]

    st.subheader("📊 Indicadores actuales")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Clientes", f"{last['clientes']:,}")
    c2.metric("ARPU", f"${last['arpu']:.2f}")
    c3.metric("CHURN", f"{last['churn']:.2f}%")
    c4.metric("MC", f"{last['mc']:.1f}%")
    c5.metric("CAC", f"${last['cac']:.2f}")
    c6.metric("Margen EBITDA", f"{last['margen_ebitda']:.1f}%")

    # 📈 Evolución del EBITDA
    st.subheader("📈 Evolución del EBITDA (USD)")
    st.altair_chart(
        alt.Chart(df).mark_line(point=True, color="#00cc83").encode(
            x="period:N",
            y=alt.Y("ebitda:Q", title="EBITDA (USD)"),
            tooltip=["period", "clientes", "arpu", "mc", "ebitda"]
        ).properties(title="Rentabilidad operativa mensual del ISP"),
        use_container_width=True
    )

    # 📋 Tabla resumen mensual
    st.subheader("📋 Tabla resumen mensual")
    st.dataframe(
        df[["period", "clientes", "arpu", "churn", "mc", "cac", "ltv", "ebitda", "margen_ebitda"]].rename(columns={
            "period": "Período", "clientes": "Clientes", "arpu": "ARPU (USD)", "churn": "CHURN (%)",
            "mc": "MC (%)", "cac": "CAC (USD)", "ltv": "LTV (USD)", "ebitda": "EBITDA (USD)",
            "margen_ebitda": "Margen EBITDA (%)"
        }).style.format({
            "Clientes": "{:,.0f}", "ARPU (USD)": "{:.2f}", "CHURN (%)": "{:.2f}", "MC (%)": "{:.1f}",
            "CAC (USD)": "{:.2f}", "LTV (USD)": "{:.0f}", "EBITDA (USD)": "{:.0f}", "Margen EBITDA (%)": "{:.1f}"
        }),
        use_container_width=True
    )

    # 🔮 Proyección mes a mes
    st.subheader("🔮 Proyección precisa")
    cols = st.columns(3)
    for label, months in [("6 meses", 6), ("12 meses", 12), ("24 meses", 24)]:
        if cols[["6 meses", "12 meses", "24 meses"].index(label)].button(f"📆 {label}"):
            churn_dec = last["churn"] / 100
            mc_dec = last["mc"] / 100
            clientes_ini = last["clientes"]
            clientes_mes, ingresos_mes, ingresos_netos_mes = [], [], []

            clientes_act = clientes_ini
            for _ in range(months):
                ingresos_mes.append(clientes_act * last["arpu"])
                ingresos_netos_mes.append(clientes_act * last["arpu"] * mc_dec)
                clientes_mes.append(clientes_act)
                clientes_act *= (1 - churn_dec)

            clientes_fin = clientes_mes[-1]
            ingresos_tot = sum(ingresos_mes)
            ingresos_netos_tot = sum(ingresos_netos_mes)
            clientes_perdidos = clientes_ini - clientes_fin
            perdida_bruta = clientes_perdidos * last["arpu"] * months
            perdida_neta = perdida_bruta * mc_dec

            st.markdown(f"### 📅 Proyección a {label}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Clientes finales", f"{clientes_fin:,.0f}", f"-{clientes_perdidos:,.0f}", delta_color="inverse")
            c2.metric("Ingresos brutos", f"${ingresos_tot:,.0f}", f"-${perdida_bruta:,.0f}", delta_color="inverse")
            c3.metric("Ingresos netos", f"${ingresos_netos_tot:,.0f}", f"-${perdida_neta:,.0f}", delta_color="inverse")

            # Gráfico de evolución mensual
            df_evo = pd.DataFrame({
                "Mes": list(range(1, months + 1)),
                "Clientes activos": clientes_mes,
                "Ingresos brutos": ingresos_mes,
                "Ingresos netos": ingresos_netos_mes
            })

            chart = alt.layer(
                alt.Chart(df_evo).mark_line(color="#1f77b4", point=True).encode(
                    x="Mes:Q", y="Clientes activos:Q", tooltip=["Mes", "Clientes activos"]
                ),
                alt.Chart(df_evo).mark_line(color="#2ca02c", strokeDash=[5, 3], point=True).encode(
                    x="Mes:Q", y="Ingresos brutos:Q", tooltip=["Mes", "Ingresos brutos"]
                ),
                alt.Chart(df_evo).mark_line(color="#ff7f0e", point=True).encode(
                    x="Mes:Q", y="Ingresos netos:Q", tooltip=["Mes", "Ingresos netos"]
                )
            ).properties(title=f"Evolución mensual de clientes e ingresos — {label}")

            st.altair_chart(chart, use_container_width=True)

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
        else:
            r = sign_in(email_input, password)
        if "error" in r:
            st.sidebar.error(r["error"]["message"])
        else:
            store_session(r)
            ensure_user_doc(r["localId"], r["email"])
            st.sidebar.success("✅ Bienvenido.")
            st.rerun()

if st.sidebar.button("🔑 Restaurar contraseña"):
    if email_input:
        if reset_password(email_input):
            st.sidebar.success("📧 Correo enviado.")
        else:
            st.sidebar.error("Error al enviar el correo.")
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
    for u in list_auth_users():
        doc = ensure_user_doc(u["uid"], u["email"])
        plan = doc.get("plan", {}).get("stringValue", "free")
        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
        c1.markdown(f"**{u['email']}** — Plan `{plan}` — UID `{u['uid']}`")
        if c2.button("Free", key=f"f_{u['uid']}"): update_plan(u["uid"], "free"); st.rerun()
        if c3.button("Pro", key=f"p_{u['uid']}"): update_plan(u["uid"], "pro"); st.rerun()
        if c4.button("Premium", key=f"x_{u['uid']}"): update_plan(u["uid"], "premium"); st.rerun()
        if c5.button("Reset", key=f"r_{u['uid']}"):
            if reset_password(u["email"]): st.success(f"📧 Link enviado a {u['email']}")
            else: st.error(f"No se pudo enviar reset a {u['email']}")
else:
    mostrar_dashboard_free(uid)
