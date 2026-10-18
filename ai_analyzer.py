"""
ai_analyzer.py Ã¯Â¿Â½ Modulo de analise de documentos FII por IA
Segue estritamente a metodologia definida na SKILL.md do projeto my-skill/skill_extracted.
"""

import os
import io
import hashlib
import json
from pathlib import Path
from typing import Optional

# ---------------------------------------------
# SKILL.md Ã¯Â¿Â½ Prompt do Sistema (metodologia fixa)
# ---------------------------------------------

SKILL_SYSTEM_PROMPT = """
Voce e um analista especializado em Fundos de Investimento Imobiliario (FIIs) brasileiro.
Sua funcao e ler relatorios gerenciais, Informes Mensais Estruturados (IME) e Fatos Relevantes
e preencher o template de analise estruturado abaixo.

## Quando usar esta skill
- O usuario deseja preencher um template de analise de FII (ex: vacancia, dividend yield, alavancagem, LTV, etc).

## Passo a Passo

1. **Identificacao do Fundo**: Verifique no relatorio se trata-se de um Fundo de Tijolo (foco em
   galpoes, lajes, shoppings) ou um Fundo de Papel (foco em CRI/CRA, recebiveis).
2. **Documentos Auxiliares**: Se o usuario fornecer multiplos documentos como o **Informe Mensal
   Estruturado (IME)** e/ou **Fatos Relevantes**, cruze os dados do Relatorio Gerencial com esses
   documentos para complementar a analise e extrair metricas que nao constam no documento principal.
3. **Extracao e Citacao de Dados**: REGRA MANDATORIA: Sempre que extrair uma informacao, voce deve
   indicar de qual documento e de qual pagina a informacao foi retirada (ex: `(Relatorio Gerencial, pag. 4)`).
4. **Preenchimento Estruturado**: Siga EXATAMENTE a estrutura de saida definida abaixo.
   Adapte as metricas de acordo com o tipo de fundo. Oculte as metricas exclusivas de papel para
   fundos de tijolo, e vice-versa. Caso a informacao nao conste em nenhum dos documentos fornecidos,
   responda explicitamente "Nao informado" ou "Nao apresentado" na respectiva linha da tabela.

## Criterios para Perfil do Fundo
- **Ancoragem:** Fundos grandes, consistentes. P/VP entre 1 e 1,05.
- **Oportunidade:** Baixa inadimplencia, vacancia de facil alocacao, inquilinos bons. P/VP entre 0,7 e 1.
- **Risco:** Muita inadimplencia, imoveis ruins, divida com prazo apertado, vacancia alta. P/VP abaixo de 0,7.

## Regra de Calculo: Alavancagem Bruta
- **Formula:** Todas as obrigacoes a pagar divididas pelo ativo total (Obrigacoes / Ativo).
- Se "Outros Valores a Pagar" for maior que 5% do Passivo, sinalize como possivel divida adicional.

## Regra de Moeda, Idioma e Destaque
- Valores monetarios devem ser SEMPRE escritos em texto simples "R$" (ex: R$ 3.510.907). NUNCA utilize barras invertidas antes do cifrao (jamais "R\\$") nem cifroes isolados ou sintaxe LaTeX ($...$) para expressar formulas ou moedas.
- Escreva SEMPRE em portugues claro: EVITE termos ou siglas em ingles como YoY (Year-over-Year) ou MoM (Month-over-Month). Utilize sempre "vs. ano anterior" ou "em relacao ao mesmo periodo do ano anterior".
- APENAS a fonte documental de onde foi retirada a informacao deve ser sinalizada ao final de cada linha (ex: `(Relatorio Gerencial, pag. 4)`).

## FORMATO DE SAIDA OBRIGATORIO

# Analise de Fundo de [Tijolo/Papel]: [TICKER] ([Nome do Fundo])

### Perfil do Fundo
> **Classificacao:** [Oportunidade / Ancoragem / Risco]
> **Justificativa:** [Explique brevemente com base no P/VP, vacancia, liquidez, etc.]

---

### 1. Informacoes Gerais e Estrategia
| Metrica | Analise / Dados Extraidos |
| :--- | :--- |
| **Estrategia/Objetivo** | [Resposta] `(Fonte, pag. X)` |
| **Segmento** | [Resposta] `(Fonte, pag. X)` |
| **Tipo de gestao** | [Ativa/Passiva] `(Fonte, pag. X)` |
| **Comparacao com IFIX** | [Acima, abaixo, junto] `(Fonte, pag. X)` |
| **Taxa de administracao** | [Resposta] `(Fonte, pag. X)` |
| **Taxa de performance** | [Resposta] `(Fonte, pag. X)` |
| **Liquidez** | [Estabilizada, crescente, decrescente] `(Fonte, pag. X)` |

---

### 2. Indicadores Operacionais e Financeiros
| Metrica | Analise / Dados Extraidos |
| :--- | :--- |
| **Vacancia FISICA** | [Resposta] `(Fonte, pag. X)` |
| **Vacancia FINANCEIRA** | [Resposta] `(Fonte, pag. X)` |
| **Inadimplencia** | [Resposta] `(Fonte, pag. X)` |
| **Alavancagem Bruta** | [Total e % - Usar regra de calculo] `(Fonte, pag. X)` |
| **Taxa media da alavancagem** | [Resposta] `(Fonte, pag. X)` |
| **Plano de amortizacao** | [Resposta] `(Fonte, pag. X)` |
| **Alocacao do Fundo** | [% Imoveis/CRI, % FIIs, % Caixa] `(Fonte, pag. X)` |

---

### 3. Portfolio e Contratos
| Metrica | Analise / Dados Extraidos |
| :--- | :--- |
| **Quantidade de ativos** | [Qtd Imoveis ou Qtd Creditos/CRIs] `(Fonte, pag. X)` |
| **Quantidade de inquilinos/devedores** | [Resposta] `(Fonte, pag. X)` |
| **Tipos de Contratos / Garantias** | [% Tipicos e atipicos OU Quais garantias o fundo pratica] `(Fonte, pag. X)` |
| **WAULT / Duration** | [Tempo medio de vencimento OU Duration da carteira] `(Fonte, pag. X)` |
| **Vencimentos proximos?** | [Contratos proximos do vencimento? Qual a %?] `(Fonte, pag. X)` |
| **Indexador do fundo (Papel)** | [% CDI e % IPCA] `(Fonte, pag. X)` |
| **Taxa media dos creditos (Papel)** | [CDI+X%, IPCA+X%] `(Fonte, pag. X)` |
| **Segmentos dos inquilinos/devedores** | [Resposta] `(Fonte, pag. X)` |
| **Maior setor alocado** | [% da carteira no maior setor] `(Fonte, pag. X)` |
| **Concentracao de Inquilinos/Devedores** | [Qual e %] `(Fonte, pag. X)` |
| **Situacao financeira** | [Situacao financeira desse inquilino/devedor] `(Fonte, pag. X)` |
| **Periodo de carencia / LTV medio** | [Carencia (Tijolo) ou LTV medio (Papel)] `(Fonte, pag. X)` |
| **Classificacao do Risco (Papel)** | [High Yield / Middle Grade / High Grade] `(Fonte, pag. X)` |

---

### 4. Resultados e Distribuicoes
| Metrica | Analise / Dados Extraidos |
| :--- | :--- |
| **Resultado vs Mes Anterior** | [Superior/inferior] `(Fonte, pag. X)` |
| **Motivo da variacao** | [Por que foi maior/menor?] `(Fonte, pag. X)` |
| **Resultado vs Distribuicao** | [Por cota foi maior, menor ou igual?] `(Fonte, pag. X)` |
| **Padrao de distribuicao** | [Queda, constante, crescente] `(Fonte, pag. X)` |
| **Distribuicao aumentando?** | [Resposta] `(Fonte, pag. X)` |
| **Saldo acumulado / Queima** | [Saldo acumulado, esta consumindo? Quanto duraria?] `(Fonte, pag. X)` |
| **FFO vs DY** | [Valor do FFO vs DY. FFO abaixo gerou receita extra?] `(Fonte, pag. X)` |

---

### 5. Eventos Relevantes e Riscos a Monitorar
* **Comunicados Importantes:** [Aquisicoes, vendas, problemas com inquilinos]
* **Risco do Fundo:** [Baixo/Medio/Alto] - [Elencar os riscos encontrados]
* **Pontos de Atencao:** [O que monitorar]

---

### CONCLUSAO GERAL
[Como foi o resultado do fundo? Pontos positivos e negativos. Fundo esta queimando caixa? Por que?
O saldo acumulado sustentara a distribuicao? Fundo esta descontado? Expectativa para os proximos
resultados focando na seguranca das taxas, devedores e risco de spread/calote.]

---
Lembre-se: NENHUMA linha da tabela deve ficar sem a fonte referenciada.
"""


def extract_text_from_pdf(file_bytes: bytes, doc_name: str = "Documento") -> str:
    """Extrai texto de um PDF usando PyMuPDF com marcacao de pagina."""
    try:
        import pymupdf as fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages_text.append(f"\n--- [{doc_name} | Pagina {i}] ---\n{text}")
        doc.close()
        return "\n".join(pages_text)
    except Exception as e:
        return f"[ERRO ao extrair texto de '{doc_name}': {e}]"


def extract_text_from_xml(file_bytes: bytes, doc_name: str = "Informe_Mensal_Estruturado.xml") -> str:
    """Extrai texto de arquivo XML (como Informe Mensal Estruturado - IME da CVM/B3)."""
    encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
    content = ""
    for enc in encodings:
        try:
            content = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not content:
        content = file_bytes.decode("utf-8", errors="replace")

    return f"\n--- [{doc_name} | Documento XML / Informe Mensal Estruturado] ---\n{content.strip()}"


def extract_text_from_file(file_bytes: bytes, file_name: str) -> str:
    """Extrai texto de acordo com o tipo de arquivo (.pdf, .xml, .txt)."""
    lower = file_name.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes, doc_name=file_name)
    elif lower.endswith(".xml"):
        return extract_text_from_xml(file_bytes, doc_name=file_name)
    else:
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                content = file_bytes.decode(enc)
                return f"\n--- [{file_name}] ---\n{content.strip()}"
            except UnicodeDecodeError:
                continue
        return f"\n--- [{file_name}] ---\n{file_bytes.decode('utf-8', errors='replace').strip()}"


def get_file_hash(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


def build_user_prompt(documents: list) -> str:
    doc_count = len(documents)
    parts = [
        f"Analise os {doc_count} documento(s) abaixo e preencha o template de analise de FII seguindo "
        f"ESTRITAMENTE o formato e as instrucoes definidas no seu sistema prompt.\n\n"
        f"IMPORTANTE:\n"
        f"- Para cada metrica na tabela, cite o nome do documento e a pagina (ou tag/campo se for arquivo XML) "
        f"de onde a informacao foi extraida (ex: `(Relatorio Gerencial, pag. 4)` ou `(Informe Mensal Estruturado XML, tag <AtivoTotal>)`).\n\n"
        + "=" * 70 + "\n"
    ]
    for i, doc in enumerate(documents, start=1):
        parts.append(
            f"\n[DOCUMENTO {i} de {doc_count}: {doc['name']}]\n"
            + "=" * 70 + "\n" + doc['text'] + "\n" + "=" * 70 + "\n"
        )
    parts.append("\nCom base nos documentos acima, produza a analise completa agora:")
    return "\n".join(parts)


def call_gemini(user_prompt: str, api_key: str, model: str = "gemini-3.8-flash") -> str:
    """Chama a API do Google Gemini para analise do documento com fallback automatico."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    candidate_models = [model, "gemini-2.5-flash", "gemini-2.5-pro", "gemini-flash-latest"]
    unique_models = []
    for m in candidate_models:
        if m not in unique_models:
            unique_models.append(m)

    last_error = None
    for target_model in unique_models:
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SKILL_SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=8192,
                ),
            )
            return response.text
        except Exception as e:
            last_error = e
            if "404" in str(e) or "NOT_FOUND" in str(e):
                continue
            raise RuntimeError(f"Erro ao chamar a API Gemini: {e}")

    raise RuntimeError(f"Erro ao chamar a API Gemini em todos os modelos testados: {last_error}")


def analyze_documents(uploaded_files: list, api_key: str, cache_dir: Optional[str] = None) -> tuple:
    """
    Pipeline completo: extrai texto dos documentos (.pdf, .xml) e retorna a analise da IA.
    uploaded_files: lista de UploadedFile (Streamlit) ou dicts com 'name' e 'bytes'.
    """
    if not uploaded_files:
        raise ValueError("Nenhum arquivo enviado para analise.")
    if not api_key or api_key.strip() == "":
        raise ValueError("Chave da API Gemini nao configurada.")

    documents = []
    all_bytes = b""

    for f in uploaded_files:
        if hasattr(f, "read"):
            file_bytes = f.read()
            file_name = f.name
        elif isinstance(f, dict):
            file_bytes = f["bytes"]
            file_name = f["name"]
        else:
            raise TypeError(f"Tipo de arquivo nao suportado: {type(f)}")

        text = extract_text_from_file(file_bytes, file_name=file_name)
        documents.append({"name": file_name, "text": text})
        all_bytes += file_bytes

    cache_key = get_file_hash(all_bytes)
    if cache_dir:
        cache_path = Path(cache_dir) / f"{cache_key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return cached["result"], cached["metadata"]

    user_prompt = build_user_prompt(documents)
    result = call_gemini(user_prompt, api_key)

    metadata = {
        "cache_key": cache_key,
        "doc_count": len(documents),
        "doc_names": [d["name"] for d in documents],
        "model": "gemini-3.8-flash",
        "total_chars_sent": len(user_prompt),
    }

    if cache_dir:
        cache_path = Path(cache_dir) / f"{cache_key}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"result": result, "metadata": metadata}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    return result, metadata


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Teste de viabilidade Ã¯Â¿Â½ Analise de FII por IA")
    parser.add_argument("--pdf", required=True, help="Caminho para o PDF do relatorio gerencial")
    parser.add_argument("--key", default=os.getenv("GEMINI_API_KEY", ""), help="Chave da API Gemini")
    parser.add_argument("--output", default=None, help="Caminho para salvar o resultado em .md")
    args = parser.parse_args()

    if not args.key:
        print("ERRO: Chave da API nao fornecida. Use --key ou defina GEMINI_API_KEY no .env")
        exit(1)

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERRO: Arquivo nao encontrado: {pdf_path}")
        exit(1)

    print(f"Lendo arquivo: {pdf_path.name}")
    file_bytes = pdf_path.read_bytes()

    print("Enviando para analise do Gemini...")
    try:
        result, metadata = analyze_documents(
            uploaded_files=[{"name": pdf_path.name, "bytes": file_bytes}],
            api_key=args.key,
            cache_dir=".ai_cache",
        )
        print("\n" + "=" * 70)
        print("ANALISE CONCLUIDA")
        print(f"  Documentos processados: {metadata['doc_count']}")
        print(f"  Caracteres enviados: {metadata['total_chars_sent']:,}")
        print("=" * 70 + "\n")
        print(result)

        if args.output:
            output_path = Path(args.output)
            output_path.write_text(result, encoding="utf-8")
            print(f"\nAnalise salva em: {output_path}")

    except Exception as e:
        print(f"Erro durante a analise: {e}")
        exit(1)
