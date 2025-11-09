import streamlit as st
import pandas as pd
import altair as alt
import math

st.set_page_config(page_title="Dashboard ISP — Vista Premium", layout="wide")

st.title("🚀 Dashboard ISP — Versión PREMIUM (Demo Visual)")

# =======================
# DISTRIBUCIÓN DE CLIENTES
# =======================
st.header("📦 Distribución de clientes por plan")

col1, col2, col3, col4, col5 = st.columns(5)
clientes_100 = col1.number_input("Plan 100 Mb", 0, 100000, 200)
clientes_200 = col2.number_input("Plan 200 Mb", 0, 100000, 150)
clientes_300 = col3.number_input("Plan 300 Mb", 0, 100000, 80)
clientes_wireless = col4.number_input("Clientes Wireless", 0, 100000, 60)
clientes_corporativo = col5.number_input("Clientes Corporativo", 0, 100000, 10)

total_clientes = clientes_100 + clientes_200 + clientes_300 + clientes_wireless + clientes_corporativo

if total_clientes == 0:
    st.warning("Ingresá valores para mostrar los gráficos.")
    st.stop()

# =======================
# PRECIOS PROMEDIO
# =======================
st.header("💲 Precio promedio por plan (USD)")

p1, p2, p3, p4, p5 = st.columns(5)
precio_100 = p1.number_input("Precio 100 Mb", 0.0, 500.0, 12.0, 0.5)
precio_200 = p2.number_input("Precio 200 Mb", 0.0, 500.0, 15.0, 0.5)
precio_300 = p3.number_input("Precio 300 Mb", 0.0, 500.0, 18.0, 0.5)
precio_wireless = p4.number_input("Precio Wireless", 0.0, 500.0, 20.0, 0.5)
precio_corporativo = p5.number_input("Precio Corporativo", 0.0, 500.0, 35.0, 0.5)

# =======================
# DATAFRAME DE PLANES
# =======================
df = pd.DataFrame([
    {"Plan": "100 Mb", "Clientes": clientes_100, "Precio": precio_100},
    {"Plan": "200 Mb", "Clientes": clientes_200, "Precio": precio_200},
    {"Plan": "300 Mb", "Clientes": clientes_300, "Precio": precio_300},
    {"Plan": "Wireless", "Clientes": clientes_wireless, "Precio": precio_wireless},
    {"Plan": "Corporativo", "Clientes": clientes_corporativo, "Precio": precio_corporativo},
])

df["Ingresos"] = df["Clientes"] * df["Precio"]
df["% Clientes"] = (df["Clientes"] / total_clientes) * 100
df["% Aporte ARPU"] = (df["Ingresos"] / df["Ingresos"].sum()) * 100

# =======================
# CÁLCULOS PRINCIPALES
# =======================
arpu = df["Ingresos"].sum() / total_clientes
churn = 2.3
mc = 60
cac = 10.5
ltv = (arpu * (mc / 100)) / (churn / 100)
ltv_cac = ltv / cac
clientes_perdidos = total_clientes * (churn / 100)
ingresos_perdidos = clientes_perdidos * arpu

# =======================
# FILA 1 - VISUALIZACIONES PRINCIPALES
# =======================
st.markdown("---")
st.header("📊 Visualizaciones principales")

left_col, right_col = st.columns([0.6, 0.4])

with left_col:
    st.subheader("Distribución de clientes por plan (individual)")
    color_map = {
        "100 Mb": "#7B3CEB",
        "200 Mb": "#3A0CA3",
        "300 Mb": "#00CC83",
        "Wireless": "#FFB703",
        "Corporativo": "#FF3C3C"
    }

    col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)
    cols = [col_p1, col_p2, col_p3, col_p4, col_p5]

    for idx, row in df.iterrows():
        plan = row["Plan"]
        percent = row["% Clientes"]
        color = color_map.get(plan, "#999999")

        single_df = pd.DataFrame({
            "Etiqueta": [plan, "Resto"],
            "Valor": [percent, 100 - percent]
        })

        chart = (
            alt.Chart(single_df)
            .mark_arc(innerRadius=60)
            .encode(
                theta=alt.Theta("Valor:Q", stack=True),
                color=alt.Color("Etiqueta:N", scale=alt.Scale(range=[color, "#E0E0E0"]), legend=None),
            )
            .properties(height=180, width=180)
        )

        with cols[idx]:
            st.markdown(f"**{plan}**")
            st.altair_chart(chart, use_container_width=True)
            st.caption(f"{percent:.1f}% del total")

with right_col:
    st.subheader("Aporte al ARPU por tipo de cliente")
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusBottomLeft=6)
        .encode(
            x=alt.X("% Aporte ARPU:Q", title="Aporte al ARPU (%)"),
            y=alt.Y("Plan:N", sort="-x"),
            color=alt.Color("Plan:N", legend=None,
                            scale=alt.Scale(domain=list(color_map.keys()), range=list(color_map.values()))),
            tooltip=["Plan", alt.Tooltip("% Aporte ARPU:Q", format=".1f"), "Clientes", "Precio"]
        )
        .properties(height=400)
    )

    text = bars.mark_text(
        align="left",
        baseline="middle",
        dx=3,
        color="white"
    ).encode(text=alt.Text("% Aporte ARPU:Q", format=".1f"))

    st.altair_chart(bars + text, use_container_width=True)

# =======================
# FILA 2 - TARJETAS + CLIENTES PERDIDOS + PROYECCIÓN
# =======================
st.markdown("---")
st.header("📈 Indicadores y Proyecciones")

colA, colB, colC = st.columns(3)

# --- Columna 1: Tarjetas (en bloque vertical) ---
with colA:
    st.markdown("#### 💡 Indicadores Financieros")
    card_style = """
    background: linear-gradient(135deg, {color1}, {color2});
    padding: 20px;
    border-radius: 15px;
    text-align: center;
    color: white;
    font-weight: bold;
    margin-bottom: 10px;
    """
    st.markdown(f"<div style='{card_style.format(color1='#4facfe', color2='#00f2fe')}'><h4>ARPU</h4><h2>${arpu:,.2f}</h2></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='{card_style.format(color1='#f7971e', color2='#ffd200')}'><h4>CHURN</h4><h2>{churn:.2f}%</h2><p>{clientes_perdidos:,.0f} clientes perdidos</p></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='{card_style.format(color1='#a18cd1', color2='#fbc2eb')}'><h4>LTV/CAC</h4><h2>{ltv_cac:.2f}x</h2></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='{card_style.format(color1='#43cea2', color2='#185a9d')}'><h4>Clientes Totales</h4><h2>{total_clientes:,}</h2></div>", unsafe_allow_html=True)

# --- Columna 2: Clientes perdidos por plan ---
with colB:
    st.markdown("#### 📉 Clientes perdidos por plan")
    df_perdidos = df.copy()
    df_perdidos["Perdidos"] = df_perdidos["Clientes"] * (churn / 100)

    pie = (
        alt.Chart(df_perdidos)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta("Perdidos:Q"),
            color=alt.Color("Plan:N", scale=alt.Scale(domain=list(color_map.keys()), range=list(color_map.values()))),
            tooltip=["Plan", alt.Tooltip("Perdidos:Q", format=",.0f")]
        )
        .properties(height=300)
    )
    st.altair_chart(pie, use_container_width=True)

# --- Columna 3: Proyecciones (semi-donas horizontales) ---
with colC:
    st.markdown("#### 🔮 Proyecciones")
    import numpy as np

    def semicircular_chart(label, porcentaje, color1, color2):
        chart_df = pd.DataFrame({"angle": [porcentaje, 100 - porcentaje], "tipo": [label, "Restante"]})
        return (
            alt.Chart(chart_df)
            .mark_arc(innerRadius=50, outerRadius=80)
            .encode(
                theta=alt.Theta("angle:Q", stack=True),
                color=alt.Color("tipo:N", scale=alt.Scale(range=[color1, "#E0E0E0"]), legend=None)
            )
            .properties(width=120, height=80)
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**Clientes Proy.**")
        st.altair_chart(semicircular_chart("Clientes", 85, "#4facfe", "#00f2fe"), use_container_width=True)

    with c2:
        st.markdown("**ARPU Proy.**")
        st.altair_chart(semicircular_chart("ARPU", 88, "#a18cd1", "#fbc2eb"), use_container_width=True)

    with c3:
        st.markdown("**Ingresos Perdidos**")
        st.altair_chart(semicircular_chart("Ingresos", 92, "#FF3C3C", "#FFB703"), use_container_width=True)
