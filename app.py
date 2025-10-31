import os
import time
import json
import requests
import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials
from datetime import datetime

st.set_page_config(page_title="Dashboard ISP — Admin Panel", layout="wide")

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
# FIREBASE AUTH REST
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
st.title("📊 Dashboard ISP — Login")

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
                uid = r["localId"]
                firestore_request("PATCH", f"users/{uid}", {
                    "fields": {
                        "email": {"stringValue": email},
                        "plan": {"stringValue": "free"},
                        "fecha_registro": {"integerValue": int(time.time())}
                    }
                })
                st.sidebar.success("✅ Usuario creado con plan FREE.")
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
# ADMIN CHECK
# =====================================
is_admin = email == st.secrets["ADMIN"]["email"]

if is_admin:
    st.sidebar.success("👑 Modo administrador activo")
else:
    st.sidebar.info(f"Usuario: {email}")

# =====================================
# PANEL ADMINISTRADOR
# =====================================
if is_admin:
    st.header("👥 Panel de administración de usuarios")

    res = firestore_request("GET", "users")
    if not res or "documents" not in res:
        st.warning("No se encontraron usuarios.")
    else:
        users = []
        for doc in res["documents"]:
            f = doc["fields"]
            users.append({
                "uid": doc["name"].split("/")[-1],
                "email": f.get("email", {}).get("stringValue", ""),
                "plan": f.get("plan", {}).get("stringValue", "free"),
                "fecha": datetime.fromtimestamp(int(f.get("fecha_registro", {}).get("integerValue", "0"))).strftime("%Y-%m-%d")
            })

        df_users = pd.DataFrame(users)
        st.dataframe(df_users, use_container_width=True)

        for user in users:
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            with c1:
                st.markdown(f"**{user['email']}** — Plan: `{user['plan']}`")
            with c2:
                if st.button("🪙 Free", key=f"free_{user['uid']}"):
                    firestore_request("PATCH", f"users/{user['uid']}", {"fields": {"plan": {"stringValue": "free"}}})
                    st.success(f"Actualizado a FREE → {user['email']}")
                    st.rerun()
            with c3:
                if st.button("🚀 Pro", key=f"pro_{user['uid']}"):
                    firestore_request("PATCH", f"users/{user['uid']}", {"fields": {"plan": {"stringValue": "pro"}}})
                    st.success(f"Actualizado a PRO → {user['email']}")
                    st.rerun()
            with c4:
                if st.button("💎 Premium", key=f"prem_{user['uid']}"):
                    firestore_request("PATCH", f"users/{user['uid']}", {"fields": {"plan": {"stringValue": "premium"}}})
                    st.success(f"Actualizado a PREMIUM → {user['email']}")
                    st.rerun()

else:
    st.header("🌱 Panel de usuario")
    st.info("Versión Free / Pro / Premium según tu plan.")
