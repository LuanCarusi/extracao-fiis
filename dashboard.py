import streamlit as st
import pandas as pd
import os

# Configuração da página
st.set_page_config(page_title="Dashboard de Fundos Imobiliários", layout="wide", initial_sidebar_state="expanded")

def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&family=Roboto:wght@300;400;700&display=swap');
        
        html, body, [class*="css"]  { font-family: 'Roboto', sans-serif; }
        h1, h2, h3 { font-family: 'Orbitron', sans-serif; color: #00d2ff; }
        
        div[data-testid="metric-container"] {
            background-color: #1e1e2f;
            border-left: 4px solid #00d2ff;
            padding: 10px 15px;
            border-radius: 4px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            margin-bottom: 10px;
        }
        .header-box {
            background-color: #11111b;
            padding: 10px;
            text-align: center;
            border-bottom: 2px solid #00d2ff;
            margin-bottom: 20px;
            font-weight: bold;
            font-size: 1.2rem;
            color: #ffffff;
            font-family: 'Orbitron', sans-serif;
            letter-spacing: 1px;
            border-radius: 5px 5px 0 0;
        }
        .stDataFrame { border: 1px solid #333; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

local_css()

# Função para classificar o P/VP
def classificar_pvp(pvp):
    if pd.isna(pvp):
        return "Indefinido"
    elif 0.95 <= pvp <= 1.05:
        return "Ancoragem"
    elif 0.80 <= pvp < 0.95:
        return "Crescimento"
    else: # pvp < 0.80
        return "Risco"

# Função para formatar os dados visuais
def format_data(df):
    df_view = df.copy()
    if 'Cotacao' in df_view.columns:
        df_view['Cotacao'] = df_view['Cotacao'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if not pd.isna(x) else "-")
    if 'Valor_de_Mercado' in df_view.columns:
        df_view['Valor_de_Mercado'] = df_view['Valor_de_Mercado'].apply(lambda x: f"R$ {x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".") if not pd.isna(x) else "-")
    if 'Liquidez' in df_view.columns:
        df_view['Liquidez'] = df_view['Liquidez'].apply(lambda x: f"R$ {x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".") if not pd.isna(x) else "-")
    
    perc_cols = ['FFO_Yield', 'Dividend_Yield', 'Vacancia_Media']
    for c in perc_cols:
        if c in df_view.columns:
            df_view[c] = df_view[c].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "-")
            
    if 'P_VP' in df_view.columns:
        df_view['P_VP'] = df_view['P_VP'].apply(lambda x: f"{x:.2f}" if not pd.isna(x) else "-")
        
    return df_view

# ============================================================
# CABEÇALHO
# ============================================================
st.title("🏢 Dashboard de Fundos Imobiliários")
st.markdown("Filtro e análise de FIIs baseados no método Magic Formula adaptado.")

st.sidebar.markdown('<div class="header-box">ATUALIZAR DADOS</div>', unsafe_allow_html=True)
ipca_rate_input = st.sidebar.number_input("Taxa IPCA+ Atual (%)", value=6.00, step=0.1, help="Utilizada para calcular o corte mínimo de Dividend Yield.")

def rodar_screening(ipca_rate):
    import subprocess
    try:
        subprocess.run(["python", "screening_fiis.py", "--ipca-rate", str(ipca_rate)], check=True)
        return True
    except Exception as e:
        st.sidebar.error(f"Erro ao executar script: {e}")
        return False

if st.sidebar.button("🔄 Atualizar Ranking Agora", use_container_width=True):
    with st.spinner("Extraindo e processando dados..."):
        if rodar_screening(ipca_rate_input):
            st.sidebar.success("Ranking atualizado com sucesso!")
            st.rerun()

st.sidebar.markdown('<br><div class="header-box">FILTROS DA CARTEIRA</div>', unsafe_allow_html=True)

# Tenta ler o arquivo de ranking
caminhos = ['ranking_fiis.xlsx', 'ranking_fiis.csv']
df_ranking = None

for path in caminhos:
    if os.path.exists(path):
        try:
            if path.endswith('.xlsx'):
                df_ranking = pd.read_excel(path)
            else:
                df_ranking = pd.read_csv(path, sep=';', decimal=',')
            break
        except Exception:
            pass

if df_ranking is None or df_ranking.empty:
    st.warning("⚠️ Arquivo de ranking não encontrado.")
    st.info("Execute o script `screening_fiis.py` primeiro para gerar os dados.")
else:
    # Cria a coluna de classificação
    df_ranking['Classificação'] = df_ranking['P_VP'].apply(classificar_pvp)
    
    # Organiza os filtros na barra lateral
    segmentos = sorted(df_ranking['Segmento'].dropna().unique().tolist())
    classificacoes = ["Ancoragem", "Crescimento", "Risco"]
    
    filtro_segmento = st.sidebar.multiselect(
        "Filtrar por Segmento",
        options=segmentos,
        default=[]
    )
    
    filtro_classificacao = st.sidebar.multiselect(
        "Filtrar por Classificação",
        options=classificacoes,
        default=[]
    )
    
    # Aplica os filtros
    df_filtrado = df_ranking.copy()
    
    if filtro_segmento:
        df_filtrado = df_filtrado[df_filtrado['Segmento'].isin(filtro_segmento)]
        
    if filtro_classificacao:
        df_filtrado = df_filtrado[df_filtrado['Classificação'].isin(filtro_classificacao)]
        
    # Remove as colunas de Rank visuais (Rank_P_VP, Rank_DY, Rank_Final_Soma)
    colunas_ocultas = ['Rank_P_VP', 'Rank_DY', 'Rank_Final_Soma']
    colunas_visiveis = [col for col in df_filtrado.columns if col not in colunas_ocultas]
    df_view = df_filtrado[colunas_visiveis]
    
    # Métricas Globais da seleção atual
    st.markdown('<div class="header-box">VISÃO GERAL DA SELEÇÃO</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ativos Encontrados", len(df_view))
    
    if len(df_view) > 0:
        dy_medio = df_view['Dividend_Yield'].mean()
        pvp_medio = df_view['P_VP'].mean()
        vac_media = df_view['Vacancia_Media'].mean()
        
        c2.metric("Dividend Yield Médio", f"{dy_medio:.2f}%")
        c3.metric("P/VP Médio", f"{pvp_medio:.2f}")
        c4.metric("Vacância Média", f"{vac_media:.2f}%")
    else:
        c2.metric("Dividend Yield Médio", "-")
        c3.metric("P/VP Médio", "-")
        c4.metric("Vacância Média", "-")
    
    st.markdown("---")
    st.markdown("### 📊 Tabela de Oportunidades (Rankeada)")
    
    # Mostrar os dados
    if not df_view.empty:
        df_display = format_data(df_view)
        st.dataframe(df_display, hide_index=True, use_container_width=True, height=600)
    else:
        st.info("Nenhum ativo corresponde aos filtros selecionados.")
