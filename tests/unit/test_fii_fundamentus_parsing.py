"""
A leitura da tabela do Fundamentus, coluna por coluna.

A tabela tem catorze colunas e o parser lia cinco. Duas consequências: quatro
indicadores que o score de FII precisa eram descartados a cada atualização, e
a coluna 6 — "Valor de Mercado" — era gravada como `patrimonio`, então a tela
mostrava capitalização de mercado sob o rótulo de patrimônio do fundo.
"""

from unittest.mock import MagicMock, patch

from services.fii_services import get_all_fiis_from_fundamentus

# Uma linha real de ABCP11, com as catorze colunas na ordem publicada:
# Papel, Segmento, Cotação, FFO Yield, Dividend Yield, P/VP, Valor de Mercado,
# Liquidez, Qtd de imóveis, Preço do m2, Aluguel por m2, Cap Rate, Vacância,
# Endereço.
_LINHA_ABCP11 = (
    "<tr>"
    "<td><a>ABCP11</a></td><td>Shoppings</td><td>80,00</td><td>8,95%</td>"
    "<td>8,87%</td><td>0,72</td><td>376.727.000</td><td>42.644</td><td>1</td>"
    "<td>5.259,39</td><td>593,72</td><td>11,29%</td><td>2,69%</td>"
    "<td>Avenida Industrial, 600</td>"
    "</tr>"
)


def _html(linhas):
    return f"<table><thead></thead><tbody>{linhas}</tbody></table>"


def _resposta(linhas):
    response = MagicMock()
    response.status_code = 200
    response.text = _html(linhas)
    return response


def _coletar(linhas=_LINHA_ABCP11):
    with patch("services.fii_services.requests.get", return_value=_resposta(linhas)):
        return get_all_fiis_from_fundamentus()["list"]


def test_patrimonio_nao_e_valor_de_mercado():
    # O fundo vale R$ 376,7 milhões em bolsa a 0,72× o patrimonial, então o
    # patrimônio é R$ 523 milhões. Gravar os R$ 376,7 milhões como patrimônio
    # errava por 28% — exatamente o desconto que se queria medir.
    fundo = _coletar()[0]

    assert fundo["patrimonio"] == round(376_727_000 / 0.72, 2)
    assert fundo["patrimonio"] > 523_000_000


def test_os_indicadores_de_imovel_sao_lidos():
    fundo = _coletar()[0]

    assert fundo["ffo_yield"] == 8.95
    assert fundo["qtd_imoveis"] == 1
    assert fundo["cap_rate"] == 11.29
    assert fundo["vacancia_media"] == 2.69


def test_os_indicadores_ja_lidos_continuam_corretos():
    fundo = _coletar()[0]

    assert fundo["price"] == 80.0
    assert fundo["dy"] == 8.87
    assert fundo["p_vp"] == 0.72
    assert fundo["liquidezmediadiaria"] == 42644.0
    assert fundo["segment"] == "Shoppings"


def test_valor_patrimonial_da_cota_sai_do_preco_e_do_p_vp():
    fundo = _coletar()[0]
    assert fundo["valorpatrimonialcota"] == round(80.0 / 0.72, 2)


def test_p_vp_zero_nao_divide_por_zero():
    # Fundo recém-listado aparece com P/VP em branco; a coleta inteira não
    # pode morrer por causa de uma linha.
    linha = _LINHA_ABCP11.replace("<td>0,72</td>", "<td>0,00</td>")
    fundo = _coletar(linha)[0]

    assert fundo["patrimonio"] == 0.0
    assert fundo["valorpatrimonialcota"] == 0.0


def test_linha_que_nao_e_ticker_de_fii_e_ignorada():
    linha = _LINHA_ABCP11.replace("<a>ABCP11</a>", "<a>PETR4</a>")
    assert _coletar(linha) == []
