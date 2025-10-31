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

# ====================================
# CONFIG GENERAL
# ====================================
st.set_page_config(page_title="Dashboard ISP", layout="wide")

# ====================================
# FIREBASE ADMIN (solo credenciales)
# ====================================
def init_firebase_admin():
    if not firebase_admin._apps:
        sa = json.loads(json.dumps(dict(st.secrets["FIREBASE"])))
        cred = credentials.Certificate(sa)
        firebase_admin.initialize_app(cred)

def get_id_token():
    """Obtiene un token de acceso para las peticiones REST a Firestore"""
    sa = dict(st.secrets["FIREBASE"])
    aud = "https://firestore.googleapis.com/"
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": firebase_admin.credentials.Certificate(sa).get_access_token().access_token
    }
    return firebase_admin.credentials.Certificate(sa).get_access_token().access_token

# ====================================
# FIRESTORE REST HELPERS
# ====================================
def firestore_request(method, path, data=None):
    """Realiza llamadas REST al endpoint de Firestore"""
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
        return r.json()
    except Exception as e:
        st.error(f"❌ Error de conexión Firestore REST: {e}")
        return None

def save_metrics_rest(uid, period, arpu, churn, mc, cac, clientes):
    path = f"tenants/{uid}/metrics/{period}"
    data = {
        "fields": {
            "period": {"stringValue": period},
            "arpu": {"doubleValue": arpu},
            "churn": {"doubleValue": churn},
            "mc": {"doubleValue": mc},
            "cac": {"doubleValue": cac},
            "clientes": {"integerValue": clientes},
            "created_at": {"integerValue": int(time.time())}
        }
    }
    return firestore_request("PATCH", path, data)

def load_metrics_rest(uid):
    path = f"tenants/{uid}/metrics"
    r = firestore_request("GET", path)
    if not r or "documents" not in r:
        return pd.DataFrame(columns=["period","arpu","churn","mc","cac","clientes"])
    rows = []
    for doc in r["documents"]:
        f = doc["fields"]
        rows.append({
            "period": f["period"]["stringValue"],
            "arpu": float(f["arpu"]["doubleValue"]),
            "churn": float(f["churn"]["doubleValue"]),
            "mc": float(f["mc"]["doubleValue"]),
            "cac": float(f["cac"]["doubleValue"]),
            "clientes": int(f["clientes"]["integerValue"]),
        })
    return pd.DataFrame(rows)

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
# INTERFAZ
# ====================================
st.title("📊 Dashboard ISP — Métricas (Firestore REST)")

uid = "test_user"
st.subheader("📝 Cargar datos mensuales")

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
    res = save_metrics_rest(uid, period, arpu, churn, mc, cac, clientes)
    if res:
        st.success(f"✅ Datos guardados en Firestore ({period})")
    else:
        st.error("❌ Error al guardar datos.")

df = load_metrics_rest(uid)
if df.empty:
    st.info("Sin datos cargados.")
    st.stop()

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
