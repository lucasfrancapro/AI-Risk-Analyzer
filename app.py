import streamlit as st
from google import genai
from datetime import datetime
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
import re


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="AI Political Risk Analyzer",
    page_icon="🌎",
    layout="wide",
)


# ============================================================
# CONFIGURAÇÃO DO GEMINI
# ============================================================

MODEL = "gemini-3.5-flash-lite"


def obter_cliente_gemini():
    """Retorna o cliente Gemini ou None quando a chave não está disponível."""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        api_key = None

    if not api_key:
        return None

    return genai.Client(api_key=api_key)


CLIENTE_GEMINI = obter_cliente_gemini()


# ============================================================
# ESTADO DA APLICAÇÃO
# ============================================================

MODO_ATUAL = "🌎 Situação atual de um país"
MODO_PREDEFINIDO = "📊 Cenário político pré-definido"

if "modo" not in st.session_state:
    st.session_state.modo = MODO_ATUAL

if "erro_api" not in st.session_state:
    st.session_state.erro_api = None


# ============================================================
# CENÁRIOS PRÉ-DEFINIDOS
# ============================================================

CENARIOS = {
    "Mudança na política tributária": {
        "categoria": "Política econômica",
        "risco": "Aumento da carga tributária",
        "probabilidade": 4,
        "impacto": 4,
    },
    "Eleição e mudança de governo": {
        "categoria": "Política",
        "risco": "Mudança de políticas governamentais",
        "probabilidade": 4,
        "impacto": 4,
    },
    "Instabilidade política": {
        "categoria": "Política",
        "risco": "Instabilidade institucional",
        "probabilidade": 3,
        "impacto": 5,
    },
    "Mudança na política comercial": {
        "categoria": "Comércio internacional",
        "risco": "Alteração de tarifas e barreiras comerciais",
        "probabilidade": 3,
        "impacto": 4,
    },
    "Sanções internacionais": {
        "categoria": "Geopolítica",
        "risco": "Aplicação de sanções econômicas",
        "probabilidade": 2,
        "impacto": 5,
    },
    "Crise diplomática": {
        "categoria": "Geopolítica",
        "risco": "Deterioração das relações diplomáticas",
        "probabilidade": 3,
        "impacto": 4,
    },
    "Mudança regulatória": {
        "categoria": "Regulação",
        "risco": "Alteração das regras para empresas",
        "probabilidade": 4,
        "impacto": 3,
    },
    "Conflito internacional": {
        "categoria": "Geopolítica",
        "risco": "Conflito militar ou escalada regional",
        "probabilidade": 2,
        "impacto": 5,
    },
    "Intervenção estatal": {
        "categoria": "Política econômica",
        "risco": "Aumento da intervenção governamental",
        "probabilidade": 3,
        "impacto": 4,
    },
    "Mudança na política econômica": {
        "categoria": "Economia",
        "risco": "Mudança na orientação econômica do governo",
        "probabilidade": 4,
        "impacto": 4,
    },
}


# ============================================================
# CLASSIFICAÇÃO DO RISCO
# ============================================================

def classificar_risco(score):
    if score <= 4:
        return "BAIXO"
    if score <= 9:
        return "MODERADO"
    if score <= 14:
        return "ALTO"
    if score <= 19:
        return "MUITO ALTO"
    return "CRÍTICO"


# ============================================================
# BUSCA DE NOTÍCIAS
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def buscar_noticias(pais, setor):
    query = (
        f'"{pais}" '
        f'(política OR governo OR economia OR geopolítica OR '
        f'regulamentação OR comércio) '
        f'"{setor}"'
    )

    url = (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}"
        "&hl=pt-BR"
        "&gl=BR"
        "&ceid=BR:pt-419"
    )

    try:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"
                )
            },
        )

        with urlopen(request, timeout=10) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)

        noticias = []
        titulos = set()

        for item in root.findall(".//item"):
            titulo_element = item.find("title")
            link_element = item.find("link")
            descricao_element = item.find("description")
            data_element = item.find("pubDate")
            fonte_element = item.find("source")

            titulo = (
                titulo_element.text.strip()
                if titulo_element is not None and titulo_element.text
                else ""
            )
            link = (
                link_element.text.strip()
                if link_element is not None and link_element.text
                else ""
            )
            descricao = (
                descricao_element.text.strip()
                if descricao_element is not None and descricao_element.text
                else ""
            )
            data_publicacao = (
                data_element.text.strip()
                if data_element is not None and data_element.text
                else ""
            )
            fonte = (
                fonte_element.text.strip()
                if fonte_element is not None and fonte_element.text
                else ""
            )

            if not titulo or titulo in titulos:
                continue

            titulos.add(titulo)

            noticias.append(
                {
                    "titulo": titulo,
                    "link": link,
                    "descricao": descricao,
                    "data": data_publicacao,
                    "fonte": fonte,
                }
            )

            if len(noticias) >= 10:
                break

        return noticias

    except Exception as erro:
        return [{"erro": str(erro)}]


# ============================================================
# PREPARAR NOTÍCIAS PARA A IA
# ============================================================

def preparar_noticias_para_ia(noticias):
    partes = []

    for i, noticia in enumerate(noticias, start=1):
        if "erro" in noticia:
            continue

        partes.append(
            f"""
NOTÍCIA {i}

Título:
{noticia.get("titulo", "")}

Fonte:
{noticia.get("fonte", "")}

Data:
{noticia.get("data", "")}

Resumo:
{noticia.get("descricao", "")}
""".strip()
        )

    return "\n\n".join(partes) if partes else "Nenhuma notícia disponível."


# ============================================================
# ANÁLISE DA SITUAÇÃO ATUAL
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def analisar_pais(pais, setor, noticias_texto):
    if CLIENTE_GEMINI is None:
        raise RuntimeError("GEMINI_API_KEY não configurada no Streamlit Cloud.")

    prompt = f"""
Você é um analista especializado em RISCO POLÍTICO,
RELAÇÕES INTERNACIONAIS e IMPACTO EMPRESARIAL.

Analise a situação política atual de:

PAÍS:
{pais}

SETOR EMPRESARIAL:
{setor}

As notícias abaixo foram coletadas externamente pelo sistema.

REGRAS IMPORTANTES:
- Use SOMENTE as notícias fornecidas abaixo como base factual.
- Não invente acontecimentos, números ou fatos.
- Não utilize informações externas que não estejam nas notícias.
- Diferencie fatos de interpretações.
- Considere os impactos para empresas do setor informado.
- A análise deve ser objetiva e adequada para um trabalho acadêmico.
- Não atribua o score final do risco. O sistema Python fará esse cálculo.

NOTÍCIAS:
{noticias_texto}

Produza a resposta exatamente seguindo esta estrutura:

# SITUAÇÃO POLÍTICA ATUAL

Explique de forma objetiva o contexto político atual do país com base nas notícias.

# PRINCIPAIS ACONTECIMENTOS

Apresente os principais acontecimentos políticos, econômicos,
regulatórios ou geopolíticos identificados.

# PRINCIPAIS RISCOS POLÍTICOS

Identifique de 2 a 4 riscos políticos relevantes para empresas.

Para CADA risco, utilize exatamente este formato:

RISCO: nome do risco
PROBABILIDADE: número inteiro de 1 a 5
IMPACTO: número inteiro de 1 a 5
EXPLICAÇÃO: explique por que esse risco existe e como ele pode afetar empresas.

IMPORTANTE:
- PROBABILIDADE deve ser somente um número inteiro entre 1 e 5.
- IMPACTO deve ser somente um número inteiro entre 1 e 5.
- Não escreva o score.

# IMPACTOS PARA EMPRESAS

Explique os possíveis impactos para empresas do setor {setor}.

Considere, quando aplicável:
- custos;
- investimentos;
- comércio;
- cadeia de suprimentos;
- regulamentação;
- demanda;
- operações;
- riscos financeiros.

# INDICADORES PARA MONITORAMENTO

Liste indicadores que uma empresa deveria acompanhar para identificar
mudanças nesse cenário político.

# MEDIDAS PREVENTIVAS

Apresente medidas que empresas poderiam adotar para reduzir sua exposição
aos riscos identificados.

# CONCLUSÃO

Apresente uma conclusão objetiva sobre o nível de risco político
e suas possíveis consequências para empresas.
"""

    resposta = CLIENTE_GEMINI.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    if not resposta.text:
        raise RuntimeError("A API não retornou conteúdo.")

    return resposta.text


# ============================================================
# ANÁLISE DE CENÁRIO PRÉ-DEFINIDO
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def analisar_cenario(cenario):
    if CLIENTE_GEMINI is None:
        raise RuntimeError("GEMINI_API_KEY não configurada no Streamlit Cloud.")

    prompt = f"""
Você é um analista especializado em risco político,
relações internacionais e ambiente empresarial.

Analise o seguinte cenário político:

{cenario}

Produza uma análise acadêmica e objetiva.

Estruture sua resposta nos seguintes tópicos:

# CONTEXTO DO CENÁRIO

Explique o que significa esse cenário político.

# PRINCIPAIS RISCOS

Explique os principais riscos políticos associados ao cenário.

# IMPACTOS PARA EMPRESAS

Explique como empresas podem ser afetadas.

Considere:
- custos;
- investimentos;
- comércio;
- cadeia de suprimentos;
- regulamentação;
- operações;
- demanda;
- riscos financeiros.

# INDICADORES PARA MONITORAMENTO

Liste indicadores que empresas deveriam acompanhar.

# MEDIDAS PREVENTIVAS

Apresente medidas que empresas poderiam adotar para reduzir
os impactos desse cenário.

# CONCLUSÃO

Apresente uma conclusão objetiva sobre o cenário.
"""

    resposta = CLIENTE_GEMINI.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    if not resposta.text:
        raise RuntimeError("A API não retornou conteúdo.")

    return resposta.text


# ============================================================
# EXTRAIR RISCOS DA ANÁLISE
# ============================================================

def extrair_riscos(texto):
    padrao = re.compile(
        r"RISCO:\s*(.*?)\s*"
        r"PROBABILIDADE:\s*(\d+)\s*"
        r"IMPACTO:\s*(\d+)\s*"
        r"EXPLICAÇÃO:\s*(.*?)(?=\nRISCO:|\n#|$)",
        re.DOTALL | re.IGNORECASE,
    )

    riscos = []

    for risco, probabilidade, impacto, explicacao in padrao.findall(texto):
        try:
            probabilidade = int(probabilidade)
            impacto = int(impacto)
        except ValueError:
            continue

        if not 1 <= probabilidade <= 5:
            continue

        if not 1 <= impacto <= 5:
            continue

        score = probabilidade * impacto

        riscos.append(
            {
                "risco": risco.strip(),
                "probabilidade": probabilidade,
                "impacto": impacto,
                "score": score,
                "classificacao": classificar_risco(score),
                "explicacao": explicacao.strip(),
            }
        )

    return riscos


# ============================================================
# TRATAMENTO DE ERRO
# ============================================================

def obter_mensagem_erro_api(erro):
    mensagem = str(erro)
    mensagem_lower = mensagem.lower()

    if "429" in mensagem or "resource_exhausted" in mensagem_lower:
        return "O limite de utilização da API do Gemini foi atingido (erro 429)."

    if "403" in mensagem or "permission_denied" in mensagem_lower:
        return "A API do Gemini recusou o acesso à chave/API (erro 403)."

    if "404" in mensagem or "not_found" in mensagem_lower:
        return "O modelo solicitado não está disponível (erro 404)."

    if "500" in mensagem:
        return "O serviço do Gemini apresentou um erro interno (erro 500)."

    if "503" in mensagem or "unavailable" in mensagem_lower:
        return "O serviço do Gemini está temporariamente indisponível (erro 503)."

    if "504" in mensagem or "deadline_exceeded" in mensagem_lower:
        return "A API do Gemini demorou mais do que o permitido (erro 504)."

    if "GEMINI_API_KEY" in mensagem:
        return "A chave GEMINI_API_KEY não está configurada no Streamlit Cloud."

    return "Não foi possível realizar a análise com a inteligência artificial."


# ============================================================
# FUNÇÃO DE FALLBACK
# ============================================================

def ativar_fallback(mensagem):
    """
    Altera somente o estado da aplicação.
    O radio não é alterado diretamente.
    O rerun cria o widget novamente com o índice correto.
    """
    st.session_state.erro_api = mensagem
    st.session_state.modo = MODO_PREDEFINIDO
    st.rerun()


# ============================================================
# LOGO E CABEÇALHO
# ============================================================

try:
    st.image("logo.png", width=280)
except Exception:
    pass

st.title("🌎 AI Political Risk Analyzer")

st.subheader(
    "Análise de Cenários Políticos e seus Impactos sobre Empresas"
)

st.caption("Faculdades Integradas Rio Branco – Granja Vianna")
st.caption(
    "Projeto acadêmico de análise de risco político utilizando inteligência artificial."
)


# ============================================================
# AVISO DE FALLBACK
# ============================================================

if st.session_state.erro_api:
    st.warning(
        "⚠️ A análise com inteligência artificial não está disponível "
        "no momento. O sistema foi direcionado automaticamente para "
        "os cenários políticos pré-definidos."
    )
    st.info(f"Motivo: {st.session_state.erro_api}")
    st.session_state.erro_api = None


# ============================================================
# SELEÇÃO DO MODO
# ============================================================

opcoes_modo = [MODO_ATUAL, MODO_PREDEFINIDO]

indice_modo = 0 if st.session_state.modo == MODO_ATUAL else 1

# IMPORTANTE:
# Não existe key="modo_radio".
# Também não alteramos o estado do radio depois que ele foi criado.
modo = st.radio(
    "Escolha o tipo de análise:",
    opcoes_modo,
    index=indice_modo,
    horizontal=True,
)

st.session_state.modo = modo


# ============================================================
# MODO 1 — SITUAÇÃO ATUAL
# ============================================================

if modo == MODO_ATUAL:

    st.markdown("## 🌎 Situação atual de um país")

    st.write(
        "Selecione um país e um setor para analisar notícias recentes "
        "e identificar possíveis riscos políticos para empresas."
    )

    paises = [
        "Brasil",
        "Estados Unidos",
        "Argentina",
        "China",
        "Alemanha",
        "França",
        "Reino Unido",
        "Rússia",
        "Índia",
        "Japão",
        "Canadá",
        "México",
        "Chile",
        "Colômbia",
        "Austrália",
        "Itália",
        "Espanha",
        "Coreia do Sul",
        "África do Sul",
        "Turquia",
        "Outro",
    ]

    setores = [
        "Indústria",
        "Comércio",
        "Tecnologia",
        "Serviços",
        "Financeiro",
        "Agronegócio",
        "Energia",
        "Logística",
        "Saúde",
        "Construção",
        "Mineração",
        "Automotivo",
        "Outro",
    ]

    col1, col2 = st.columns(2)

    with col1:
        pais = st.selectbox("🌎 País", paises)

    with col2:
        setor = st.selectbox("🏢 Setor empresarial", setores)

    st.divider()

    analisar = st.button(
        "🔍 ANALISAR SITUAÇÃO ATUAL",
        type="primary",
        use_container_width=True,
    )

    if analisar:

        with st.spinner("🔎 Buscando notícias recentes..."):
            noticias = buscar_noticias(pais, setor)

        if (
            not noticias
            or (len(noticias) == 1 and "erro" in noticias[0])
        ):
            st.error("Não foi possível obter notícias para essa pesquisa.")
        else:
            st.success(f"📰 {len(noticias)} notícias encontradas.")

            with st.expander(
                "📰 Notícias utilizadas na análise",
                expanded=False,
            ):
                for i, noticia in enumerate(noticias, start=1):
                    st.markdown(f"### {i}. {noticia['titulo']}")

                    if noticia.get("fonte"):
                        st.caption(f"Fonte: {noticia['fonte']}")

                    if noticia.get("data"):
                        st.caption(f"Data: {noticia['data']}")

                    if noticia.get("descricao"):
                        descricao = re.sub(
                            r"<.*?>",
                            "",
                            noticia["descricao"],
                        )
                        st.write(descricao)

                    if noticia.get("link"):
                        st.markdown(
                            f"[🔗 Ver notícia]({noticia['link']})"
                        )

                    st.divider()

            noticias_texto = preparar_noticias_para_ia(noticias)

            try:
                with st.spinner(
                    "🤖 Analisando riscos políticos com IA..."
                ):
                    analise = analisar_pais(
                        pais,
                        setor,
                        noticias_texto,
                    )

                st.success("✅ Análise concluída com sucesso.")

                st.markdown("---")
                st.markdown("## 🤖 Análise de Risco Político")
                st.markdown(analise)

                riscos = extrair_riscos(analise)

                if riscos:
                    st.markdown("---")
                    st.markdown("## 📊 Avaliação Quantitativa dos Riscos")

                    for risco in riscos:
                        st.markdown(f"### ⚠️ {risco['risco']}")

                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            st.metric(
                                "Probabilidade",
                                f"{risco['probabilidade']}/5",
                            )

                        with col2:
                            st.metric(
                                "Impacto",
                                f"{risco['impacto']}/5",
                            )

                        with col3:
                            st.metric(
                                "Score",
                                f"{risco['score']}/25",
                            )

                        with col4:
                            st.metric(
                                "Classificação",
                                risco["classificacao"],
                            )

                        st.info(risco["explicacao"])

                    maior_risco = max(
                        riscos,
                        key=lambda item: item["score"],
                    )

                    st.markdown("---")
                    st.markdown("## 🚨 Principal risco identificado")

                    st.error(
                        f"""
**{maior_risco['risco']}**

Score: **{maior_risco['score']}/25**

Classificação: **{maior_risco['classificacao']}**
"""
                    )
                else:
                    st.warning(
                        "A IA não retornou riscos em formato estruturado "
                        "suficiente para calcular o score automaticamente."
                    )

                st.markdown("---")
                st.markdown("## 🔗 Fontes utilizadas")

                for noticia in noticias:
                    if noticia.get("link"):
                        st.markdown(
                            f"- [{noticia['titulo']}]({noticia['link']})"
                        )

            except Exception as erro:
                mensagem = obter_mensagem_erro_api(erro)
                ativar_fallback(mensagem)


# ============================================================
# MODO 2 — CENÁRIOS PRÉ-DEFINIDOS
# ============================================================

else:

    st.markdown("## 📊 Cenário político pré-definido")

    st.write(
        "Escolha um cenário político para realizar uma análise "
        "sem depender da consulta de notícias em tempo real."
    )

    cenario_selecionado = st.selectbox(
        "Escolha o cenário:",
        list(CENARIOS.keys()),
    )

    dados = CENARIOS[cenario_selecionado]

    st.divider()

    st.markdown(f"### 📌 {cenario_selecionado}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Categoria", dados["categoria"])

    with col2:
        st.metric(
            "Probabilidade",
            f"{dados['probabilidade']}/5",
        )

    with col3:
        st.metric(
            "Impacto",
            f"{dados['impacto']}/5",
        )

    score = dados["probabilidade"] * dados["impacto"]
    classificacao = classificar_risco(score)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Score de risco", f"{score}/25")

    with col2:
        st.metric("Classificação", classificacao)

    st.info(f"**Risco principal:** {dados['risco']}")

    analisar_cenario_button = st.button(
        "🔍 ANALISAR CENÁRIO",
        type="primary",
        use_container_width=True,
    )

    if analisar_cenario_button:

        if CLIENTE_GEMINI is None:
            st.warning(
                "A IA não está disponível porque a GEMINI_API_KEY "
                "não está configurada."
            )
        else:
            try:
                with st.spinner("🤖 Gerando análise do cenário..."):
                    analise = analisar_cenario(cenario_selecionado)

                st.success("✅ Análise concluída.")

                st.markdown("---")
                st.markdown("## 🤖 Análise do Cenário")
                st.markdown(analise)

            except Exception as erro:
                mensagem = obter_mensagem_erro_api(erro)

                st.error(
                    "⚠️ A inteligência artificial não está disponível "
                    "neste momento."
                )

                st.warning(mensagem)

        # O cálculo quantitativo é local e continua funcionando
        # mesmo quando a IA está indisponível.
        st.markdown("---")
        st.markdown("## 📊 Avaliação Quantitativa")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Probabilidade",
                f"{dados['probabilidade']}/5",
            )

        with col2:
            st.metric(
                "Impacto",
                f"{dados['impacto']}/5",
            )

        with col3:
            st.metric(
                "Score",
                f"{score}/25",
            )

        with col4:
            st.metric(
                "Classificação",
                classificacao,
            )


# ============================================================
# RODAPÉ
# ============================================================

st.markdown("---")

st.caption(
    "AI Political Risk Analyzer • Projeto acadêmico • "
    "Faculdades Integradas Rio Branco"
)

st.caption(
    f"Última execução: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
)
