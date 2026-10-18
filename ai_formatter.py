"""
ai_formatter.py — Formatador e renderizador executivo da analise de FIIs por IA.
Responsavel por:
1. Eliminar o bug de renderizacao KaTeX/LaTeX nos valores monetarios (R$).
2. Destacar exclusivamente as fontes de informacao (Relatorio, Informe, etc.).
3. Transformar o relatorio em um visual moderno, executivo e compativel com o dashboard,
   sem alterar ou reduzir nenhuma informacao.
"""

import re
import html
from typing import Dict, Any, List

def clean_financial_text(text: str) -> str:
    """
    Higieniza o texto financeiro:
    1. Remove qualquer barra invertida indevida antes de cifroes (ex: R\\$ -> R$).
    2. Traduz siglas em ingles como YoY, MoM, QoQ para portugues claro (ex: vs. ano anterior).
    3. Converte '$' na entidade HTML '&#36;' para garantir que o interpretador
       KaTeX/LaTeX do Streamlit jamais interprete valores monetarios como equacoes matematicas
       e sem exibir barras invertidas indesejadas no navegador.
    """
    if not text:
        return ""

    # 1. Remove qualquer barra invertida antes do cifrao
    cleaned = re.sub(r'\\+\$', '$', text)

    # 2. Traduz/substitui siglas em ingles
    cleaned = re.sub(r'\bYoY\b', 'vs. ano anterior', cleaned)
    cleaned = re.sub(r'\byoy\b', 'vs. ano anterior', cleaned)
    cleaned = re.sub(r'\bMoM\b', 'vs. mês anterior', cleaned)
    cleaned = re.sub(r'\bmom\b', 'vs. mês anterior', cleaned)
    cleaned = re.sub(r'\bQoQ\b', 'vs. trimestre anterior', cleaned)
    cleaned = re.sub(r'\bqoq\b', 'vs. trimestre anterior', cleaned)

    # 3. Converte cifroes em entidade HTML segura
    cleaned = cleaned.replace('$', '&#36;')
    return cleaned


def highlight_sources(text: str) -> str:
    """
    Higieniza o texto (eliminando R\\$ e YoY) e destaca EXCLUSIVAMENTE
    as referencias/fontes de documentos com uma badge visual elegante.
    """
    if not text:
        return ""

    # 1. Limpa moedas e siglas
    safe_text = clean_financial_text(text)

    # 2. Converte citacoes de fontes em tags HTML estilizadas
    def _badge_replacer(match: re.Match) -> str:
        content = match.group(1).strip()
        
        # Define icone baseado no tipo de documento
        lower = content.lower()
        if any(k in lower for k in ["xml", "tag", "ime", "informe"]):
            icon = "📋"
        elif any(k in lower for k in ["fato", "comunicado", "aviso"]):
            icon = "📢"
        else:
            icon = "📄"

        # Limpa eventuais backticks internos
        clean_content = content.replace("`", "")
        # Escapa tags XML como <AtivoTotal> para nao sumirem no HTML
        clean_content = clean_content.replace("<", "&lt;").replace(">", "&gt;")

        return f'<span class="fii-source-badge">{icon} {clean_content}</span>'

    # Padrao refinado para capturar citacoes de fontes
    source_pattern = r'`?\(\s*([^\)]*?(?:Relat[oó]rio|Informe|Fato Relevante|Fonte|Informe_|\.xml|\.pdf|tag\s*<|tag\s*&lt;|tags\s*<|tags\s*&lt;|pag\.|pág\.)[^\)]*?)\s*\)`?'

    return re.sub(source_pattern, _badge_replacer, safe_text, flags=re.IGNORECASE)


def parse_analysis_markdown(md_text: str) -> Dict[str, Any]:
    """
    Faz o parse estruturado do markdown retornado pelo Gemini.
    Preserva 100% dos dados originais.
    """
    data = {
        "title": "",
        "ticker": "",
        "fund_name": "",
        "fund_type": "",
        "classification": "",
        "justification": "",
        "sections": {
            "1": {"title": "Informações Gerais e Estratégia", "icon": "🎯", "rows": []},
            "2": {"title": "Indicadores Operacionais e Financeiros", "icon": "📊", "rows": []},
            "3": {"title": "Portfólio e Contratos", "icon": "📑", "rows": []},
            "4": {"title": "Resultados e Distribuições", "icon": "💰", "rows": []},
        },
        "risk_events": {"title": "Eventos Relevantes e Riscos", "icon": "⚠️", "items": []},
        "conclusion": "",
        "raw_markdown": md_text,
        "is_parsed": False
    }

    if not md_text or not isinstance(md_text, str):
        return data

    lines = md_text.splitlines()

    # 1. Titulo, Ticker e Tipo
    for line in lines:
        line_clean = line.strip()
        if "Analise de Fundo de" in line_clean:
            data["title"] = line_clean.lstrip("#").strip()
            
            m_type = re.search(r"Fundo de\s+([A-Za-z]+):", line_clean, re.I)
            if m_type:
                data["fund_type"] = m_type.group(1).capitalize()
                
            m_ticker = re.search(r":\s*([A-Za-z0-9]{4,6}\d{0,2})\s*(?:\((.*?)\))?", line_clean)
            if m_ticker:
                data["ticker"] = m_ticker.group(1).strip()
                if m_ticker.group(2):
                    data["fund_name"] = m_ticker.group(2).strip()
            break

    # 2. Perfil do Fundo
    m_class = re.search(r">\s*\*\*Classificacao:\*\*\s*(.+)", md_text, re.I)
    if m_class:
        data["classification"] = m_class.group(1).strip()
        
    m_just = re.search(r">\s*\*\*Justificativa:\*\*\s*(.+)", md_text, re.I)
    if m_just:
        data["justification"] = m_just.group(1).strip()

    # 3. Secoes 1 a 4 (Tabelas de Metricas)
    section_defs = [
        ("1", r"#{2,4}\s*1\.\s*Informac[oõ]es Gerais e Estrat[eé]gia"),
        ("2", r"#{2,4}\s*2\.\s*Indicadores Operacionais e Financeiros"),
        ("3", r"#{2,4}\s*3\.\s*Portf[oó]lio e Contratos"),
        ("4", r"#{2,4}\s*4\.\s*Resultados e Distribuic[oõ]es"),
    ]

    for sec_num, sec_pat in section_defs:
        m_start = re.search(sec_pat, md_text, re.I)
        if not m_start:
            continue
        start_idx = m_start.end()
        next_m = re.search(r"\n---\s*\n|\n#{2,4}\s+", md_text[start_idx:])
        sec_content = md_text[start_idx:start_idx + next_m.start()] if next_m else md_text[start_idx:]

        rows = []
        for line in sec_content.splitlines():
            line_s = line.strip()
            if not line_s.startswith("|") or line_s.startswith("| :") or "Metrica" in line_s:
                continue
            cols = [c.strip() for c in line_s.split("|")[1:-1]]
            if len(cols) >= 2:
                metrica = cols[0].replace("**", "").strip()
                analise = cols[1].strip()
                rows.append({
                    "metrica": metrica,
                    "analise_raw": analise,
                    "analise_formatted": highlight_sources(analise)
                })
        data["sections"][sec_num]["rows"] = rows

    # 4. Secao 5 (Eventos Relevantes e Riscos a Monitorar)
    m_sec5 = re.search(
        r"#{2,4}\s*5\.\s*Eventos Relevantes e Riscos a Monitorar(.*?)(?=\n---\s*\n|\n#{2,4}\s+CONCLUS[AÃ]O|\Z)",
        md_text,
        re.S | re.I
    )
    if m_sec5:
        sec5_text = m_sec5.group(1).strip()
        items = []

        m_com = re.search(r"\*\s*\*\*Comunicados Importantes:\*\*\s*(.*?)(?=\n\*\s*\*\*|\Z)", sec5_text, re.S | re.I)
        if m_com:
            items.append({
                "title": "Comunicados Importantes",
                "icon": "📢",
                "type": "info",
                "content": highlight_sources(m_com.group(1).strip())
            })

        m_ris = re.search(r"\*\s*\*\*Risco do Fundo:\*\*\s*(.*?)(?=\n\*\s*\*\*|\Z)", sec5_text, re.S | re.I)
        if m_ris:
            items.append({
                "title": "Risco do Fundo",
                "icon": "🛡️",
                "type": "risk",
                "content": highlight_sources(m_ris.group(1).strip())
            })

        m_pon = re.search(r"\*\s*\*\*Pontos de Aten[cç][aã]o:\*\*\s*(.*?)(?=\n\*\s*\*\*|\Z)", sec5_text, re.S | re.I)
        if m_pon:
            items.append({
                "title": "Pontos de Atenção",
                "icon": "🔍",
                "type": "warning",
                "content": highlight_sources(m_pon.group(1).strip())
            })

        data["risk_events"]["items"] = items

    # 5. Conclusao Geral
    m_conc = re.search(r"#{2,4}\s*CONCLUS[AÃ]O GERAL\s*\n+(.*?)(?=\n---\s*\n|\Z)", md_text, re.S | re.I)
    if m_conc:
        data["conclusion"] = highlight_sources(m_conc.group(1).strip())

    # Checagem de sucesso no parse
    has_rows = any(len(sec["rows"]) > 0 for sec in data["sections"].values())
    data["is_parsed"] = has_rows

    return data


def get_ai_formatter_css() -> str:
    """Retorna o CSS customizado para os componentes visuais da analise por IA."""
    return """
    <style>
        /* Hero Card Executivo */
        .fii-hero-card {
            background: linear-gradient(135deg, #131728 0%, #0d101d 100%);
            border: 1px solid rgba(0, 210, 255, 0.25);
            border-radius: 12px;
            padding: 22px 26px;
            margin-bottom: 22px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        .fii-hero-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 14px;
        }
        .fii-hero-ticker {
            font-family: 'Orbitron', sans-serif;
            font-size: 2.2rem;
            font-weight: 700;
            color: #00d2ff;
            letter-spacing: 2px;
            display: inline-flex;
            align-items: center;
            gap: 12px;
        }
        .fii-hero-name {
            font-size: 1.05rem;
            color: #94a3b8;
            font-weight: 400;
            margin-top: 2px;
        }
        .fii-badge-type {
            display: inline-block;
            background: rgba(0, 210, 255, 0.12);
            color: #00d2ff;
            border: 1px solid rgba(0, 210, 255, 0.4);
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .fii-badge-classification {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 18px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 1rem;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        .fii-class-oportunidade {
            background: rgba(0, 210, 255, 0.15);
            border: 1.5px solid #00d2ff;
            color: #00d2ff;
            box-shadow: 0 0 15px rgba(0, 210, 255, 0.2);
        }
        .fii-class-ancoragem {
            background: rgba(46, 204, 113, 0.15);
            border: 1.5px solid #2ecc71;
            color: #2ecc71;
            box-shadow: 0 0 15px rgba(46, 204, 113, 0.2);
        }
        .fii-class-risco {
            background: rgba(231, 76, 60, 0.15);
            border: 1.5px solid #e74c3c;
            color: #e74c3c;
            box-shadow: 0 0 15px rgba(231, 76, 60, 0.2);
        }
        .fii-justification-box {
            background: rgba(17, 17, 27, 0.85);
            border-left: 4px solid #00d2ff;
            border-radius: 6px;
            padding: 16px 20px;
            margin-top: 14px;
            color: #e2e8f0;
            font-size: 0.96rem;
            line-height: 1.65;
        }

        /* Badge Exclusiva para Fontes de Informacao */
        .fii-source-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(0, 210, 255, 0.12);
            border: 1px solid rgba(0, 210, 255, 0.45);
            color: #5eead4;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 0.82rem;
            font-family: 'Roboto', sans-serif;
            font-weight: 500;
            margin-top: 4px;
            margin-right: 6px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }

        /* Cards de Metricas */
        .fii-metric-card {
            background: #161a2b;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-left: 4px solid #00d2ff;
            border-radius: 8px;
            padding: 16px 18px;
            margin-bottom: 14px;
            transition: all 0.2s ease-in-out;
        }
        .fii-metric-card:hover {
            border-color: #00d2ff;
            background: #1a1f33;
            box-shadow: 0 4px 14px rgba(0, 210, 255, 0.15);
        }
        .fii-metric-header {
            color: #00d2ff;
            font-weight: 700;
            font-size: 1.02rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .fii-metric-body {
            color: #f1f5f9;
            font-size: 0.95rem;
            line-height: 1.65;
        }

        /* Cards de Eventos e Riscos (Secao 5) */
        .fii-risk-card {
            background: #161a2b;
            border-radius: 8px;
            padding: 18px 20px;
            margin-bottom: 16px;
            border-left: 4px solid #00d2ff;
        }
        .fii-risk-card.info {
            border-left-color: #00d2ff;
        }
        .fii-risk-card.risk {
            border-left-color: #38bdf8;
        }
        .fii-risk-card.warning {
            border-left-color: #fbbf24;
        }
        .fii-risk-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .fii-risk-content {
            color: #f1f5f9;
            font-size: 0.95rem;
            line-height: 1.65;
        }

        /* Caixa de Conclusao Geral */
        .fii-conclusion-box {
            background: linear-gradient(135deg, #15192c 0%, #0f1322 100%);
            border: 1px solid rgba(0, 210, 255, 0.35);
            border-left: 5px solid #00d2ff;
            border-radius: 10px;
            padding: 24px;
            color: #f8fafc;
            font-size: 0.98rem;
            line-height: 1.75;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
        }
    </style>
    """


def render_ai_dashboard(parsed_data: Dict[str, Any], st_module) -> None:
    """
    Renderiza o dashboard de analise profunda no Streamlit com alto padrao visual,
    suporte a alternancia de modos de visualizacao e sem perda de informacoes.
    """
    st_module.markdown(get_ai_formatter_css(), unsafe_allow_html=True)

    ticker = parsed_data.get("ticker", "FII")
    fund_name = parsed_data.get("fund_name", "")
    fund_type = parsed_data.get("fund_type", "Imobiliário")
    classification = parsed_data.get("classification", "")
    justification = parsed_data.get("justification", "")
    sections = parsed_data.get("sections", {})
    risk_events = parsed_data.get("risk_events", {})
    conclusion = parsed_data.get("conclusion", "")
    raw_markdown = parsed_data.get("raw_markdown", "")

    # Define estilo do badge de classificacao
    class_lower = classification.lower()
    if "oportunidade" in class_lower:
        badge_class = "fii-class-oportunidade"
        badge_icon = "💡"
    elif "ancoragem" in class_lower:
        badge_class = "fii-class-ancoragem"
        badge_icon = "🏛️"
    elif "risco" in class_lower:
        badge_class = "fii-class-risco"
        badge_icon = "⚠️"
    else:
        badge_class = "fii-class-oportunidade"
        badge_icon = "📌"

    # 1. HERO CARD EXECUTIVO
    hero_html = f"""
    <div class="fii-hero-card">
        <div class="fii-hero-top">
            <div>
                <div class="fii-hero-ticker">🏢 {ticker}</div>
                <div class="fii-hero-name">{fund_name}</div>
            </div>
            <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                <span class="fii-badge-type">Fundo de {fund_type}</span>
                <span class="fii-badge-classification {badge_class}">{badge_icon} {classification}</span>
            </div>
        </div>
        <div class="fii-justification-box">
            <strong>📋 Justificativa do Perfil:</strong><br>
            {highlight_sources(justification)}
        </div>
    </div>
    """
    st_module.markdown(hero_html, unsafe_allow_html=True)

    # 2. SELETOR DE MODO DE VISUALIZACAO
    col_view, col_spacer = st_module.columns([3, 1])
    with col_view:
        view_mode = st_module.radio(
            "📐 Formato de Visualização:",
            [
                "📱 Cartões por Categoria (Recomendado)",
                "📄 Relatório Contínuo / Markdown"
            ],
            index=0,
            horizontal=True,
            key="ai_view_mode_selector"
        )

    st_module.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # MODO 1: CARTOES POR CATEGORIA (SUB-TABS ORGANIZADAS)
    # =========================================================================
    if view_mode == "📱 Cartões por Categoria (Recomendado)":
        tab_titles = [
            f"{sections['1']['icon']} 1. Geral & Estratégia",
            f"{sections['2']['icon']} 2. Operacional & Financeiro",
            f"{sections['3']['icon']} 3. Portfólio & Contratos",
            f"{sections['4']['icon']} 4. Resultados & Distribuições",
            f"{risk_events['icon']} 5. Riscos & Eventos",
            "📝 Conclusão Geral"
        ]
        subtabs = st_module.tabs(tab_titles)

        # Abas de 1 a 4 (Metricas)
        for i, sec_key in enumerate(["1", "2", "3", "4"]):
            with subtabs[i]:
                sec_data = sections.get(sec_key, {})
                rows = sec_data.get("rows", [])
                st_module.markdown(f"#### {sec_data['icon']} {sec_data['title']}")

                if not rows:
                    st_module.info("Nenhuma métrica detalhada nesta seção.")
                else:
                    for row in rows:
                        card_html = f"""
                        <div class="fii-metric-card">
                            <div class="fii-metric-header">
                                <span>🔹</span> {row['metrica']}
                            </div>
                            <div class="fii-metric-body">
                                {row['analise_formatted']}
                            </div>
                        </div>
                        """
                        st_module.markdown(card_html, unsafe_allow_html=True)

        # Aba 5 (Riscos e Eventos)
        with subtabs[4]:
            st_module.markdown(f"#### {risk_events['icon']} {risk_events['title']}")
            items = risk_events.get("items", [])
            if not items:
                st_module.info("Nenhum evento relevante reportado.")
            else:
                for item in items:
                    item_type = item.get("type", "info")
                    card_html = f"""
                    <div class="fii-risk-card {item_type}">
                        <div class="fii-risk-title">{item['icon']} {item['title']}</div>
                        <div class="fii-risk-content">{item['content']}</div>
                    </div>
                    """
                    st_module.markdown(card_html, unsafe_allow_html=True)

        # Aba 6 (Conclusao Geral)
        with subtabs[5]:
            st_module.markdown("#### 📝 Conclusão e Tese de Investimento")
            if not conclusion:
                st_module.info("Conclusão não informada.")
            else:
                conclusion_html = f"""
                <div class="fii-conclusion-box">
                    {conclusion}
                </div>
                """
                st_module.markdown(conclusion_html, unsafe_allow_html=True)

    # =========================================================================
    # MODO 2: RELATORIO CONTINUO / MARKDOWN HIGIENIZADO
    # =========================================================================
    else:
        st_module.markdown("#### 📄 Relatório Formatado (KaTeX Higienizado & Fontes Destacadas)")
        sanitized_md = highlight_sources(raw_markdown)
        st_module.markdown(sanitized_md, unsafe_allow_html=True)


