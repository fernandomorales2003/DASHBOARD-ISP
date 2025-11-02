import os
import time
import json
import requests
import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, auth
from datetime import datetime

st.set_page_config(page_title="Dashboard ISP — Admin + Login", layout="wide")

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

        # ✅ Manejo del 404 con aviso informativo
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
    """Devuelve lista de dicts con uid y email desde Firebase Auth."""
    init_firebase_admin()
    out = []
    page = auth.list_users()
    while page:
        for u in page.users:
            out.append({"uid": u.uid, "email": u.email or ""})
        page = page.get_next_page()
    return out

def get_user_doc(uid):
    """Lee users/{uid} de Firestore."""
    r = firestore_request("GET", f"users/{uid}")
    return r.get("fields") if (r and "fields" in r) else None

def ensure_user_doc(uid, email):
    """Asegura que exista users/{uid} con email y plan free."""
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
    """Actualiza el plan preservando el email."""
    fields = get_user_doc(uid)
    email = ""
    if fields and "email" in fields:
        email = fields["email"].get("stringValue", "")
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

# Reset password
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

# =====================================
# ADMIN CHECK
# =====================================
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
            "uid": u["uid"],
            "email": u["email"],
            "plan": plan,
            "fecha": datetime.fromtimestamp(int(fields.get("fecha_registro", {}).get("integerValue", "0"))).strftime("%Y-%m-%d") if "fecha_registro" in fields else "-"
        })

    df_users = pd.DataFrame(merged).sort_values("email")
    st.dataframe(df_users, use_container_width=True)

    st.markdown("### Cambiar plan / Reset contraseña")
    for user in merged:
        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
        with c1:
            st.markdown(f"**{user['email']}** — Plan: `{user['plan']}` — UID: `{user['uid']}`")
        with c2:
            if st.button("🪙 Free", key=f"free_{user['uid']}"):
                update_plan(user["uid"], "free")
                st.rerun()
        with c3:
            if st.button("🚀 Pro", key=f"pro_{user['uid']}"):
                update_plan(user["uid"], "pro")
                st.rerun()
        with c4:
            if st.button("💎 Premium", key=f"prem_{user['uid']}"):
                update_plan(user["uid"], "premium")
                st.rerun()
        with c5:
            if st.button("🔑 Reset", key=f"reset_{user['uid']}"):
                if user["email"] and reset_password(user["email"]):
                    st.success(f"📧 Link enviado a {user['email']}")
                else:
                    st.error(f"No se pudo enviar reset a {user['email'] or '(sin email)'}")

# =====================================
# PANEL DE USUARIO NORMAL
# =====================================
else:
    st.header("🌱 Panel de usuario")
    fields = ensure_user_doc(uid, logged_email)
    plan = fields.get("plan", {}).get("stringValue", "free")
    st.info(f"Tu plan actual es: **{plan.upper()}**")
    st.write("🔹 Aquí podrás ver tus indicadores financieros y técnicos según el plan.")
