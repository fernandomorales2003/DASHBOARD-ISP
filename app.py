import streamlit as st
import pandas as pd
import altair as alt

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
# LAYOUT DE GRÁFICOS
# =======================
st.header("📊 Visualizaciones")

left_col, right_col = st.columns([0.6, 0.4])  # 60% / 40%

# ---- 60%: GRÁFICOS CIRCULARES UNO AL LADO DEL OTRO ----
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

# ---- 40%: GRÁFICO DE BARRAS (APORTE ARPU) ----
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
# FILA 2: INDICADORES CLAVE EN GRÁFICOS
# =======================
st.header("📈 Indicadores clave (simulados)")

# Datos simulados
arpu = df["Ingresos"].sum() / total_clientes
churn = 2.3
clientes_actuales = total_clientes
objetivo_arpu = 23
max_churn = 3
max_clientes = clientes_actuales + 500

indicadores = pd.DataFrame([
    {"Indicador": "ARPU (USD)", "Actual": arpu, "Objetivo": objetivo_arpu},
    {"Indicador": "CHURN (%)", "Actual": churn, "Objetivo": max_churn},
    {"Indicador": "Clientes", "Actual": clientes_actuales, "Objetivo": max_clientes}
])

# Crear gráfico de barras horizontales
st.subheader("📊 Comparativa de indicadores vs objetivos")
chart_indicadores = (
    alt.Chart(indicadores)
    .transform_fold(
        ["Actual", "Objetivo"],
        as_=["Tipo", "Valor"]
    )
    .mark_bar(size=25)
    .encode(
        y=alt.Y("Indicador:N", title=None, sort=["ARPU (USD)", "CHURN (%)", "Clientes"]),
        x=alt.X("Valor:Q", title="Valor"),
        color=alt.Color("Tipo:N", scale=alt.Scale(domain=["Actual", "Objetivo"], range=["#00CC83", "#E0E0E0"])),
        tooltip=["Indicador", "Tipo", alt.Tooltip("Valor:Q", format=".2f")]
    )
    .properties(height=180)
)

# Texto sobre las barras
text_indicadores = chart_indicadores.mark_text(
    align="left",
    baseline="middle",
    dx=3,
    color="black"
).encode(text=alt.Text("Valor:Q", format=".1f"))

st.altair_chart(chart_indicadores + text_indicadores, use_container_width=True)

# =======================
# EBITDA FINAL
# =======================
st.markdown("---")
st.subheader("💹 EBITDA y Participación por Segmento")

mc = 60
df["EBITDA"] = df["Ingresos"] * (mc / 100)
bar2 = (
    alt.Chart(df)
    .mark_bar()
    .encode(
        x=alt.X("Plan:N", sort="-y"),
        y=alt.Y("EBITDA:Q", title="EBITDA (USD)"),
        color=alt.Color("Plan:N", legend=None,
                        scale=alt.Scale(domain=list(color_map.keys()), range=list(color_map.values()))),
        tooltip=["Plan", alt.Tooltip("EBITDA:Q", format=",.0f"), "Clientes"]
    )
    .properties(height=350)
)
st.altair_chart(bar2, use_container_width=True)

st.markdown("📊 **Dashboard demo listo para presentación (vista Premium).**")
