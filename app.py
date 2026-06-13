# -*- coding: utf-8 -*-
"""
Dashboard Streamlit — Infrações de trânsito em rodovias federais (PRF, jan/2026)
TP2 — DCC011 Introdução a Banco de Dados

Como rodar localmente:
    pip install streamlit pandas
    streamlit run app.py
(o arquivo infracoes-prf.db deve estar na mesma pasta deste script)
"""
import os
import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "infracoes-prf.db")
COD_VELOCIDADE = (74550, 74630, 74710)  # art. 218, I/II/III — infrações de velocidade

st.set_page_config(page_title="Infrações PRF · jan/2026", page_icon="🚗", layout="wide")


# ----------------------------------------------------------------------------- infra
@st.cache_resource
def get_conn():
    # check_same_thread=False porque o Streamlit reexecuta o script em outra thread
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data(show_spinner=False)
def run_query(sql, params=()):
    return pd.read_sql_query(sql, get_conn(), params=params)


def in_clause(values):
    """Gera ('?,?,?', [valores]) para usar em IN (...) com parâmetros."""
    return ", ".join("?" * len(values)), list(values)


# ----------------------------------------------------------------------------- guarda
if not os.path.exists(DB_PATH):
    st.error(
        "Banco `infracoes-prf.db` não encontrado nesta pasta. "
        "Rode o notebook `TP2_Limpeza_e_Normalizacao.ipynb` para gerá-lo "
        "e coloque o arquivo ao lado de `app.py`."
    )
    st.stop()


# ----------------------------------------------------------------------------- sidebar
st.sidebar.title("🚗 Infrações PRF")
st.sidebar.caption("Rodovias federais · janeiro/2026")

so_velocidade = st.sidebar.checkbox(
    "Somente infrações de velocidade (art. 218)", value=True,
    help="Restringe as análises às infrações de excesso de velocidade, "
         "onde a coluna ExcessoVerificado representa km/h acima do limite.",
)

rodovias = run_query(
    """
    SELECT r.NumBR, COUNT(*) AS total
    FROM Infracao i
    JOIN Trecho t  ON t.TrechoID = i.TrechoID
    JOIN Rodovia r ON r.NumBR = t.NumBR
    GROUP BY r.NumBR
    ORDER BY total DESC
    """
)
opcoes_br = rodovias["NumBR"].tolist()
sel_br = st.sidebar.multiselect(
    "Filtrar por rodovia (BR)", opcoes_br,
    default=[], format_func=lambda x: f"BR-{x:03d}",
    help="Vazio = todas as rodovias.",
)
top_n = st.sidebar.slider("Top N nos rankings", 5, 25, 10)

# fragmentos de WHERE reaproveitados
filtros, params = [], []
if so_velocidade:
    ph, vals = in_clause(COD_VELOCIDADE)
    filtros.append(f"i.CodInfracao IN ({ph})")
    params += vals
if sel_br:
    ph, vals = in_clause(sel_br)
    filtros.append(f"t.NumBR IN ({ph})")
    params += vals
where_join = ("WHERE " + " AND ".join(filtros)) if filtros else ""


# ----------------------------------------------------------------------------- header + KPIs
st.title("Análise de infrações em rodovias federais")
st.markdown(
    "Dashboard interativo sobre as autuações da Polícia Rodoviária Federal "
    "(janeiro/2026), a partir do banco normalizado do TP2. Use os filtros na barra lateral."
)

base = run_query(
    f"""
    SELECT COUNT(*) AS total,
           ROUND(AVG(i.ExcessoVerificado), 1) AS excesso_medio,
           MAX(i.ExcessoVerificado) AS excesso_max
    FROM Infracao i
    JOIN Trecho t ON t.TrechoID = i.TrechoID
    {where_join}
    """,
    params,
)
total_geral = int(run_query("SELECT COUNT(*) AS n FROM Infracao")["n"].iloc[0])
n = int(base["total"].iloc[0] or 0)
exc_medio = base["excesso_medio"].iloc[0]
exc_max = base["excesso_max"].iloc[0] or 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Infrações (filtro atual)", f"{n:,}".replace(",", "."))
c2.metric("% do total da base", f"{(100 * n / total_geral):.1f}%")
c3.metric("Excesso médio", f"{exc_medio} km/h" if so_velocidade else f"{exc_medio}")
c4.metric("Maior excesso", f"{exc_max:.0f} km/h" if so_velocidade else f"{exc_max:.0f}")

st.divider()


# ----------------------------------------------------------------------------- abas
aba_rod, aba_tipo, aba_veic, aba_hora, aba_extremo = st.tabs(
    ["🛣️ Rodovias", "📋 Tipos de infração", "🏍️ Veículos", "🕐 Por hora", "⚠️ Casos extremos"]
)

with aba_rod:
    st.subheader("Rodovias com mais infrações")
    df = run_query(
        f"""
        SELECT r.NumBR,
               COUNT(*) AS total_infracoes,
               ROUND(AVG(i.ExcessoVerificado), 1) AS excesso_medio
        FROM Infracao i
        JOIN Trecho t  ON t.TrechoID = i.TrechoID
        JOIN Rodovia r ON r.NumBR = t.NumBR
        {where_join}
        GROUP BY r.NumBR
        ORDER BY total_infracoes DESC
        LIMIT {top_n}
        """,
        params,
    )
    df["Rodovia"] = df["NumBR"].apply(lambda x: f"BR-{x:03d}")
    st.bar_chart(df.set_index("Rodovia")["total_infracoes"])
    st.dataframe(
        df[["Rodovia", "total_infracoes", "excesso_medio"]],
        width='stretch', hide_index=True,
    )

with aba_tipo:
    st.subheader("Tipos de infração mais frequentes")
    df = run_query(
        f"""
        SELECT ti.Descricao,
               COUNT(*) AS total,
               ROUND(AVG(i.ExcessoVerificado), 1) AS excesso_medio
        FROM Infracao i
        JOIN Trecho t        ON t.TrechoID = i.TrechoID
        JOIN Tipo_Infracao ti ON ti.CodInfracao = i.CodInfracao
        {where_join}
        GROUP BY ti.CodInfracao, ti.Descricao
        ORDER BY total DESC
        LIMIT {top_n}
        """,
        params,
    )
    df["rotulo"] = df["Descricao"].str.slice(0, 45) + "…"
    st.bar_chart(df.set_index("rotulo")["total"])
    st.dataframe(df[["Descricao", "total", "excesso_medio"]],
                 width='stretch', hide_index=True)

with aba_veic:
    st.subheader("Marcas de veículo mais autuadas")
    df = run_query(
        f"""
        SELECT mv.Marca, COUNT(*) AS total
        FROM Infracao i
        JOIN Trecho t          ON t.TrechoID = i.TrechoID
        JOIN Modelo_Veiculo mv ON mv.ModeloID = i.ModeloID
        {where_join + (' AND ' if where_join else 'WHERE ')} mv.Marca IS NOT NULL
        GROUP BY mv.Marca
        ORDER BY total DESC
        LIMIT {top_n}
        """,
        params,
    )
    st.bar_chart(df.set_index("Marca")["total"])
    st.dataframe(df, width='stretch', hide_index=True)

with aba_hora:
    st.subheader("Distribuição das infrações por hora do dia")
    df = run_query(
        f"""
        SELECT i.Hora, COUNT(*) AS total
        FROM Infracao i
        JOIN Trecho t ON t.TrechoID = i.TrechoID
        {where_join + (' AND ' if where_join else 'WHERE ')} i.Hora IS NOT NULL
        GROUP BY i.Hora
        ORDER BY i.Hora
        """,
        params,
    )
    st.bar_chart(df.set_index("Hora")["total"])
    st.caption("Pico de autuações ao longo do dia — útil para planejar fiscalização.")

with aba_extremo:
    st.subheader("Veículos a mais que o dobro do limite (excesso > 100%)")
    st.caption("Somente infrações de velocidade (art. 218), independentemente do filtro lateral de velocidade.")
    ph, vals = in_clause(COD_VELOCIDADE)
    extra = ""
    p2 = list(vals)
    if sel_br:
        ph_br, vals_br = in_clause(sel_br)
        extra = f" AND t.NumBR IN ({ph_br})"
        p2 += vals_br
    df = run_query(
        f"""
        SELECT i.NumAuto, i.DataInfracao, i.Hora,
               r.NumBR, i.LimiteVia, i.MedicaoConsiderada, i.ExcessoVerificado,
               ROUND(100.0 * i.ExcessoVerificado / i.LimiteVia, 0) AS pct_acima_limite
        FROM Infracao i
        JOIN Trecho t  ON t.TrechoID = i.TrechoID
        JOIN Rodovia r ON r.NumBR = t.NumBR
        WHERE i.CodInfracao IN ({ph})
          AND i.MedicaoConsiderada > 2 * i.LimiteVia{extra}
        ORDER BY pct_acima_limite DESC, i.MedicaoConsiderada DESC
        LIMIT {top_n}
        """,
        p2,
    )
    df["Rodovia"] = df["NumBR"].apply(lambda x: f"BR-{x:03d}")
    st.dataframe(
        df[["NumAuto", "DataInfracao", "Hora", "Rodovia", "LimiteVia",
            "MedicaoConsiderada", "ExcessoVerificado", "pct_acima_limite"]],
        width='stretch', hide_index=True,
    )

st.divider()
st.caption("TP2 · DCC011 — Introdução a Banco de Dados · dados: PRF (dados.gov.br)")
