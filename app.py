import streamlit as st
import pandas as pd
import requests
from pathlib import Path
from PyPDF2 import PdfMerger
import tempfile

st.set_page_config(page_title="Unificação de Cobranças", layout="wide")

st.title("📑 Unificação de PDFs – Contas a Receber")

st.markdown("""
Este app:
- Lê a planilha de Contas a Receber do ERP  
- Agrupa clientes por **Telefone (holding)**  
- Baixa documentos (Boleto, NFSe, Faturamento e Funcionários)  
- Unifica PDFs  
- Gera **Output_WABA.xlsx** pronto para importação
""")

# -----------------------------------
# FUNÇÕES AUXILIARES
# -----------------------------------
def baixar_pdf(url, destino):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        destino.write_bytes(r.content)
        return True
    except Exception:
        return False

def formatar_valor(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def tratar_data(datas):
    datas_unicas = set(datas)
    if len(datas_unicas) == 1:
        return datas_unicas.pop().strftime("%d/%m/%Y")
    return "datas variadas"

# -----------------------------------
# COLUNAS DE PDF (PLANILHA REAL)
# -----------------------------------
COLUNAS_PDF = [
    "Boleto PDF",
    "Nfse PDF",
    "Faturamento PDF",
    "Funcionários PDF"
]

# -----------------------------------
# UPLOAD
# -----------------------------------
arquivo = st.file_uploader("📤 Envie a planilha (Excel)", type=["xlsx"])

if arquivo:
    df = pd.read_excel(arquivo)
    st.success("Arquivo carregado com sucesso!")

    st.subheader("🔍 Prévia dos Dados")
    st.dataframe(df.head())

    # Validação das colunas obrigatórias
    obrigatorias = [
        "Telefone",
        "Valor Atualizado",
        "Data Vencimento"
    ] + COLUNAS_PDF

    faltantes = [c for c in obrigatorias if c not in df.columns]
    if faltantes:
        st.error(f"Colunas ausentes no arquivo: {faltantes}")
        st.stop()

    if st.button("🚀 Processar Unificação"):
        with st.spinner("Processando dados e documentos..."):

            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_dir = Path(tmpdir)
                saida = []

                # SUPER-AGRUPAMENTO POR TELEFONE
                for telefone, grupo in df.groupby("Telefone"):

                    valor_total = grupo["Valor Atualizado"].sum()
                    datas = pd.to_datetime(grupo["Data Vencimento"])
                    data_saida = tratar_data(datas)

                    pdfs = []

                    for _, row in grupo.iterrows():
                        for col in COLUNAS_PDF:
                            link = row[col]
                            if pd.notna(link):
                                nome_pdf = f"{telefone}_{len(pdfs)}.pdf"
                                caminho = pdf_dir / nome_pdf
                                if baixar_pdf(link, caminho):
                                    pdfs.append(caminho)

                    # Merge PDFs
                    pdf_final = pdf_dir / f"{telefone}_unificado.pdf"
                    if pdfs:
                        merger = PdfMerger()
                        for p in pdfs:
                            merger.append(str(p))
                        merger.write(str(pdf_final))
                        merger.close()

                    saida.append({
                        "telefone": telefone,
                        "{{1}}": formatar_valor(valor_total),
                        "{{3}}": data_saida,
                        "arquivo_pdf": str(pdf_final) if pdfs else ""
                    })

                df_saida = pd.DataFrame(saida)

                output_excel = pdf_dir / "Output_WABA.xlsx"
                df_saida.to_excel(output_excel, index=False)

                st.success("✅ Processamento concluído!")

                # DOWNLOAD
                with open(output_excel, "rb") as f:
                    st.download_button(
                        "📥 Baixar Output_WABA.xlsx",
                        f,
                        file_name="Output_WABA.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                st.subheader("📄 Prévia do Output")
                st.dataframe(df_saida)
