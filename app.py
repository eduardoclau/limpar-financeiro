import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
import PyPDF2
import tempfile
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import zipfile
import base64

# Configuração da página
st.set_page_config(
    page_title="Sistema de Cobrança - Unificação de Contas",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #2563EB;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #3B82F6;
        margin-bottom: 1rem;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
    .stButton button {
        width: 100%;
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
    }
    .stButton button:hover {
        background-color: #2563EB;
    }
    .stDownloadButton button {
        background-color: #10B981;
        color: white;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Título do aplicativo
st.markdown('<h1 class="main-header">💰 Sistema de Cobrança - Unificação de Contas</h1>', unsafe_allow_html=True)

# Barra lateral para configurações
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
    st.markdown("### ⚙️ Configurações")
    
    st.markdown("#### Opções de Processamento")
    baixar_pdfs = st.checkbox("📥 Baixar e unificar PDFs", value=True)
    agrupar_holdings = st.checkbox("🏢 Agrupar Holdings (mesmo telefone)", value=True)
    
    st.markdown("#### Filtros")
    valor_minimo = st.number_input("Valor mínimo (R$)", min_value=0, value=0)
    
    st.markdown("---")
    st.markdown("### 📊 Estatísticas")
    
    if 'resultados' in st.session_state:
        stats = st.session_state.resultados_stats
        st.metric("Total Clientes", stats['total_clientes'])
        st.metric("Valor Total", f"R$ {stats['valor_total']:,.2f}")
        st.metric("Média por Cliente", f"R$ {stats['media_cliente']:,.2f}")
    
    st.markdown("---")
    st.markdown("#### ℹ️ Instruções")
    st.info("""
    1. Faça upload do arquivo Excel
    2. Configure as opções desejadas
    3. Clique em 'Processar Dados'
    4. Faça download dos resultados
    """)

# Funções principais
def baixar_pdf_streamlit(url):
    """Baixa um PDF a partir de uma URL"""
    if pd.isna(url) or url == '' or not isinstance(url, str):
        return None
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return BytesIO(response.content)
    except Exception as e:
        st.warning(f"Erro ao baixar PDF: {e}")
    return None

def unificar_pdfs_streamlit(lista_pdfs_bytes, output_path):
    """Unifica múltiplos PDFs em um único arquivo"""
    if not lista_pdfs_bytes:
        return False
    
    merger = PyPDF2.PdfMerger()
    pdfs_adicionados = 0
    
    for pdf_bytes in lista_pdfs_bytes:
        try:
            merger.append(pdf_bytes)
            pdfs_adicionados += 1
        except Exception as e:
            st.warning(f"Erro ao processar PDF: {e}")
            continue
    
    if pdfs_adicionados > 0:
        with open(output_path, 'wb') as output_file:
            merger.write(output_file)
        return True
    return False

def processar_dados(df, baixar_pdfs_option=True, agrupar_holdings_option=True):
    """Processa os dados conforme configurações"""
    
    # Barra de progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Etapa 1: Preparação dos dados
    status_text.text("📋 Preparando dados...")
    progress_bar.progress(10)
    
    # Renomear colunas
    colunas_renomear = {
        'ID Emp.': 'ID_Cliente',
        'Razão Social': 'Razao_Social',
        'CPF/CNPJ': 'CNPJ',
        'Vencimento': 'Data_Vencimento',
        'Valor': 'Valor_Bruto',
        'Valor Líquido': 'Valor_Liquido',
        'Boleto PDF': 'Link_Boleto',
        'Nfse PDF': 'Link_NFSe',
        'Faturamento PDF': 'Link_Faturamento',
        'Funcionários PDF': 'Link_Funcionarios',
        'Nosso Núm.': 'Telefone_Contato'
    }
    
    df = df.rename(columns=colunas_renomear)
    
    # Converter datas e valores
    df['Data_Vencimento'] = pd.to_datetime(df['Data_Vencimento'], errors='coerce')
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    
    df['Valor_Liquido'] = df['Valor_Liquido'].fillna(df['Valor_Bruto'])
    df['Valor_Atualizado'] = pd.to_numeric(
        df['Valor_Liquido'].replace('R\$ ', '', regex=True).replace('.', '', regex=True).replace(',', '.', regex=True),
        errors='coerce'
    )
    
    # Etapa 2: Agrupamento por telefone (holdings)
    if agrupar_holdings_option:
        status_text.text("🏢 Agrupando holdings...")
        progress_bar.progress(30)
        
        # Agrupar por CNPJ
        df_agrupado_cnpj = df.groupby('CNPJ').agg({
            'Telefone_Contato': 'first',
            'Razao_Social': 'first',
            'ID_Cliente': lambda x: list(set(x))
        }).reset_index()
        
        # Identificar holdings pelo telefone
        telefone_para_cnpjs = {}
        for _, row in df_agrupado_cnpj.iterrows():
            telefone = row['Telefone_Contato']
            if pd.isna(telefone):
                continue
            telefone = str(telefone)
            if telefone not in telefone_para_cnpjs:
                telefone_para_cnpjs[telefone] = []
            telefone_para_cnpjs[telefone].append(row['CNPJ'])
        
        # Mapear CNPJ para telefone principal
        cnpj_para_telefone_principal = {}
        for telefone, cnpjs in telefone_para_cnpjs.items():
            if len(cnpjs) > 1:  # É uma holding
                for cnpj in cnpjs:
                    cnpj_para_telefone_principal[cnpj] = telefone
        
        df['Telefone_Agrupado'] = df['CNPJ'].map(cnpj_para_telefone_principal).fillna(df['Telefone_Contato'])
        grupo_cols = ['Telefone_Agrupado', 'CNPJ']
    else:
        df['Telefone_Agrupado'] = df['Telefone_Contato']
        grupo_cols = ['ID_Cliente', 'CNPJ']
    
    # Etapa 3: Processamento por grupo
    status_text.text("📊 Processando grupos...")
    progress_bar.progress(50)
    
    resultados = []
    pdfs_para_download = {}
    grupos_processados = set()
    
    total_grupos = len(df.groupby(grupo_cols))
    grupos_processados_count = 0
    
    for (telefone, cnpj), grupo in df.groupby(grupo_cols):
        grupo_id = f"{telefone}_{cnpj}"
        if grupo_id in grupos_processados:
            continue
        
        grupos_processados.add(grupo_id)
        grupos_processados_count += 1
        
        # Atualizar progresso
        progresso = 50 + (grupos_processados_count / total_grupos * 40)
        progress_bar.progress(int(progresso))
        status_text.text(f"📄 Processando grupo {grupos_processados_count} de {total_grupos}...")
        
        # Dados do grupo
        razao_social = grupo['Razao_Social'].iloc[0]
        id_cliente = grupo['ID_Cliente'].iloc[0] if not agrupar_holdings_option else str(grupo['ID_Cliente'].iloc[0])
        
        # Lógica da data
        datas_vencimento = grupo['Data_Vencimento'].dropna().dt.strftime('%d/%m/%Y').unique()
        if len(datas_vencimento) == 1:
            data_vencimento = datas_vencimento[0]
        else:
            data_vencimento = "datas variadas"
        
        # Lógica do valor
        valor_total = grupo['Valor_Atualizado'].sum()
        
        # Processar PDFs se habilitado
        caminho_pdf = None
        if baixar_pdfs_option:
            todos_pdfs_bytes = []
            colunas_pdf = ['Link_Boleto', 'Link_NFSe', 'Link_Faturamento', 'Link_Funcionarios']
            
            for _, linha in grupo.iterrows():
                for coluna in colunas_pdf:
                    pdf_bytes = baixar_pdf_streamlit(linha[coluna])
                    if pdf_bytes:
                        todos_pdfs_bytes.append(pdf_bytes)
            
            if todos_pdfs_bytes:
                # Criar diretório temporário para PDFs
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', 
                                                prefix=f"{id_cliente}_") as tmp_file:
                    tmp_path = tmp_file.name
                
                if unificar_pdfs_streamlit(todos_pdfs_bytes, tmp_path):
                    caminho_pdf = tmp_path
                    pdfs_para_download[grupo_id] = {
                        'caminho': tmp_path,
                        'nome': f"{id_cliente}_{razao_social[:30]}.pdf".replace('/', '_')
                    }
        
        # Adicionar ao resultado
        resultados.append({
            'ID_Cliente': id_cliente,
            'Razao_Social': razao_social,
            'CNPJ': cnpj,
            'Telefone_Contato': telefone,
            'Data_Vencimento': data_vencimento,
            'Valor_Total': round(valor_total, 2),
            'Quantidade_Contas': len(grupo),
            'PDF_Disponivel': 'Sim' if caminho_pdf else 'Não',
            'Grupo_ID': grupo_id
        })
    
    # Etapa 4: Finalizar
    status_text.text("✅ Processamento concluído!")
    progress_bar.progress(100)
    
    # Criar DataFrame de resultados
    df_resultado = pd.DataFrame(resultados)
    
    # Ordenar por valor total
    df_resultado = df_resultado.sort_values('Valor_Total', ascending=False)
    
    # Formatar valor para exibição
    df_resultado['Valor_Total_Formatado'] = df_resultado['Valor_Total'].apply(
        lambda x: f'R$ {x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    )
    
    # Calcular estatísticas
    stats = {
        'total_clientes': len(df_resultado),
        'valor_total': df_resultado['Valor_Total'].sum(),
        'media_cliente': df_resultado['Valor_Total'].mean(),
        'clientes_com_pdf': df_resultado['PDF_Disponivel'].eq('Sim').sum()
    }
    
    return df_resultado, pdfs_para_download, stats

# Funções para download
def criar_arquivo_zip(pdfs_dict, nome_arquivo="PDFs_Unificados.zip"):
    """Cria um arquivo ZIP com todos os PDFs"""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for grupo_id, info in pdfs_dict.items():
            if os.path.exists(info['caminho']):
                zip_file.write(info['caminho'], info['nome'])
                # Remover arquivo temporário
                os.remove(info['caminho'])
    
    zip_buffer.seek(0)
    return zip_buffer

def get_download_link(data, filename, text):
    """Gera link de download para arquivos"""
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{text}</a>'
    return href

# Interface principal
tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "📊 Visualização", "📈 Dashboard", "📥 Download"])

with tab1:
    st.markdown('<h2 class="sub-header">📤 Upload do Arquivo</h2>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Selecione o arquivo Excel de contas a receber",
        type=['xlsx', 'xls'],
        help="Arquivo deve conter as colunas: ID Emp., Razão Social, CPF/CNPJ, Vencimento, Valor, etc."
    )
    
    if uploaded_file is not None:
        try:
            # Ler o arquivo
            df_original = pd.read_excel(uploaded_file, header=1)
            st.session_state.df_original = df_original
            
            # Mostrar prévia
            st.success(f"✅ Arquivo carregado com sucesso! ({len(df_original)} registros)")
            
            with st.expander("👁️ Visualizar amostra dos dados"):
                st.dataframe(df_original.head(10))
            
            # Botão para processar
            if st.button("🚀 Processar Dados", type="primary"):
                with st.spinner("Processando dados..."):
                    resultados, pdfs, stats = processar_dados(
                        df_original.copy(),
                        baixar_pdfs_option=baixar_pdfs,
                        agrupar_holdings_option=agrupar_holdings
                    )
                    
                    # Salvar resultados na sessão
                    st.session_state.resultados = resultados
                    st.session_state.pdfs_para_download = pdfs
                    st.session_state.resultados_stats = stats
                    
                    st.success("✅ Dados processados com sucesso!")
                    
                    # Atualizar sidebar automaticamente
                    st.rerun()
                    
        except Exception as e:
            st.error(f"❌ Erro ao processar arquivo: {str(e)}")
            st.info("Verifique se o arquivo está no formato correto.")

with tab2:
    st.markdown('<h2 class="sub-header">📊 Visualização dos Resultados</h2>', unsafe_allow_html=True)
    
    if 'resultados' in st.session_state:
        df_resultados = st.session_state.resultados
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_pdf = st.selectbox(
                "Filtrar por PDF disponível",
                ["Todos", "Com PDF", "Sem PDF"]
            )
        with col2:
            filtro_valor = st.selectbox(
                "Ordenar por valor",
                ["Maior valor", "Menor valor"]
            )
        with col3:
            mostrar_colunas = st.multiselect(
                "Colunas para exibir",
                df_resultados.columns.tolist(),
                default=['Razao_Social', 'CNPJ', 'Telefone_Contato', 'Data_Vencimento', 'Valor_Total_Formatado', 'PDF_Disponivel']
            )
        
        # Aplicar filtros
        df_filtrado = df_resultados.copy()
        
        if filtro_pdf == "Com PDF":
            df_filtrado = df_filtrado[df_filtrado['PDF_Disponivel'] == 'Sim']
        elif filtro_pdf == "Sem PDF":
            df_filtrado = df_filtrado[df_filtrado['PDF_Disponivel'] == 'Não']
        
        if filtro_valor == "Menor valor":
            df_filtrado = df_filtrado.sort_values('Valor_Total')
        else:
            df_filtrado = df_filtrado.sort_values('Valor_Total', ascending=False)
        
        # Aplicar valor mínimo
        df_filtrado = df_filtrado[df_filtrado['Valor_Total'] >= valor_minimo]
        
        # Exibir resultados
        st.dataframe(
            df_filtrado[mostrar_colunas] if mostrar_colunas else df_filtrado,
            use_container_width=True,
            height=400
        )
        
        # Métricas rápidas
        st.markdown("### 📈 Resumo")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Clientes", len(df_filtrado))
        with col2:
            st.metric("Valor Total", f"R$ {df_filtrado['Valor_Total'].sum():,.2f}")
        with col3:
            st.metric("Média por Cliente", f"R$ {df_filtrado['Valor_Total'].mean():,.2f}")
        with col4:
            st.metric("Com PDF", f"{df_filtrado['PDF_Disponivel'].eq('Sim').sum()}")
        
        # Visualização detalhada
        with st.expander("🔍 Detalhes por cliente"):
            cliente_selecionado = st.selectbox(
                "Selecione um cliente para detalhes",
                df_resultados['Razao_Social'].tolist()
            )
            
            if cliente_selecionado:
                cliente_info = df_resultados[df_resultados['Razao_Social'] == cliente_selecionado].iloc[0]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Informações do Cliente:**")
                    st.write(f"**ID:** {cliente_info['ID_Cliente']}")
                    st.write(f"**CNPJ/CPF:** {cliente_info['CNPJ']}")
                    st.write(f"**Telefone:** {cliente_info['Telefone_Contato']}")
                    st.write(f"**Vencimento:** {cliente_info['Data_Vencimento']}")
                
                with col2:
                    st.write("**Informações Financeiras:**")
                    st.write(f"**Valor Total:** R$ {cliente_info['Valor_Total']:,.2f}")
                    st.write(f"**Quantidade de Contas:** {cliente_info['Quantidade_Contas']}")
                    st.write(f"**PDF Disponível:** {cliente_info['PDF_Disponivel']}")
                    
                    # Variáveis para disparo
                    st.markdown("---")
                    st.markdown("**📱 Variáveis para WhatsApp:**")
                    st.code(f"{{1}} = {cliente_info['Razao_Social']}")
                    st.code(f"{{2}} = R$ {cliente_info['Valor_Total']:,.2f}")
                    st.code(f"{{3}} = {cliente_info['Data_Vencimento']}")
    else:
        st.info("👆 Faça upload e processe os dados na aba 'Upload' para ver os resultados.")

with tab3:
    st.markdown('<h2 class="sub-header">📈 Dashboard Analítico</h2>', unsafe_allow_html=True)
    
    if 'resultados' in st.session_state:
        df_resultados = st.session_state.resultados
        
        # Gráfico 1: Top 10 clientes por valor
        fig1 = px.bar(
            df_resultados.head(10),
            x='Razao_Social',
            y='Valor_Total',
            title='🔝 Top 10 Clientes por Valor',
            labels={'Razao_Social': 'Cliente', 'Valor_Total': 'Valor (R$)'},
            color='Valor_Total',
            color_continuous_scale='Blues'
        )
        fig1.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig1, use_container_width=True)
        
        # Gráfico 2: Distribuição de valores
        col1, col2 = st.columns(2)
        
        with col1:
            fig2 = px.pie(
                df_resultados,
                names='PDF_Disponivel',
                title='📄 Distribuição de PDFs Disponíveis',
                color='PDF_Disponivel',
                color_discrete_map={'Sim': '#10B981', 'Não': '#EF4444'}
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        with col2:
            fig3 = px.histogram(
                df_resultados,
                x='Valor_Total',
                title='📊 Distribuição de Valores',
                nbins=20,
                labels={'Valor_Total': 'Valor (R$)'}
            )
            fig3.update_layout(bargap=0.1)
            st.plotly_chart(fig3, use_container_width=True)
        
        # Gráfico 3: Linha do tempo (se houver datas específicas)
        df_datas = df_resultados[df_resultados['Data_Vencimento'] != 'datas variadas'].copy()
        if not df_datas.empty:
            df_datas['Data_Vencimento'] = pd.to_datetime(df_datas['Data_Vencimento'], format='%d/%m/%Y')
            df_datas = df_datas.sort_values('Data_Vencimento')
            
            fig4 = px.scatter(
                df_datas,
                x='Data_Vencimento',
                y='Valor_Total',
                size='Valor_Total',
                color='Razao_Social',
                title='📅 Distribuição por Data de Vencimento',
                labels={'Data_Vencimento': 'Data de Vencimento', 'Valor_Total': 'Valor (R$)'}
            )
            st.plotly_chart(fig4, use_container_width=True)
        
        # Tabela de estatísticas avançadas
        with st.expander("📋 Estatísticas Detalhadas"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Valor Máximo", f"R$ {df_resultados['Valor_Total'].max():,.2f}")
                st.metric("Valor Mínimo", f"R$ {df_resultados['Valor_Total'].min():,.2f}")
            
            with col2:
                st.metric("Mediana", f"R$ {df_resultados['Valor_Total'].median():,.2f}")
                st.metric("Desvio Padrão", f"R$ {df_resultados['Valor_Total'].std():,.2f}")
            
            with col3:
                st.metric("Q1 (25%)", f"R$ {df_resultados['Valor_Total'].quantile(0.25):,.2f}")
                st.metric("Q3 (75%)", f"R$ {df_resultados['Valor_Total'].quantile(0.75):,.2f}")
    else:
        st.info("👆 Processe os dados para visualizar o dashboard.")

with tab4:
    st.markdown('<h2 class="sub-header">📥 Download dos Resultados</h2>', unsafe_allow_html=True)
    
    if 'resultados' in st.session_state:
        df_resultados = st.session_state.resultados
        
        # Seção 1: Download da planilha
        st.markdown("### 📋 Planilha de Resultados")
        
        # Criar Excel em memória
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            # Planilha principal
            df_export = df_resultados.copy()
            df_export['Valor_Total'] = df_export['Valor_Total'].apply(
                lambda x: f'R$ {x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
            )
            
            df_export[[
                'ID_Cliente',
                'Razao_Social',
                'CNPJ',
                'Telefone_Contato',
                'Data_Vencimento',
                'Valor_Total',
                'Quantidade_Contas',
                'PDF_Disponivel'
            ]].to_excel(writer, sheet_name='Clientes_Unificados', index=False)
            
            # Planilha de estatísticas
            stats_df = pd.DataFrame({
                'Métrica': ['Total de Clientes', 'Valor Total', 'Média por Cliente', 'Clientes com PDF'],
                'Valor': [
                    len(df_resultados),
                    f"R$ {df_resultados['Valor_Total'].sum():,.2f}",
                    f"R$ {df_resultados['Valor_Total'].mean():,.2f}",
                    df_resultados['PDF_Disponivel'].eq('Sim').sum()
                ]
            })
            stats_df.to_excel(writer, sheet_name='Estatisticas', index=False)
        
        excel_buffer.seek(0)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Baixar Planilha Excel",
                data=excel_buffer,
                file_name="Clientes_Unificados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Seção 2: Download de PDFs
        st.markdown("### 📄 PDFs Unificados")
        
        if 'pdfs_para_download' in st.session_state and st.session_state.pdfs_para_download:
            pdfs_dict = st.session_state.pdfs_para_download
            
            with col2:
                # Criar ZIP com todos os PDFs
                zip_buffer = criar_arquivo_zip(pdfs_dict)
                
                st.download_button(
                    label="📦 Baixar Todos os PDFs (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="PDFs_Unificados.zip",
                    mime="application/zip"
                )
            
            # Lista individual de PDFs
            st.markdown("#### 📋 PDFs Disponíveis")
            for grupo_id, info in pdfs_dict.items():
                if os.path.exists(info['caminho']):
                    with open(info['caminho'], 'rb') as f:
                        pdf_data = f.read()
                    
                    col_pdf1, col_pdf2 = st.columns([3, 1])
                    with col_pdf1:
                        st.write(f"**{info['nome']}**")
                    with col_pdf2:
                        st.download_button(
                            label="⬇️ Baixar",
                            data=pdf_data,
                            file_name=info['nome'],
                            mime="application/pdf",
                            key=f"pdf_{grupo_id}"
                        )
        else:
            st.warning("⚠️ Nenhum PDF disponível para download. Verifique se a opção 'Baixar PDFs' estava habilitada.")
        
        # Seção 3: Relatório de disparo
        st.markdown("### 📱 Dados para Disparo (WhatsApp)")
        
        with st.expander("Ver dados formatados para disparo"):
            st.markdown("#### Template de Mensagem:")
            template = """Olá {{1}},

Este é um lembrete sobre o(s) título(s) em aberto no valor de {{2}}, com vencimento para {{3}}.

Por favor, entre em contato para regularizar a situação.

Atenciosamente,
Equipe Financeira"""
            
            st.code(template, language='text')
            
            st.markdown("#### Dados para substituição:")
            for _, row in df_resultados.iterrows():
                with st.expander(f"{row['Razao_Social']}"):
                    st.write(f"**{{1}}**: {row['Razao_Social']}")
                    st.write(f"**{{2}}**: R$ {row['Valor_Total']:,.2f}")
                    st.write(f"**{{3}}**: {row['Data_Vencimento']}")
        
        # Seção 4: Exportação em outros formatos
        st.markdown("### 🔄 Outros Formatos")
        
        col_format1, col_format2, col_format3 = st.columns(3)
        
        with col_format1:
            # CSV
            csv = df_resultados.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📄 CSV",
                data=csv,
                file_name="clientes_unificados.csv",
                mime="text/csv"
            )
        
        with col_format2:
            # JSON
            json_str = df_resultados.to_json(orient='records', force_ascii=False)
            st.download_button(
                label="📋 JSON",
                data=json_str.encode('utf-8'),
                file_name="clientes_unificados.json",
                mime="application/json"
            )
        
        with col_format3:
            # Texto simples
            txt_content = "CLIENTES UNIFICADOS\n===================\n\n"
            for _, row in df_resultados.iterrows():
                txt_content += f"""
Cliente: {row['Razao_Social']}
CNPJ: {row['CNPJ']}
Telefone: {row['Telefone_Contato']}
Valor: R$ {row['Valor_Total']:,.2f}
Vencimento: {row['Data_Vencimento']}
PDF: {row['PDF_Disponivel']}
{'-'*40}
"""
            
            st.download_button(
                label="📝 TXT",
                data=txt_content.encode('utf-8'),
                file_name="clientes_unificados.txt",
                mime="text/plain"
            )
    else:
        st.info("👆 Processe os dados para habilitar o download.")

# Rodapé
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #6B7280; font-size: 0.9rem;'>
    Desenvolvido por Sistema de Cobrança • Versão 1.0 • 
    Dados processados: {}
    </div>
    """.format(datetime.now().strftime("%d/%m/%Y %H:%M")),
    unsafe_allow_html=True
)
