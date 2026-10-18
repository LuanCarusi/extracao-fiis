import streamlit as st
import pandas as pd
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from ai_formatter import parse_analysis_markdown, render_ai_dashboard, highlight_sources, get_ai_formatter_css

load_dotenv()

# Configuracao da pagina
st.set_page_config(
    page_title="Dashboard de Fundos Imobiliarios",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🏢",
)

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
        .ai-info-box {
            background: linear-gradient(135deg, #1e1e2f 0%, #16213e 100%);
            border: 1px solid #00d2ff33;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
    </style>
    """, unsafe_allow_html=True)

local_css()

# Funcao para classificar o P/VP
def classificar_pvp(pvp):
    if pd.isna(pvp):
        return "Indefinido"
    elif 0.95 <= pvp <= 1.05:
        return "Ancoragem"
    elif 0.80 <= pvp < 0.95:
        return "Crescimento"
    else:
        return "Risco"

# Funcao para formatar os dados visuais
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
# CABECALHO GLOBAL
# ============================================================
st.title("🏢 Dashboard de Fundos Imobiliarios")
st.markdown("Filtro, ranking e analise profunda de FIIs com suporte a Inteligencia Artificial.")

# ============================================================
# SIDEBAR GLOBAL
# ============================================================
st.sidebar.markdown('<div class="header-box">ATUALIZAR DADOS</div>', unsafe_allow_html=True)
ipca_rate_input = st.sidebar.number_input("Taxa IPCA+ Atual (%)", value=6.00, step=0.1, help="Utilizada para calcular o corte minimo de Dividend Yield.")

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

# ============================================================
# ABAS PRINCIPAIS
# ============================================================
tab_ranking, tab_ia = st.tabs(["📊 Ranking & Filtros", "🤖 Analise por IA"])

# ──────────────────────────────────────────────────────────
# ABA 1 — RANKING & FILTROS (logica original preservada)
# ──────────────────────────────────────────────────────────
with tab_ranking:

    st.sidebar.markdown('<br><div class="header-box">FILTROS DA CARTEIRA</div>', unsafe_allow_html=True)

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
        st.warning("⚠️ Arquivo de ranking nao encontrado.")
        st.info("Execute o script `screening_fiis.py` primeiro para gerar os dados.")
    else:
        df_ranking['Classificacao'] = df_ranking['P_VP'].apply(classificar_pvp)
        
        segmentos = sorted(df_ranking['Segmento'].dropna().unique().tolist())
        classificacoes = ["Ancoragem", "Crescimento", "Risco"]
        
        filtro_segmento = st.sidebar.multiselect("Filtrar por Segmento", options=segmentos, default=[])
        filtro_classificacao = st.sidebar.multiselect("Filtrar por Classificacao", options=classificacoes, default=[])
        
        df_filtrado = df_ranking.copy()
        
        if filtro_segmento:
            df_filtrado = df_filtrado[df_filtrado['Segmento'].isin(filtro_segmento)]
        if filtro_classificacao:
            df_filtrado = df_filtrado[df_filtrado['Classificacao'].isin(filtro_classificacao)]
            
        colunas_ocultas = ['Rank_P_VP', 'Rank_DY', 'Rank_Final_Soma']
        colunas_visiveis = [col for col in df_filtrado.columns if col not in colunas_ocultas]
        df_view = df_filtrado[colunas_visiveis]
        
        st.markdown('<div class="header-box">VISAO GERAL DA SELECAO</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ativos Encontrados", len(df_view))
        
        if len(df_view) > 0:
            dy_medio = df_view['Dividend_Yield'].mean()
            pvp_medio = df_view['P_VP'].mean()
            vac_media = df_view['Vacancia_Media'].mean()
            c2.metric("Dividend Yield Medio", f"{dy_medio:.2f}%")
            c3.metric("P/VP Medio", f"{pvp_medio:.2f}")
            c4.metric("Vacancia Media", f"{vac_media:.2f}%")
        else:
            c2.metric("Dividend Yield Medio", "-")
            c3.metric("P/VP Medio", "-")
            c4.metric("Vacancia Media", "-")
        
        st.markdown("---")
        st.markdown("### 📊 Tabela de Oportunidades (Rankeada)")
        
        if not df_view.empty:
            df_display = format_data(df_view)
            st.dataframe(df_display, hide_index=True, use_container_width=True, height=600)
        else:
            st.info("Nenhum ativo corresponde aos filtros selecionados.")

# ──────────────────────────────────────────────────────────
# ABA 2 — ANALISE POR IA
# ──────────────────────────────────────────────────────────
with tab_ia:

    st.markdown("### 🤖 Analise Profunda de FII com Inteligencia Artificial")
    st.markdown(
        "Faca upload do **Relatorio Gerencial** (obrigatorio) e, opcionalmente, do "
        "**Informe Mensal Estruturado (IME)** e/ou **Fatos Relevantes** para uma analise completa. "
        "A IA seguira estritamente a metodologia de analise definida internamente."
    )

    # Configuracao da API Key
    st.markdown("---")
    col_key, col_info = st.columns([2, 1])
    with col_key:
        gemini_api_key = st.text_input(
            "🔑 Chave da API Gemini",
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            help="Obtenha gratuitamente em https://aistudio.google.com/app/apikey",
            placeholder="AIza...",
        )
    with col_info:
        st.info("💡 **Dica:** Coloque sua chave no arquivo `.env` como `GEMINI_API_KEY=...` para nao precisar digitar toda vez.")

    st.markdown("---")

    # Upload de arquivos
    st.markdown("#### 📎 Anexar Documentos")
    MAX_SIZE_MB = 20
    uploaded_files = st.file_uploader(
        f"Selecione os documentos do FII (.pdf ou .xml para IME — max. {MAX_SIZE_MB} MB por arquivo)",
        type=["pdf", "xml"],
        accept_multiple_files=True,
        help="Tipos suportados: Relatorio Gerencial (.pdf), IME / Informe Mensal Estruturado (.xml ou .pdf), Fatos Relevantes (.pdf).",
        key="fii_docs_uploader",
    )

    # Validacao de arquivos
    files_ok = True
    if uploaded_files:
        for f in uploaded_files:
            size_mb = len(f.getvalue()) / (1024 * 1024)
            if size_mb > MAX_SIZE_MB:
                st.error(f"⚠️ O arquivo **{f.name}** excede {MAX_SIZE_MB} MB ({size_mb:.1f} MB). Por favor, reduza o tamanho.")
                files_ok = False

        if files_ok:
            st.success(f"✅ {len(uploaded_files)} arquivo(s) carregado(s) com sucesso.")
            cols = st.columns(min(len(uploaded_files), 3))
            for i, f in enumerate(uploaded_files):
                size_mb = len(f.getvalue()) / (1024 * 1024)
                icon = "📋" if f.name.lower().endswith(".xml") else "📄"
                tipo_badge = "XML/IME" if f.name.lower().endswith(".xml") else "PDF"
                cols[i % 3].markdown(f"{icon} **{f.name}** `[{tipo_badge}]` ({size_mb:.1f} MB)")


    st.markdown("---")

    # Cache de analises anteriores
    cache_dir = Path(".ai_cache")
    cached_analyses = {}
    if cache_dir.exists():
        for cp in sorted(cache_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                cdata = json.loads(cp.read_text(encoding="utf-8"))
                cmeta = cdata.get("metadata", {})
                first_line = cdata.get("result", "").splitlines()[0] if cdata.get("result") else ""
                label_clean = first_line.replace("# Analise de Fundo de ", "").replace("#", "").strip() or cp.stem
                docs_str = ", ".join(cmeta.get("doc_names", []))
                display_label = f"🏢 {label_clean} — [{docs_str}]"
                cached_analyses[display_label] = (cdata.get("result", ""), cmeta)
            except Exception:
                pass

    col_btn, col_cache = st.columns([1.5, 1])
    with col_btn:
        btn_disabled = not uploaded_files or not files_ok or not gemini_api_key
        if st.button(
            "🔍 Analisar Documentos com IA",
            use_container_width=True,
            disabled=btn_disabled,
            type="primary",
            key="btn_analyze",
        ):
            if not gemini_api_key:
                st.error("❌ Insira sua chave da API Gemini antes de analisar.")
            elif not uploaded_files:
                st.warning("⚠️ Faca upload de pelo menos um PDF/XML para analisar.")
            else:
                try:
                    from ai_analyzer import analyze_documents

                    for f in uploaded_files:
                        f.seek(0)

                    with st.spinner("🧠 Analisando documentos... Isso pode levar ate 30 segundos."):
                        result, metadata = analyze_documents(
                            uploaded_files=uploaded_files,
                            api_key=gemini_api_key,
                            cache_dir=".ai_cache",
                        )

                    st.session_state["ai_result"] = result
                    st.session_state["ai_metadata"] = metadata
                    st.success(
                        f"✅ Analise concluida! {metadata['doc_count']} documento(s) processado(s). "
                        f"Cache key: `{metadata['cache_key'][:8]}...`"
                    )

                except ImportError:
                    st.error("❌ Modulo `ai_analyzer` nao encontrado. Verifique se o arquivo `ai_analyzer.py` esta na mesma pasta do dashboard.")
                except RuntimeError as e:
                    st.error(f"❌ Erro na API Gemini: {e}")
                    if "API_KEY" in str(e).upper():
                        st.info("💡 Verifique se sua chave da API esta correta e se voce tem cota disponivel.")
                except Exception as e:
                    st.error(f"❌ Erro inesperado: {e}")
                    st.exception(e)

    with col_cache:
        if cached_analyses:
            selected_cache = st.selectbox(
                "📂 Carregar análise recente do cache:",
                options=["-- Selecionar do histórico --"] + list(cached_analyses.keys()),
                key="cache_analysis_selector",
                help="Carrega analises salvas anteriormente sem precisar gastar cotas ou reenviar os documentos."
            )
            if selected_cache != "-- Selecionar do histórico --":
                st.session_state["ai_result"] = cached_analyses[selected_cache][0]
                st.session_state["ai_metadata"] = cached_analyses[selected_cache][1]

    # Se ainda nao ha resultado na sessao mas ha analises no cache, carrega a mais recente automaticamente
    if "ai_result" not in st.session_state and cached_analyses:
        latest_label = list(cached_analyses.keys())[0]
        st.session_state["ai_result"] = cached_analyses[latest_label][0]
        st.session_state["ai_metadata"] = cached_analyses[latest_label][1]

    # Aviso quando botao esta desativado
    if not gemini_api_key:
        st.warning("🔑 Configure a chave da API Gemini para habilitar novas analises.")
    elif not uploaded_files and "ai_result" not in st.session_state:
        st.info("📎 Faca upload de um ou mais documentos (.pdf ou .xml) para comecar a analise.")

    # RENDERIZACAO EXECUTIVA DO RESULTADO
    if "ai_result" in st.session_state and st.session_state["ai_result"]:
        active_result = st.session_state["ai_result"]
        active_metadata = st.session_state.get("ai_metadata", {})

        st.markdown("---")
        st.markdown("## 📋 Resultado da Analise Profunda")

        parsed = parse_analysis_markdown(active_result)
        if parsed.get("is_parsed"):
            render_ai_dashboard(parsed, st)
        else:
            # Fallback seguro para garantir 100% de disponibilidade
            st.markdown(highlight_sources(active_result), unsafe_allow_html=True)

        # Botao de download em largura total
        st.markdown("---")
        doc_names = ", ".join(active_metadata.get("doc_names", ["documentos_analisados"]))
        cache_id = active_metadata.get("cache_key", "resultado")[:8]
        st.download_button(
            label="💾 Baixar Relatório Completo (.md)",
            data=active_result.encode("utf-8"),
            file_name=f"analise_fii_{cache_id}.md",
            mime="text/markdown",
            key="btn_download_result",
            help=f"Documentos analisados: {doc_names}",
            use_container_width=True
        )

    # Rodape informativo
    st.markdown("---")
    with st.expander("ℹ️ Como funciona a analise por IA?"):
        st.markdown("""
        **Pipeline de analise:**
        1. **Extracao de texto**: Os documentos (.pdf e .xml) sao processados e o texto e extraido (com marcacao de paginas e tags)
        2. **Identificacao do fundo**: A IA identifica se e Tijolo ou Papel
        3. **Preenchimento do template**: A IA preenche as 5 secoes da analise seguindo a metodologia
        4. **Citacao de fontes**: Cada metrica inclui o documento e pagina/tag de origem
        
        **Documentos suportados:**
        - 📊 **Relatorio Gerencial** (.pdf — obrigatorio) — fonte principal de dados
        - 📋 **Informe Mensal Estruturado (IME)** (.xml ou .pdf) — complementa dados de ativo, passivo e alavancagem
        - 📢 **Fatos Relevantes** (.pdf) — eventos e comunicados recentes
        
        **Classificacoes geradas:**
        - 🏛️ **Ancoragem** — fundo consolidado, P/VP ~ 1.0
        - 💡 **Oportunidade** — desconto potencial, P/VP entre 0.7 e 1.0
        - ⚠️ **Risco** — problemas identificados, P/VP < 0.7
        
        **Privacidade:** Os documentos sao enviados para a API do Google Gemini para processamento.
        A chave de API nunca e armazenada permanentemente no servidor.
        """)
