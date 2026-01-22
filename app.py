import streamlit as st
import pandas as pd
import requests
from pathlib import Path
from PyPDF2 import PdfMerger
from datetime import datetime
import tempfile
import os

st.set_page_config(page_title="Unificação de Cobranças", layout="wide")

st.title("📑 Unificação de PDFs e Geração WABA")

st.markdown("""
Este aplicativo:
- Lê planilhas exportadas do ERP  
- Agrupa cobranças por **telefone (holding)**  
- Soma valores  
- Trata datas de vencimento  
- Baixa e unifica PDFs  
- Gera **Output_WABA.xlsx**
""")

# -----------------------------
# FUNÇÕES AUXILIARES
# -----------------------------
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

# -----------------------------
# UPLOAD DO ARQUIVO
# -----------------------------
arquivo = st.file_uploader("📤 Envie o arquivo do ERP (Excel)", type=["xlsx"])

if arquivo:
    df = pd.read_excel(arquivo)
    st.success("Arquivo carregado com sucesso!")

    st.subheader("📊 Prévia dos Dados")
    st.dataframe(df.head())

    link_cols = [c for c in df.columns if c.startswith("Link_")]

    if not link_cols:
        st.error("Nenhuma coluna 'Link_' encontrada.")
        st.stop()

    if st.button("🚀 Processar Cobranças"):
        with st.spinner("Processando dados e PDFs..."):

            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_dir = Path(tmpdir)

                saida = []

                for telefone, grupo_tel in df.groupby("Telefone"):

                    valor_total = grupo_tel["Valor_Atualizado"].sum()
                    datas = pd.to_datetime(grupo_tel["Data_Vencimento"])
                    data_saida = tratar_data(datas)

                    pdfs_cliente = []

                    for _, row in grupo_tel.iterrows():
                        for col in link_cols:
                            link = row[col]
                            if pd.notna(link):
                                nome_pdf = f"{telefone}_{len(pdfs_cliente)}.pdf"
                                caminho_pdf = pdf_dir / nome_pdf
                                if baixar_pdf(link, caminho_pdf):
                                    pdfs_cliente.append(caminho_pdf)

                    # Merge dos PDFs
                    pdf_final = pdf_dir / f"{telefone}_unificado.pdf"
                    if pdfs_cliente:
                        merger = PdfMerger()
                        for pdf in pdfs_cliente:
                            merger.append(str(pdf))
                        merger.write(str(pdf_final))
                        merger.close()

                    saida.append({
                        "telefone": telefone,
                        "{{1}}": formatar_valor(valor_total),
                        "{{3}}": data_saida,
                        "arquivo_pdf": str(pdf_final) if pdfs_cliente else ""
                    })

                df_saida = pd.DataFrame(saida)

                output_excel = pdf_dir / "Output_WABA.xlsx"
                df_saida.to_excel(output_excel, index=False)

                st.success("✅ Processamento concluído!")

                # DOWNLOAD DO EXCEL
                with open(output_excel, "rb") as f:
                    st.download_button(
                        label="📥 Baixar Output_WABA.xlsx",
                        data=f,
                        file_name="Output_WABA.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                st.subheader("📄 Prévia do Output")
                st.dataframe(df_saida)
