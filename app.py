import os
import json
import time
import streamlit as st
import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore

st.set_page_config(page_title="🔥 Test Firestore", layout="centered")

st.title("🔍 Test de conexión Firestore")

# ===============================
# Inicialización Firebase Admin
# ===============================
def init_firebase_admin():
    try:
        if not firebase_admin._apps:
            sa = json.loads(json.dumps(dict(st.secrets["FIREBASE"])))
            cred = credentials.Certificate(sa)
            firebase_admin.initialize_app(cred)
        st.success("✅ Firebase Admin inicializado correctamente.")
    except Exception as e:
        st.error(f"❌ Error al inicializar Firebase: {e}")

# ===============================
# Conexión Firestore
# ===============================
def get_db():
    try:
        init_firebase_admin()
        project_id = st.secrets["FIREBASE"]["project_id"]
        os.environ["GCLOUD_PROJECT"] = project_id
        db = firestore.Client(project=project_id)
        st.write("🔗 Firestore conectado al proyecto:", project_id)
        return db
    except Exception as e:
        st.error(f"❌ Error al conectar con Firestore: {e}")
        return None

# ===============================
# Prueba de escritura / lectura
# ===============================
def test_firestore(uid="test_user"):
    db = get_db()
    if not db:
        st.stop()

    st.write("📦 Probando escritura y lectura...")

    try:
        test_ref = db.collection("tenants").document(uid).collection("metrics").document("2025-10")
        data = {
            "period": "2025-10",
            "arpu": 16,
            "churn": 2.0,
            "mc": 60,
            "cac": 150,
            "clientes": 1000,
            "created_at": int(time.time())
        }

        st.code(data, language="python")
        test_ref.set(data)
        st.success("✅ Documento escrito correctamente en Firestore.")

        docs = db.collection("tenants").document(uid).collection("metrics").stream()
        rows = [doc.to_dict() for doc in docs]
        st.write("📄 Documentos recuperados:")
        st.json(rows)
        if rows:
            st.success("✅ Lectura exitosa. Firestore operativo.")
        else:
            st.warning("⚠️ Se conectó, pero no devolvió documentos.")
    except Exception as e:
        st.error(f"❌ Error al guardar o leer en Firestore: {e}")

# ===============================
# Interfaz Streamlit
# ===============================
if st.button("🚀 Ejecutar test Firestore"):
    test_firestore()
else:
    st.info("Presioná el botón para iniciar la prueba.")
