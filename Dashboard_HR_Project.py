import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from io import BytesIO
from pandas.tseries.offsets import MonthEnd

# -------------------------
# CONFIG: activar datos ficticios
# -------------------------
USE_FAKE = True
SEED = 42
np.random.seed(SEED)

# -------------------------
# 1. Cargar datos
# -------------------------
hc_df    = pd.read_excel("Data.xlsx", sheet_name="HC")
bajas_df = pd.read_excel("Data.xlsx", sheet_name="Bajas")

# -------------------------
# 2. Consolidar base
# -------------------------
cols = [
    "N. EMPLOYEE", "DATE OF BIRTH", "GENDER", "HIRE DATE",
    "FUNCTION", "COUNTRY P&L", "ADMINISTRATIVO - ALMACEN - TRAINEE",
    "AREA", "COST CENTER", "LOCATION", "JOB LEVEL"
]
hc    = hc_df[cols].copy()
bajas = bajas_df[cols + ["LAST DAY OF WORK", "EXIT TYPE"]].copy()
hc["LAST DAY OF WORK"] = pd.NaT
hc["EXIT TYPE"]        = np.nan
base = pd.concat([hc, bajas], ignore_index=True)
base["HIRE DATE"]        = pd.to_datetime(base["HIRE DATE"], errors="coerce")
base["LAST DAY OF WORK"] = pd.to_datetime(base["LAST DAY OF WORK"], errors="coerce")
base["DATE OF BIRTH"]    = pd.to_datetime(base["DATE OF BIRTH"], errors="coerce")

# -------------------------
# 3. Generar datos ficticios
# -------------------------
if USE_FAKE:
    # Anonimizar cost centers
    unique_cc = base["COST CENTER"].dropna().unique()
    cc_map = {cc: f"CC_{i+1}" for i, cc in enumerate(unique_cc)}
    base["COST CENTER"] = base["COST CENTER"].map(cc_map).fillna("CC_Unknown")

    # Anonimizar location
    unique_loc = base["LOCATION"].dropna().unique()
    loc_map = {loc: f"LOC_{i+1}" for i, loc in enumerate(unique_loc)}
    base["LOCATION"] = base["LOCATION"].map(loc_map).fillna("LOC_Unknown")

    # Desfasar fechas aleatoriamente ±180 días
    base["HIRE DATE"] += pd.to_timedelta(
        np.random.randint(-180, 180, len(base)), unit="d"
    )
    mask_exit = ~base["LAST DAY OF WORK"].isna()
    base.loc[mask_exit, "LAST DAY OF WORK"] += pd.to_timedelta(
        np.random.randint(-180, 180, mask_exit.sum()), unit="d"
    )

# -------------------------
# 4. KPIs y series mensuales
# -------------------------
fechas  = pd.date_range(start="2022-01-31", end=pd.Timestamp.today(), freq="M")
resumen = []
for fecha in fechas:
    if USE_FAKE:
        hc_end = int(np.random.uniform(80, 200))
        hires  = int(np.random.uniform(0, 30))
        terms  = int(np.random.uniform(0, 30))
    else:
        ventana  = MonthEnd(1)
        hc_start = base[(base["HIRE DATE"] < fecha) & ((base["LAST DAY OF WORK"].isna()) | (base["LAST DAY OF WORK"] >= fecha))]
        hc_end   = base[(base["HIRE DATE"] <= fecha) & ((base["LAST DAY OF WORK"].isna()) | (base["LAST DAY OF WORK"] > fecha))]
        hires    = base[(base["HIRE DATE"] >= fecha - ventana) & (base["HIRE DATE"] <= fecha)].shape[0]
        terms    = base[(base["LAST DAY OF WORK"] >= fecha - ventana) & (base["LAST DAY OF WORK"] <= fecha)].shape[0]
        hc_end = len(hc_end)

    avg_hc = (hc_end + (resumen[-1]["Headcount End"] if resumen else hc_end)) / 2
    resumen.append({
        "Month": fecha,
        "Headcount End":   hc_end,
        "Hires":            hires,
        "Terminations":     terms,
        "Turnover Rate":    terms / avg_hc             if avg_hc else 0,
        "Hire Rate":        hires / avg_hc            if avg_hc else 0,
        "Early Turnover Rate": (terms * 0.1) / avg_hc if avg_hc else 0
    })
df_resumen = pd.DataFrame(resumen)

# -------------------------
# 5. Desglose por segmento
# -------------------------
def build_group_df(group_col):
    recs = []
    for fecha in fechas:
        total_hc_end = df_resumen.loc[df_resumen["Month"] == fecha, "Headcount End"].values[0]
        for val in base[group_col].dropna().unique():
            if USE_FAKE:
                cnt = int(np.random.uniform(0, 10))
            else:
                ventana = MonthEnd(1)
                terms = base[
                    (base["LAST DAY OF WORK"] >= fecha - ventana) &
                    (base["LAST DAY OF WORK"] <= fecha) &
                    (base[group_col] == val)
                ]
                cnt = len(terms)
            rate = cnt / total_hc_end if total_hc_end else 0
            recs.append({"Month": fecha, group_col: val, "Term Count": cnt, "Rate": rate})
    return pd.DataFrame(recs)

df_gender = build_group_df("GENDER")
df_cost   = build_group_df("COST CENTER")
df_exit   = build_group_df("EXIT TYPE")

# -------------------------
# 6. Template de colores Plotly
# -------------------------
custom_template = dict(
    layout=go.Layout(
        font=dict(family="Arial", size=14, color="#2B2B2B"),
        paper_bgcolor="#F7F7F7",
        plot_bgcolor="#F7F7F7",
        xaxis=dict(showgrid=True, gridcolor="#BDC3C7", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#BDC3C7", zeroline=False),
        colorway=["#5D6D7E", "#4F4F4F", "#A0A0A0", "#1C1C1C"]
    )
)

# -------------------------
# 7. Dashboard completo
# -------------------------
def render_dashboard():
    st.set_page_config(layout="wide", page_title="HR Analytics Sample")

    # Logo y título
    st.image("Personal_logo.jpg", width=150)
    st.markdown(
        "<h1 style='text-align: center; color: #4F4F4F;'>📊 HR Analytics Dashboard</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<h4 style='text-align: center; color: #5D6D7E;'>This is a project sample for HR analytics – turn your HR data into actionable insights</h4>",
        unsafe_allow_html=True
    )

    # KPI cards
    active       = base[base["LAST DAY OF WORK"].isna()]
    total_active = len(active)
    gender_cnt   = active["GENDER"].value_counts()
    loc_cnt      = active["LOCATION"].value_counts()

    c0, c1, c2 = st.columns(3)
    c0.metric("👥 Headcount Actual", total_active)
    c1.metric("♂ Hombres", int(gender_cnt.get("Male", 0)))
    c2.metric("♀ Mujeres", int(gender_cnt.get("Female", 0)))

    st.markdown("### 📍 Location")
    loc_cols = st.columns(len(loc_cnt))
    for col, (loc, cnt) in zip(loc_cols, loc_cnt.items()):
        col.metric(loc, cnt)

    # Charts: Hires & Terms
    st.markdown("### 📈 Descriptive Monthly Data")
    ch, ct = st.columns(2)
    with ch:
        fig_h = px.bar(df_resumen, x="Month", y="Hires", text="Hires", labels={"Hires": "# Altas"})
        fig_h.update_layout(xaxis_tickformat="%b %Y", title="Hires per Month", title_x=0.5, template=custom_template)
        st.plotly_chart(fig_h, use_container_width=True)
    with ct:
        fig_t = px.bar(df_resumen, x="Month", y="Terminations", text="Terminations", labels={"Terminations": "# Bajas"})
        fig_t.update_layout(xaxis_tickformat="%b %Y", title="Turnover", title_x=0.5, template=custom_template)
        st.plotly_chart(fig_t, use_container_width=True)

    # Exit Type bar
    st.markdown("### 📊 Turnover Type")
    fig_et = px.bar(df_exit, x="Month", y="Term Count", color="EXIT TYPE", barmode="group")
    fig_et.update_layout(xaxis_tickformat="%b %Y", title="Turnover by Type", title_x=0.5, template=custom_template)
    st.plotly_chart(fig_et, use_container_width=True)

    # Rates line charts
    st.markdown("### 📉 Turnover KPI's")
    c5, c6 = st.columns(2)
    with c5:
        fig_tr = px.line(df_resumen, x="Month", y="Turnover Rate", markers=True, title="Turnover Rate")
        fig_tr.update_layout(yaxis_tickformat=".0%", xaxis_tickformat="%b %Y", title_x=0.5, template=custom_template)
        st.plotly_chart(fig_tr, use_container_width=True)
    with c6:
        fig_hr = px.line(df_resumen, x="Month", y="Hire Rate", markers=True, title="Hire Rate")
        fig_hr.update_layout(yaxis_tickformat=".0%", xaxis_tickformat="%b %Y", title_x=0.5, template=custom_template)
        st.plotly_chart(fig_hr, use_container_width=True)

    # Breakdown + tables
    st.markdown("### 💼 Breakdown por Segmento")
    gc, cc, ec = st.columns(3)
    with gc:
        fig_g = px.line(df_gender, x="Month", y="Rate", color="GENDER", markers=True, title="By Gender")
        fig_g.update_layout(yaxis_tickformat=".0%", xaxis_tickformat="%b %Y", title_x=0.5, template=custom_template)
        st.plotly_chart(fig_g, use_container_width=True)
        st.dataframe(df_gender.assign(Rate=df_gender["Rate"].map("{:.1%}".format)), use_container_width=True)
    with cc:
        fig_c = px.line(df_cost, x="Month", y="Rate", color="COST CENTER", markers=True, title="By Cost Center")
        fig_c.update_layout(yaxis_tickformat=".0%", xaxis_tickformat="%b %Y", title_x=0.5, template=custom_template)
        st.plotly_chart(fig_c, use_container_width=True)
        st.dataframe(df_cost.assign(Rate=df_cost["Rate"].map("{:.1%}".format)), use_container_width=True)
    with ec:
        fig_e = px.line(df_exit, x="Month", y="Rate", color="EXIT TYPE", markers=True, title="By Exit Type")
        fig_e.update_layout(yaxis_tickformat=".0%", xaxis_tickformat="%b %Y", title_x=0.5, template=custom_template)
        st.plotly_chart(fig_e, use_container_width=True)
        st.dataframe(df_exit.assign(Rate=df_exit["Rate"].map("{:.1%}".format)), use_container_width=True)

    # Headcount history
    st.markdown("### 📋 Headcount Histórico")
    hc_table = df_resumen[["Month", "Headcount End"]].copy()
    hc_table["Month"] = hc_table["Month"].apply(lambda x: x.strftime("%b %Y"))
    st.dataframe(hc_table, use_container_width=True)
    fig_hc = px.bar(hc_table, x="Month", y="Headcount End", text="Headcount End", labels={"Headcount End":"# Empleados"})
    fig_hc.update_layout(xaxis_tickangle=-45, title="Headcount End por Mes", title_x=0.5, template=custom_template)
    st.plotly_chart(fig_hc, use_container_width=True)

    # Download
    def to_excel(df):
        buf = BytesIO()
        df.to_excel(buf, index=False)
        return buf.getvalue()
    st.download_button("📥 Descargar Resumen", data=to_excel(df_resumen), file_name="Resumen_HR.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Footer
    st.markdown("---")
    st.markdown("🔗 Connect with me on [LinkedIn](https://www.linkedin.com/in/diego-gonzalez-farias-248870234/)")

# Ejecutar dashboard
if __name__ == "__main__":
    render_dashboard()
