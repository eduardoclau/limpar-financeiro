import streamlit as st
import pandas as pd
import requests
from pathlib import Path
from PyPDF2 import PdfMerger
import tempfile

# -------------------------------------------------
# CONFIGURAÇÃO STREAMLIT
# -------------------------------------------------
st.set_page_config(
    page_title="Centralização de Documentos – Contas a Receber",
    layout="wide"
)

st.title("📑 Centralização e Unificação de Documentos")

st.markdown("""
Este aplicativo:
- Lê a planilha de Contas a Receber do ERP  
- Centraliza todos os documentos por **cliente lógico**  
- Baixa PDFs (Boleto, NFSe, Faturamento e Funcionários)  
- Unifica tudo em **um único PDF por cliente**  
- Gera **Output_WABA.xlsx** pronto para uso
""")

# -------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------
def baixar_pdf(url, destino):
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        destino.write_bytes(r.content)
        return True
    except Exception:
        return False

def chave_centralizacao(row):
    """
    Define a chave lógica de centralização.
    Ordem de prioridade:
    1. Telefone
    2. ID_Cliente
    3. CNPJ
    4. Índice da linha
    """
    if "Telefone" in row and pd.notna(row["Telefone"]):
        return f"TEL_{str(row['Telefone']).strip()}"
    if "ID_Cliente" in row and pd.notna(row["ID_Cliente"]):
        return f"ID_{str(row['ID_Cliente']).strip()}"
    if "CNPJ" in row and pd.notna(row["CNPJ"]):
        return f"CNPJ_{str(row['CNPJ']).strip()}"
    return f"LINHA_{row.name}"

# -------------------------------------------------
# COLUNAS DE DOCUMENTOS (PLANILHA REAL)
# -------------------------------------------------
COLUNAS_PDF = [
    "Boleto PDF",
    "Nfse PDF",
    "Faturamento PDF",
    "Funcionários PDF"
]

# -------------------------------------------------
# UPLOAD DO ARQUIVO
# -------------------------------------------------
arquivo = st.file_uploader(
    "📤 Envie a planilha do ERP (Excel)",
    type=["xlsx"]
)

if arquivo:
    df = pd.read_excel(arquivo)
    st.success("Arquivo carregado com sucesso!")

    st.subheader("🔍 Prévia da Planilha")
    st.dataframe(df.head())

    # Validação mínima: ao menos uma coluna de PDF deve existir
    colunas_presentes = [c for c in COLUNAS_PDF if c in df.columns]
    if not colunas_presentes:
        st.error(
            "Nenhuma coluna de documentos encontrada. "
            "Esperado ao menos uma das colunas:\n"
            f"{COLUNAS_PDF}"
        )
        st.stop()

    # -------------------------------------------------
    # BOTÃO DE PROCESSAMENTO
    # -------------------------------------------------
    if st.button("🚀 Centralizar e Unificar Documentos"):
        with st.spinner("Processando documentos..."):

            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_dir = Path(tmpdir)
                resultados = []

                # Criação da chave de centralização
                df["CHAVE_CENTRAL"] = df.apply(chave_centralizacao, axis=1)

                # Agrupamento centralizado
                for chave, grupo in df.groupby("CHAVE_CENTRAL"):

                    pdfs_cliente = []

                    for _, row in grupo.iterrows():
                        for col in colunas_presentes:
                            link = row[col]
                            if pd.notna(link):
                                nome_pdf = f"{chave}_{len(pdfs_cliente)}.pdf"
                                caminho = pdf_dir / nome_pdf
                                if baixar_pdf(link, caminho):
                                    pdfs_cliente.append(caminho)

                    # Merge dos PDFs
                    pdf_final = pdf_dir / f"{chave}_UNIFICADO.pdf"

                    if pdfs_cliente:
                        merger = PdfMerger()
                        for pdf in pdfs_cliente:
                            merger.append(str(pdf))
                        merger.write(str(pdf_final))
                        merger.close()

                    resultados.append({
                        "chave_cliente": chave,
                        "qtd_documentos": len(pdfs_cliente),
                        "arquivo_pdf": str(pdf_final) if pdfs_cliente else ""
                    })

                # -------------------------------------------------
                # OUTPUT FINAL
                # -------------------------------------------------
                df_saida = pd.DataFrame(resultados)

                output_excel = pdf_dir / "Output_WABA.xlsx"
                df_saida.to_excel(output_excel, index=False)

                st.success("✅ Centralização concluída com sucesso!")

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
