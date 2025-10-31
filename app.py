import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Prueba de Proyección ISP", layout="wide")

# ===============================
# DATOS DE PRUEBA
# ===============================
st.title("📊 Mini prueba — Proyección ISP")

arpu = 16.0       # USD
churn = 2.0       # %
mc = 60.0         # %
clientes = 1000   # cantidad actual

st.markdown(f"""
**Datos base**
- ARPU: ${arpu}
- CHURN: {churn}%
- MC: {mc}%
- Clientes actuales: {clientes}
""")

# ===============================
# BOTONES DE PROYECCIÓN
# ===============================
st.markdown("---")
st.subheader("📆 Elegí horizonte de proyección")

col1, col2, col3 = st.columns(3)
horizonte = None
if col1.button("📆 Proyectar 6 meses"):
    horizonte = 6
elif col2.button("📆 Proyectar 1 año"):
    horizonte = 12
elif col3.button("📆 Proyectar 2 años"):
    horizonte = 24

# ===============================
# CÁLCULO Y RESULTADOS
# ===============================
if horizonte:
    churn_dec = churn / 100
    mc_dec = mc / 100

    clientes_ini = clientes
    clientes_fin = clientes_ini * ((1 - churn_dec) ** horizonte)
    clientes_prom = (clientes_ini + clientes_fin) / 2
    ingresos_brutos = clientes_prom * arpu * horizonte
    ingresos_netos = ingresos_brutos * mc_dec
    ltv_meses = 1 / churn_dec

    st.markdown(f"### 📈 Resultados a {horizonte} meses")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clientes finales", f"{clientes_fin:,.0f}", f"-{(1 - clientes_fin/clientes_ini)*100:.1f}%")
    c2.metric("Ingresos brutos", f"${ingresos_brutos:,.0f}")
    c3.metric("Ingresos netos (MC%)", f"${ingresos_netos:,.0f}")
    c4.metric("Tiempo de vida (LTV)", f"{ltv_meses:.1f} meses")

    # ===============================
    # GRÁFICO DE EVOLUCIÓN
    # ===============================
    meses = list(range(horizonte + 1))
    clientes_mes = [clientes_ini * ((1 - churn_dec) ** m) for m in meses]
    df_proj = pd.DataFrame({"Mes": meses, "Clientes": clientes_mes})

    chart_proj = (
        alt.Chart(df_proj)
        .mark_line(point=True, color="#4fb4ca")
        .encode(x="Mes:Q", y="Clientes:Q")
        .properties(title=f"Evolución de clientes proyectados ({horizonte} meses)")
    )
    st.altair_chart(chart_proj, use_container_width=True)
