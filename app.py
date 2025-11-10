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
# VISUALIZACIÓN PRINCIPAL
# =======================
st.markdown("---")
st.header("📊 Visualizaciones principales")

left_col, right_col = st.columns([0.6, 0.4])

# ---- 60%: Gráficos circulares más gruesos ----
with left_col:
    st.subheader("Distribución de clientes por plan (individual)")
    color_map = {
        "100 Mb": "#7B3CEB",
        "200 Mb": "#3A0CA3",
        "300 Mb": "#00CC83",
        "Wireless": "#FFB703",
        "Corporativo": "#FF3C3C",
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
            .mark_arc(innerRadius=30, outerRadius=90)
            .encode(
                theta=alt.Theta("Valor:Q", stack=True),
                color=alt.Color(
                    "Etiqueta:N",
                    scale=alt.Scale(range=[color, "#E0E0E0"]),
                    legend=None
                ),
            )
            .properties(height=180, width=180)
        )

        text = (
            alt.Chart(pd.DataFrame({"text": [f"{percent:.1f}%"]}))
            .mark_text(
                text=f"{percent:.1f}%",
                fontSize=16,
                fontWeight="bold",
                color=color,
                align="center",
                baseline="middle"
            )
            .properties(height=180, width=180)
        )

        with cols[idx]:
            st.markdown(f"**{plan}**")
            st.altair_chart(chart + text, use_container_width=True)
            st.caption(f"{percent:.1f}% del total")

# ---- 40%: Aporte ARPU ----
with right_col:
    st.subheader("Aporte al ARPU por tipo de cliente")
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusBottomLeft=6)
        .encode(
            x=alt.X("% Aporte ARPU:Q", title="Aporte al ARPU (%)"),
            y=alt.Y("Plan:N", sort="-x"),
            color=alt.Color(
                "Plan:N",
                legend=None,
                scale=alt.Scale(domain=list(color_map.keys()), range=list(color_map.values())),
            ),
            tooltip=["Plan", alt.Tooltip("% Aporte ARPU:Q", format=".1f"), "Clientes", "Precio"],
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
# KPIs / PROYECCIONES
# =======================
st.markdown("---")
st.header("Indicadores y Proyecciones")

# Cálculos base
churn = 2.3
mc = 60
cac = 10.5
ltv = (df["Ingresos"].sum() / total_clientes) * (mc / 100) / (churn / 100)
ltv_cac = ltv / cac
clientes_perdidos = total_clientes * (churn / 100)
ingresos_perdidos = clientes_perdidos * (df["Ingresos"].sum() / total_clientes)

# Tarjetas de indicadores
colA, colB, colC, colD = st.columns(4)

card_style = """
background: linear-gradient(135deg, {color1}, {color2});
padding: 14px;
border-radius: 12px;
text-align: center;
color: white;
font-weight: bold;
font-size: 13px;
box-shadow: 0px 3px 8px rgba(0,0,0,0.18);
margin-bottom: 20px;
"""

colors = [
    ("#6D28D9", "#A78BFA"),
    ("#7C3AED", "#C084FC"),
    ("#5B21B6", "#818CF8"),
    ("#312E81", "#6366F1"),
]

with colA:
    st.markdown(
        f"""
        <div style="{card_style.format(color1=colors[0][0], color2=colors[0][1])}">
            <div>ARPU Actual</div>
            <div style='font-size:24px;margin-top:4px;'>${df["Ingresos"].sum() / total_clientes:,.2f}</div>
            <div style='font-size:11px;margin-top:2px;'>Objetivo $23</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with colB:
    st.markdown(
        f"""
        <div style="{card_style.format(color1=colors[1][0], color2=colors[1][1])}">
            <div>CHURN Rate</div>
            <div style='font-size:24px;margin-top:4px;'>{churn:.2f}%</div>
            <div style='font-size:11px;margin-top:2px;'>{clientes_perdidos:,.0f} clientes perdidos</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with colC:
    st.markdown(
        f"""
        <div style="{card_style.format(color1=colors[2][0], color2=colors[2][1])}">
            <div>LTV / CAC</div>
            <div style='font-size:24px;margin-top:4px;'>{ltv_cac:.2f}x</div>
            <div style='font-size:11px;margin-top:2px;'>Alarma &lt; 3x</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with colD:
    st.markdown(
        f"""
        <div style="{card_style.format(color1=colors[3][0], color2=colors[3][1])}">
            <div>Clientes Totales</div>
            <div style='font-size:24px;margin-top:4px;'>{total_clientes:,}</div>
            <div style='font-size:11px;margin-top:2px;'>Meta: +500 clientes</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("📊 **Dashboard demo listo para presentación (vista Premium).**")
