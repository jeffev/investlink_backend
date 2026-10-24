"""
Coleta de ações no Fundamentus.

Por que existe:
    A rotina diária foi ligada e, na primeira execução, o StatusInvest
    devolveu **403**. A coleta de ações estava parada — e como nada rodava
    sozinho até então, ninguém tinha percebido: a tabela de ações mostrava o
    fechamento de um mês atrás com cara de preço de hoje.

    O Fundamentus já era a fonte primária de FII e publica a mesma tabela para
    ações: 995 papéis com P/L, P/VP, margens, ROE, ROIC, liquidez de dois
    meses e crescimento de receita. O StatusInvest fica como alternativa, do
    mesmo jeito que já acontece do lado dos fundos.

O que esta fonte **não** traz, e por que não é problema:
    Setor, subsetor e nome da empresa. A atualização só escreve as chaves que
    recebe, então quem já está na base mantém o que tinha. Papel estreando
    entra sem setor e cai no balde "MERCADO" do score — que é exatamente o
    tratamento que o score já dá a setor pequeno demais para ter mediana.

    LPA, VPA, dívida líquida/EBIT e margens auditadas vêm da CVM depois, em
    `enrich_with_cvm`, e sobrescrevem o que vier daqui.
"""

import logging
import re

import requests

from services.br_numbers import parse_br_float

URL = "https://www.fundamentus.com.br/resultado.php"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 60

# Posição da coluna na tabela publicada -> campo do model.
# "Liq.2meses" é o volume médio negociado em dois meses, que é justamente a
# métrica do guard rail de liquidez do score.
COLUNAS = {
    0: "ticker",
    1: "price",
    2: "p_l",
    3: "p_vp",
    4: "p_sr",
    5: "dy",
    6: "p_ativo",
    7: "p_capitalgiro",
    8: "p_ebit",
    9: "p_ativocirculante",
    10: "ev_ebit",
    12: "margembruta",
    13: "margemebit",
    14: "margemliquida",
    15: "liquidezcorrente",
    16: "roic",
    17: "roe",
    18: "liquidezmediadiaria",
    20: "dividaliquidapatrimonioliquido",
    21: "receitas_cagr5",
}

MIN_COLUNAS = 22
# A raiz do ticker tem quatro caracteres alfanuméricos, não quatro letras:
# B3SA3 é a própria bolsa. Exigir letra aqui descartou a B3 da coleta e a
# rotina de deslistagem a marcou como fora do pregão — o mesmo erro que já
# tinha acontecido na ponte de tickers da CVM. O sufixo opcional cobre papéis
# como ENMA3B.
_TICKER = re.compile(r"^[A-Z0-9]{4}\d{1,2}[A-Z]?$")


def _linhas_da_tabela(html):
    inicio = html.find("<tbody>")
    fim = html.find("</tbody>")
    if inicio == -1 or fim == -1:
        raise ValueError("tbody não encontrado na página do Fundamentus")
    return re.findall(r"<tr[^>]*>(.*?)</tr>", html[inicio:fim], re.DOTALL)


def _celulas(linha):
    return [
        re.sub(r"<[^>]+>", "", celula).strip()
        for celula in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.DOTALL)
    ]


def parse_stocks_table(html):
    """Converte o HTML publicado na lista de dicionários que o update espera."""
    acoes = []
    for linha in _linhas_da_tabela(html):
        celulas = _celulas(linha)
        if len(celulas) < MIN_COLUNAS:
            continue

        ticker = celulas[0].strip().upper()
        if not _TICKER.match(ticker):
            continue

        acao = {"ticker": ticker}
        for indice, campo in COLUNAS.items():
            if campo == "ticker":
                continue
            acao[campo] = parse_br_float(celulas[indice])

        # Papel sem cotação é papel que não negocia; entra na base e o guard
        # rail de liquidez cuida do resto.
        acoes.append(acao)

    return acoes


def get_all_stocks_from_fundamentus():
    """{"list": [...]} no mesmo formato da fonte antiga, ou None se falhar."""
    try:
        resposta = requests.get(URL, headers=HEADERS, timeout=TIMEOUT)
        if resposta.status_code != 200:
            logging.error(f"Fundamentus HTTP error: {resposta.status_code}")
            return None

        acoes = parse_stocks_table(resposta.text)
        if not acoes:
            logging.error("Fundamentus: nenhuma ação reconhecida na tabela")
            return None

        logging.info(f"Fundamentus: {len(acoes)} ações coletadas")
        return {"list": acoes}
    except Exception as error:
        logging.error(f"Erro ao buscar ações do Fundamentus: {error}")
        return None
