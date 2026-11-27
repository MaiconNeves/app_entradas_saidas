import io
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd
import streamlit as st

# Configuração da página
st.set_page_config(page_title="MVP Varejo - Kardex Consolidado", page_icon="📊", layout="wide")


def _strip_ns(tag: str) -> str:
    """Remove o namespace XML da tag."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def processar_arquivos_enviados(arquivos_entrada, arquivos_saida):
    dados_relatorio = []

    lotes = [
        ("Entrada", arquivos_entrada),
        ("Saida", arquivos_saida)
    ]

    for tipo_movimento, lista_arquivos in lotes:
        if not lista_arquivos:
            continue

        for arquivo in lista_arquivos:
            try:
                # Lê diretamente o arquivo enviado na memória (BytesIO)
                tree = ET.parse(arquivo)
                root = tree.getroot()

                for elem in root.iter():
                    elem.tag = _strip_ns(elem.tag)

                inf_nfe = root.find('.//infNFe')
                if inf_nfe is None:
                    continue

                dh_emi = inf_nfe.findtext('.//ide/dhEmi', default="")
                data_iso = dh_emi[:10] if dh_emi else ""
                if not data_iso:
                    continue

                fornecedor = inf_nfe.findtext('.//emit/xNome', default="Não Informado")

                for det in inf_nfe.findall('.//det'):
                    prod = det.find('prod')
                    if prod is not None:
                        cod_prod = prod.findtext('cProd', default="")
                        nome_prod = prod.findtext('xProd', default="")
                        qtd = float(prod.findtext('qCom', default="0"))

                        dados_relatorio.append({
                            "Data_Obj": datetime.strptime(data_iso, "%Y-%m-%d").date(),
                            "Tipo": tipo_movimento,
                            "Fornecedor": fornecedor,
                            "SKU": cod_prod,
                            "Produto": nome_prod,
                            "SKU_Label": f"{cod_prod} - {nome_prod}",
                            "Quantidade": qtd
                        })

            except Exception as e:
                st.error(f"Erro ao processar {arquivo.name}: {e}")

    return pd.DataFrame(dados_relatorio)


# --- INTERFACE STREAMLIT ---
st.title("📊 MVP Varejo — Kardex Consolidado (Entradas x Saídas)")

# --- UPLOAD DE ARQUIVOS NA BARRA LATERAL ---
st.sidebar.header("📂 1. Importar XMLs")
xmls_entrada = st.sidebar.file_uploader(
    "XMLs de Entrada (Compras):",
    type=["xml"],
    accept_multiple_files=True
)
xmls_saida = st.sidebar.file_uploader(
    "XMLs de Saída (Vendas):",
    type=["xml"],
    accept_multiple_files=True
)

if not xmls_entrada and not xmls_saida:
    st.info("👈 Selecione os arquivos XML de **Entrada** e/ou **Saída** na barra lateral para gerar o relatório.")
    st.stop()

df_total = processar_arquivos_enviados(xmls_entrada, xmls_saida)

if df_total.empty:
    st.warning("Nenhum item válido de NF-e/NFC-e foi encontrado nos arquivos enviados.")
    st.stop()

# --- FILTROS DE PESQUISA ---
st.sidebar.divider()
st.sidebar.header("🔍 2. Filtros de Pesquisa")

data_min = df_total["Data_Obj"].min()
data_max = df_total["Data_Obj"].max()

col_d1, col_d2 = st.sidebar.columns(2)
data_de = col_d1.date_input("De:", value=data_min, min_value=data_min, max_value=data_max, format="DD/MM/YYYY")
data_ate = col_d2.date_input("Até:", value=data_max, min_value=data_min, max_value=data_max, format="DD/MM/YYYY")

lista_produtos = ["Todos"] + sorted(df_total["SKU_Label"].unique().tolist())
produto_selecionado = st.sidebar.selectbox("Produto / SKU:", lista_produtos)

lista_fornecedores = ["Todos"] + sorted(df_total["Fornecedor"].unique().tolist())
fornecedor_selecionado = st.sidebar.selectbox("Fornecedor / Emitente:", lista_fornecedores)

# --- APLICAÇÃO DOS FILTROS ---
df_filtrado = df_total[
    (df_total["Data_Obj"] >= data_de) &
    (df_total["Data_Obj"] <= data_ate)
].copy()

if produto_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["SKU_Label"] == produto_selecionado]

if fornecedor_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Fornecedor"] == fornecedor_selecionado]

if df_filtrado.empty:
    st.warning("Nenhuma movimentação encontrada para os filtros selecionados.")
    st.stop()

# ==============================================================================
# 1. CONSOLIDAÇÃO POR DIA E SKU
# ==============================================================================
df_consolidado_dia = df_filtrado.pivot_table(
    index=["Data_Obj", "SKU", "Produto"],
    columns="Tipo",
    values="Quantidade",
    aggfunc="sum",
    fill_value=0
).reset_index()

if "Entrada" not in df_consolidado_dia.columns:
    df_consolidado_dia["Entrada"] = 0.0
if "Saida" not in df_consolidado_dia.columns:
    df_consolidado_dia["Saida"] = 0.0

df_consolidado_dia = df_consolidado_dia.sort_values(by=["Data_Obj", "SKU"])
df_consolidado_dia["Dia"] = pd.to_datetime(df_consolidado_dia["Data_Obj"]).dt.strftime("%d/%m/%Y")
df_consolidado_dia = df_consolidado_dia.rename(columns={
    "Entrada": "QTDE_ENTRADA",
    "Saida": "QTDE_SAIDA"
})

colunas_dia = ["Dia", "SKU", "Produto", "QTDE_ENTRADA", "QTDE_SAIDA"]
df_exibicao_dia = df_consolidado_dia[colunas_dia]

# ==============================================================================
# 2. CONSOLIDAÇÃO POR SKU (TODAS AS ENTRADAS E SAÍDAS NO PERÍODO)
# ==============================================================================
df_consolidado_sku = df_filtrado.pivot_table(
    index=["SKU", "Produto"],
    columns="Tipo",
    values="Quantidade",
    aggfunc="sum",
    fill_value=0
).reset_index()

if "Entrada" not in df_consolidado_sku.columns:
    df_consolidado_sku["Entrada"] = 0.0
if "Saida" not in df_consolidado_sku.columns:
    df_consolidado_sku["Saida"] = 0.0

df_consolidado_sku["SALDO_PERIODO"] = df_consolidado_sku["Entrada"] - df_consolidado_sku["Saida"]
df_consolidado_sku = df_consolidado_sku.sort_values(by=["SKU"])

df_consolidado_sku = df_consolidado_sku.rename(columns={
    "Entrada": "TOTAL_ENTRADA",
    "Saida": "TOTAL_SAIDA"
})

colunas_sku = ["SKU", "Produto", "TOTAL_ENTRADA", "TOTAL_SAIDA", "SALDO_PERIODO"]
df_exibicao_sku = df_consolidado_sku[colunas_sku]

# --- MÉTRICAS NO TOPO ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("SKUs Únicos", len(df_exibicao_sku))
m2.metric("Total Entradas", f"{df_exibicao_sku['TOTAL_ENTRADA'].sum():,.2f}")
m3.metric("Total Saídas", f"{df_exibicao_sku['TOTAL_SAIDA'].sum():,.2f}")
m4.metric("Saldo Líquido", f"{df_exibicao_sku['SALDO_PERIODO'].sum():,.2f}")

st.divider()

# --- ABAS NA INTERFACE ---
aba_sku, aba_dia = st.tabs(["📦 Consolidado por SKU", "📅 Consolidado Diário (Dia x SKU)"])

with aba_sku:
    st.subheader("Resumo Total por SKU no Período Filtrado")
    st.dataframe(df_exibicao_sku, use_container_width=True, hide_index=True)

with aba_dia:
    st.subheader("Movimentação Detalhada por Dia e SKU")
    st.dataframe(df_exibicao_dia, use_container_width=True, hide_index=True)

# --- DOWNLOAD EXCEL (COM AS DUAS ABAS) ---
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    df_exibicao_sku.to_excel(writer, index=False, sheet_name="Consolidado_SKU")
    df_exibicao_dia.to_excel(writer, index=False, sheet_name="Consolidado_Diario")

st.download_button(
    label="📥 Baixar Relatório Completo (Excel com 2 Abas)",
    data=buffer.getvalue(),
    file_name=f"Kardex_Consolidado_{data_de.strftime('%d%m')}_a_{data_ate.strftime('%d%m')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
