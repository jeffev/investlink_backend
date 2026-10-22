"""
O nome do fundo, que o Fundamentus não publica.

A fonte primária de FII devolve só o ticker, e a coleta preenchia
`companyname` com ele — o card mostrava "HGLG11" embaixo de "HGLG11". O nome
vem do Informe Mensal da CVM, em caixa alta e cercado de jargão jurídico.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.fii_services import enrich_fii_names, humanize_fund_name


@pytest.mark.parametrize(
    "publicado, esperado",
    [
        ("PÁTRIA LOG - FUNDO DE INVESTIMENTO IMOBILIÁRIO", "Pátria Log"),
        (
            "KINEA RENDA IMOBILIARIA FII RESPONSABILIDADE LIMITADA",
            "Kinea Renda Imobiliaria",
        ),
        ("FII MAXI RENDA RL", "Maxi Renda"),
        ("VIA PARQUE SHOPPING FII RESP LTDA", "Via Parque Shopping"),
        (
            "FUNDO DE INVESTIMENTO IMOBILIÁRIO VIA PARQUE SHOPPING",
            "Via Parque Shopping",
        ),
    ],
)
def test_o_jargao_juridico_sai_do_nome(publicado, esperado):
    assert humanize_fund_name(publicado) == esperado


@pytest.mark.parametrize(
    "publicado, esperado",
    [
        ("XP MALLS FII", "XP Malls"),
        ("CSHG LOGÍSTICA FII", "CSHG Logística"),
        ("VBI PRIME FII RL", "VBI Prime"),
        ("RBR CREDITO IMOB FII", "RBR Credito Imob"),
        ("BTG PACTUAL CORPORATE OFFICE FUND", "BTG Pactual Corporate Office Fund"),
    ],
)
def test_a_sigla_do_gestor_continua_em_caixa_alta(publicado, esperado):
    # `.title()` sozinho devolveria Xp, Cshg e Vbi — o nome do gestor vira
    # erro de digitação.
    assert humanize_fund_name(publicado) == esperado


def test_particula_pendurada_pelo_jargao_removido_e_descartada():
    # "BB PREMIUM MALLS FII DE RESPONSABILIDADE LIMITADA" perde o miolo e
    # sobrava com um "de" solto no fim.
    assert humanize_fund_name("BB PREMIUM MALLS FII DE RESPONSABILIDADE LIMITADA") == (
        "BB Premium Malls"
    )


def test_a_particula_fica_minuscula_no_meio_do_nome():
    assert humanize_fund_name("TORRE DE OFICINAS DA PAULISTA") == (
        "Torre de Oficinas da Paulista"
    )


def test_nome_que_e_so_jargao_nao_vira_nome():
    # Sobra vazio: melhor nenhum nome do que "Fundo De Investimento".
    assert humanize_fund_name("FUNDO DE INVESTIMENTO IMOBILIÁRIO") is None
    assert humanize_fund_name("") is None
    assert humanize_fund_name(None) is None


# ── Enriquecimento da coleta ─────────────────────────────────────────────────


def _enriquecer(fiis, linhas):
    with patch("services.fii_services.db") as mock_db:
        chain = MagicMock()
        chain.filter.return_value.order_by.return_value.all.return_value = linhas
        mock_db.session.query.return_value = chain
        enrich_fii_names(fiis)
    return fiis


def test_o_nome_da_cvm_substitui_o_ticker_repetido(app):
    with app.app_context():
        fiis = [{"ticker": "HGLG11", "companyname": "HGLG11"}]
        _enriquecer(fiis, [("HGLG11", "CSHG LOGÍSTICA FII")])

        assert fiis[0]["companyname"] == "CSHG Logística"


def test_o_informe_mais_recente_vence(app):
    # A consulta ordena por data crescente, então a última linha sobrescreve.
    with app.app_context():
        fiis = [{"ticker": "HGLG11", "companyname": "HGLG11"}]
        _enriquecer(
            fiis,
            [("HGLG11", "NOME ANTIGO FII"), ("HGLG11", "PÁTRIA LOG FII")],
        )

        assert fiis[0]["companyname"] == "Pátria Log"


def test_nome_vindo_da_fonte_nao_e_sobrescrito(app):
    # O StatusInvest, que é a fonte alternativa, publica nome de verdade.
    with app.app_context():
        fiis = [{"ticker": "HGLG11", "companyname": "CSHG Logística FII"}]
        _enriquecer(fiis, [("HGLG11", "OUTRO NOME FII")])

        assert fiis[0]["companyname"] == "CSHG Logística FII"


def test_sem_historico_o_ticker_permanece(app):
    with app.app_context():
        fiis = [{"ticker": "NOVO11", "companyname": "NOVO11"}]
        _enriquecer(fiis, [])

        assert fiis[0]["companyname"] == "NOVO11"


def test_falha_ao_ler_o_nome_nao_derruba_a_atualizacao(app):
    # Nome é enfeite; cotação não. A tabela do histórico pode nem existir num
    # servidor onde o pipeline ainda não rodou.
    from sqlalchemy.exc import SQLAlchemyError

    with app.app_context():
        fiis = [{"ticker": "HGLG11", "companyname": "HGLG11"}]
        with patch("services.fii_services.db") as mock_db:
            mock_db.session.query.side_effect = SQLAlchemyError(
                "relation does not exist"
            )
            enrich_fii_names(fiis)

        assert fiis[0]["companyname"] == "HGLG11"


def test_nao_consulta_quando_todos_ja_tem_nome(app):
    with app.app_context():
        fiis = [{"ticker": "HGLG11", "companyname": "CSHG Logística"}]
        with patch("services.fii_services.db") as mock_db:
            enrich_fii_names(fiis)
            mock_db.session.query.assert_not_called()
