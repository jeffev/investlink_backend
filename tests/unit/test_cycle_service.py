"""
"É hora?" — a pergunta que o score não respondia.

O score compara a empresa com as do setor. Com isso, a mesma ação no topo
histórico e 40% abaixo do pico recebia exatamente a mesma nota, sendo decisões
opostas.

A regra que estes testes fixam é a que separa a ideia certa da ingênua: queda
grande **sozinha** seleciona deterioração, não pechincha. Este projeto já
provou isso na prática — na primeira execução real do score de FII, o topo dos
três perfis eram os quatro fundos de crédito mais descontados da bolsa, que
eram os mais caídos *e* os mais quebrados.
"""

import pytest

from services.cycle_service import (
    CAINDO,
    CRESCENDO,
    DETERIORACAO,
    ESTAVEL,
    NEAR_PEAK,
    NEUTRO,
    OPORTUNIDADE,
    RELEVANT_DROP,
    TOPO,
    classify,
    describe,
)

# ── A classificação ──────────────────────────────────────────────────────────


def test_queda_com_lucro_crescendo_e_oportunidade():
    assert classify(-40.0, CRESCENDO, 0.8) == OPORTUNIDADE


def test_queda_com_lucro_estavel_tambem_e_oportunidade():
    # Lucro que não cresceu mas também não afundou continua sendo fundamento
    # de pé: o preço caiu sozinho.
    assert classify(-40.0, ESTAVEL, 1.0) == OPORTUNIDADE


def test_queda_com_lucro_caindo_e_armadilha():
    # É o caso que motivou a regra inteira.
    assert classify(-40.0, CAINDO, 0.5) == DETERIORACAO


def test_queda_sem_saber_do_lucro_nao_vira_oportunidade():
    # Sem o discriminador não dá para afirmar que o fundamento resistiu —
    # e anunciar oportunidade sem isso é exatamente o erro que se quer evitar.
    assert classify(-40.0, None, 0.8) == NEUTRO


def test_colado_no_topo_e_caro_para_si_mesmo_e_topo():
    assert classify(-1.0, CRESCENDO, 1.4) == TOPO


def test_na_maxima_e_topo_mesmo_sem_multiplo_historico():
    assert classify(0.0, CRESCENDO, None) == TOPO


def test_queda_pequena_e_neutra():
    assert classify(-12.0, CRESCENDO, 1.0) == NEUTRO


def test_sem_queda_medida_nao_ha_estado():
    # Inventar "neutro" diria que foi verificado quando não foi.
    assert classify(None, CRESCENDO, 0.9) is None


@pytest.mark.parametrize("queda", [RELEVANT_DROP, RELEVANT_DROP - 0.1])
def test_o_limiar_de_queda_relevante_inclui_a_propria_borda(queda):
    assert classify(queda, CRESCENDO, 1.0) == OPORTUNIDADE


@pytest.mark.parametrize("queda", [NEAR_PEAK, NEAR_PEAK + 0.1])
def test_o_limiar_de_topo_inclui_a_propria_borda(queda):
    assert classify(queda, CRESCENDO, 1.5) == TOPO


# ── A frase que vai para o card ──────────────────────────────────────────────


def test_a_frase_de_oportunidade_traz_a_queda_e_o_lucro():
    frase = describe(OPORTUNIDADE, -41.6, CRESCENDO)
    assert "42%" in frase
    assert "lucro segue crescendo" in frase


def test_a_frase_de_armadilha_diz_que_o_lucro_caiu_junto():
    frase = describe(DETERIORACAO, -32.4, CAINDO)
    assert "32%" in frase
    assert "lucro caiu junto" in frase


def test_a_frase_de_topo_avisa_que_e_compra_no_topo():
    assert "topo do próprio ciclo" in describe(TOPO, -1.0, CRESCENDO)


def test_estado_neutro_nao_vira_frase():
    # Card não precisa de uma linha para dizer que não há nada a dizer.
    assert describe(NEUTRO, -12.0, CRESCENDO) is None
