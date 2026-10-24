"""
A coleta de ações no Fundamentus.

A fonte antiga passou a devolver 403 e isso só apareceu quando a rotina
automática rodou pela primeira vez — até então a atualização dependia de
alguém clicar num botão, e a tabela de ações mostrava o fechamento de semanas
atrás com cara de preço de hoje.
"""

from unittest.mock import MagicMock, patch

from services.fundamentus_stocks import (
    get_all_stocks_from_fundamentus,
    parse_stocks_table,
)

# Uma linha real, com as 22 colunas na ordem publicada.
_LINHA = (
    "<tr>"
    "<td><a>PETR4</a></td><td>58,68</td><td>8,15</td><td>1,32</td><td>0,940</td>"
    "<td>7,44%</td><td>0,430</td><td>5,21</td><td>4,30</td><td>-2,40</td>"
    "<td>5,30</td><td>3,10</td><td>48,36%</td><td>29,17%</td><td>15,65%</td>"
    "<td>0,82</td><td>17,28%</td><td>20,91%</td><td>1.284.560.000,00</td>"
    "<td>367.512.000.000,00</td><td>0,65</td><td>12,83%</td>"
    "</tr>"
)


def _html(linhas):
    return f"<table><thead></thead><tbody>{linhas}</tbody></table>"


def test_le_os_indicadores_que_o_score_usa():
    acao = parse_stocks_table(_html(_LINHA))[0]

    assert acao["ticker"] == "PETR4"
    assert acao["price"] == 58.68
    assert acao["p_l"] == 8.15
    assert acao["p_vp"] == 1.32
    assert acao["dy"] == 7.44
    assert acao["roe"] == 20.91
    assert acao["roic"] == 17.28


def test_le_a_liquidez_que_e_o_guard_rail():
    # "Liq.2meses" é o volume médio negociado, exatamente a métrica que o
    # score usa para não recomendar papel que ninguém consegue vender.
    acao = parse_stocks_table(_html(_LINHA))[0]
    assert acao["liquidezmediadiaria"] == 1_284_560_000.00


def test_o_ticker_com_digito_na_raiz_e_aceito():
    # B3SA3 é a própria bolsa. Exigir quatro letras na raiz descartou a B3 da
    # coleta e a rotina de deslistagem a marcou como fora do pregão.
    linha = _LINHA.replace("<a>PETR4</a>", "<a>B3SA3</a>")
    assert parse_stocks_table(_html(linha))[0]["ticker"] == "B3SA3"


def test_o_ticker_com_sufixo_de_letra_e_aceito():
    linha = _LINHA.replace("<a>PETR4</a>", "<a>ENMA3B</a>")
    assert parse_stocks_table(_html(linha))[0]["ticker"] == "ENMA3B"


def test_linha_que_nao_e_ticker_e_ignorada():
    linha = _LINHA.replace("<a>PETR4</a>", "<a>TOTAL</a>")
    assert parse_stocks_table(_html(linha)) == []


def test_linha_curta_demais_e_ignorada():
    assert parse_stocks_table(_html("<tr><td>PETR4</td><td>58,68</td></tr>")) == []


def test_valor_vazio_vira_zero_e_nao_derruba_a_linha():
    # A fonte publica ausência como campo vazio; o score já trata zero como
    # "sem dado".
    linha = _LINHA.replace("<td>8,15</td>", "<td>-</td>")
    acao = parse_stocks_table(_html(linha))[0]

    assert acao["p_l"] == 0.0
    assert acao["ticker"] == "PETR4"


def test_resposta_fora_do_ar_devolve_none():
    resposta = MagicMock(status_code=403, text="")
    with patch("services.fundamentus_stocks.requests.get", return_value=resposta):
        assert get_all_stocks_from_fundamentus() is None


def test_tabela_sem_nenhuma_acao_devolve_none():
    # Melhor devolver nada do que uma lista vazia: lista vazia faria a
    # deslistagem achar que o pregão inteiro fechou.
    resposta = MagicMock(status_code=200, text=_html(""))
    with patch("services.fundamentus_stocks.requests.get", return_value=resposta):
        assert get_all_stocks_from_fundamentus() is None


def test_coleta_bem_sucedida_tem_o_formato_que_o_update_espera():
    resposta = MagicMock(status_code=200, text=_html(_LINHA))
    with patch("services.fundamentus_stocks.requests.get", return_value=resposta):
        dados = get_all_stocks_from_fundamentus()

    assert list(dados) == ["list"]
    assert dados["list"][0]["ticker"] == "PETR4"
