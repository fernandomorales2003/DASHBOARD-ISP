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
# MÉTRICAS (guardar / leer)
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
            "arpu": float(f.get("arpu", {}).get("doubleValue", 0.0)),
            "churn": float(f.get("churn", {}).get("doubleValue", 0.0)),
            "mc": float(f.get("mc", {}).get("doubleValue", 0.0)),
            "cac": float(f.get("cac", {}).get("doubleValue", 0.0)),
        })
    return pd.DataFrame(rows).sort_values("period")

# =====================================
# PROYECCIÓN (precisa mes a mes)
# =====================================
def proyectar_mes_a_mes(clientes_ini, churn_pct, arpu, mc_pct, months):
    churn_dec = churn_pct / 100.0
    mc_dec = mc_pct / 100.0
    clientes_mes = []
    ingresos_mes = []
    ingresos_netos_mes = []
    perdidos_mes = []
    ingresos_perdidos_mes = []
    c = float(clientes_ini)
    for m in range(1, months + 1):
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
# DASHBOARD FREE (usuario)
# =====================================
# (tu función mostrar_dashboard_free original aquí sin cambios)

# =====================================
# DASHBOARD PREMIUM
# =====================================
def mostrar_dashboard_premium(uid):
    st.header("🚀 Dashboard ISP — Versión PREMIUM")
    st.markdown("Visualización avanzada de métricas y composición de clientes por plan.")

    st.subheader("📦 Distribución de clientes por plan")
    c1, c2, c3, c4, c5 = st.columns(5)
    clientes_100 = c1.number_input("Plan 100 Mb", 0, 100000, 200)
    clientes_200 = c2.number_input("Plan 200 Mb", 0, 100000, 150)
    clientes_300 = c3.number_input("Plan 300 Mb", 0, 100000, 80)
    clientes_wireless = c4.number_input("Clientes Wireless", 0, 100000, 60)
    clientes_corporativo = c5.number_input("Clientes Corporativo", 0, 100000, 10)

    total_clientes = clientes_100 + clientes_200 + clientes_300 + clientes_wireless + clientes_corporativo
    if total_clientes == 0:
        st.warning("Ingresá al menos un valor de clientes para ver los gráficos.")
        st.stop()

    st.subheader("💲 Precio promedio por plan (USD)")
    p1, p2, p3, p4, p5 = st.columns(5)
    precio_100 = p1.number_input("Precio 100 Mb", 0.0, 500.0, 12.0, 0.5)
    precio_200 = p2.number_input("Precio 200 Mb", 0.0, 500.0, 15.0, 0.5)
    precio_300 = p3.number_input("Precio 300 Mb", 0.0, 500.0, 18.0, 0.5)
    precio_wireless = p4.number_input("Precio Wireless", 0.0, 500.0, 20.0, 0.5)
    precio_corporativo = p5.number_input("Precio Corporativo", 0.0, 500.0, 35.0, 0.5)

    df_segmentos = pd.DataFrame([
        {"Plan": "100 Mb", "Clientes": clientes_100, "Precio": precio_100},
        {"Plan": "200 Mb", "Clientes": clientes_200, "Precio": precio_200},
        {"Plan": "300 Mb", "Clientes": clientes_300, "Precio": precio_300},
        {"Plan": "Wireless", "Clientes": clientes_wireless, "Precio": precio_wireless},
        {"Plan": "Corporativo", "Clientes": clientes_corporativo, "Precio": precio_corporativo},
    ])

    df_segmentos["Ingreso"] = df_segmentos["Clientes"] * df_segmentos["Precio"]
    ingreso_total = df_segmentos["Ingreso"].sum()
    df_segmentos["Aporte_ARPU_%"] = (df_segmentos["Ingreso"] / ingreso_total) * 100
    df_segmentos["Clientes_%"] = (df_segmentos["Clientes"] / total_clientes) * 100

    st.subheader("📊 Visualizaciones de distribución")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Distribución de clientes por plan**")
        pie = (
            alt.Chart(df_segmentos)
            .mark_arc(innerRadius=50)
            .encode(
                theta=alt.Theta("Clientes_%:Q", title="Participación"),
                color=alt.Color("Plan:N", scale=alt.Scale(range=["#7B3CEB", "#3A0CA3", "#00CC83", "#FFB703", "#FF3C3C"])),
                tooltip=["Plan", "Clientes", alt.Tooltip("Clientes_%:Q", format=".1f")]
            )
            .properties(height=300, width="container")
        )
        st.altair_chart(pie, use_container_width=True)

    with col2:
        st.markdown("**Aporte al ARPU por tipo de cliente**")
        bars = (
            alt.Chart(df_segmentos)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusBottomLeft=4)
            .encode(
                x=alt.X("Aporte_ARPU_%:Q", title="Aporte al ARPU (%)"),
                y=alt.Y("Plan:N", sort="-x"),
                color=alt.Color("Plan:N", scale=alt.Scale(range=["#7B3CEB", "#3A0CA3", "#00CC83", "#FFB703", "#FF3C3C"]), legend=None),
                tooltip=["Plan", alt.Tooltip("Aporte_ARPU_%:Q", format=".1f"), "Clientes", "Precio"]
            )
            .properties(height=300)
        )
        st.altair_chart(bars, use_container_width=True)

    st.subheader("📋 Resumen de segmentación")
    st.dataframe(
        df_segmentos[["Plan", "Clientes", "Precio", "Clientes_%", "Aporte_ARPU_%"]]
        .style.format({"Clientes_%": "{:.1f}%", "Aporte_ARPU_%": "{:.1f}%", "Precio": "${:.2f}"}),
        use_container_width=True,
    )

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
            st.sidebar.success("📧 Correo de recuperación enviado.")
        else:
            st.sidebar.error("Error al enviar el correo.")
    else:
        st.sidebar.warning("Ingresá tu correo antes.")

# =====================================
# GATE
# =====================================
if "auth" not in st.session_state:
    st.stop()

uid = st.session_state["auth"]["uid"]
email = st.session_state["auth"]["email"]
is_admin = (email == st.secrets["ADMIN"]["email"])
if is_admin:
    st.sidebar.success("👑 Modo administrador activo")
else:
    st.sidebar.info(f"Usuario: {email}")

# =====================================
# ADMIN / USER DASHBOARD SELECTION
# =====================================
from firebase_admin import firestore

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
            if u["email"] and reset_password(u["email"]):
                st.success(f"📧 Link enviado a {u['email']}")
            else:
                st.error(f"No se pudo enviar reset a {u['email'] or '(sin email)'}")
else:
    # 🔍 Lectura directa de Firestore con el SDK oficial
    db = firestore.client()
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    plan = "free"
    if user_doc.exists:
        data = user_doc.to_dict()
        plan = data.get("plan", "free")

    st.sidebar.markdown(f"**Plan actual:** `{plan}`")

    if plan.lower() == "premium":
        mostrar_dashboard_premium(uid)
    else:
        mostrar_dashboard_free(uid)
