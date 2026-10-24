"""
A vitrine de FII: mesma rota da de ações, com `asset_type=FII`.

O que estes testes protegem é a separação entre os dois ativos. Um score de
fundo lido com os pesos de ação, ou um card de FII trazendo Graham e ROE, seria
um erro silencioso — a tela renderizaria campos vazios sem reclamar de nada.
"""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.opportunity_service import (
    get_stock_score,
    list_opportunities,
    list_profiles,
)


class _FiiScore:
    """Dublê com o mesmo contrato to_json do FiiScore."""

    def __init__(self, ticker, total, eligible=True):
        self.ticker = ticker
        self.profile = "EQUILIBRADO"
        self.run_date = datetime(2026, 9, 24)
        self.score_total = total
        self.eligible = eligible

    def to_json(self):
        return {
            "ticker": self.ticker,
            "profile": self.profile,
            "score_total": self.score_total,
            "eligible": self.eligible,
            "pillars": [{"key": "renda", "label": "Renda", "value": 82.0}],
            "reasons": [{"code": "DY_SAUDAVEL", "message": "Dividend Yield de 8,9%"}],
            "red_flags": [{"code": "AGIO", "message": "Cota a 1,10× o patrimonial"}],
            "exclusion_reasons": [],
        }


def _fii(ticker):
    return SimpleNamespace(
        ticker=ticker,
        companyname=f"Fundo {ticker}",
        segment="Logística",
        price=147.60,
        p_vp=0.89,
        dy=8.97,
        ffo_yield=7.55,
        cap_rate=9.16,
        vacancia_media=2.41,
        qtd_imoveis=37,
        liquidezmediadiaria=22_213_500.0,
        patrimonio=7_559_573_034.0,
        valorpatrimonialcota=165.84,
    )


def _run_list(scores, fiis, profile=None, limit=12, asset_type="FII"):
    with (
        patch("services.opportunity_service.FiiScore.query") as mock_scores,
        patch("services.opportunity_service.Fii.query") as mock_fiis,
        patch("services.opportunity_service.get_score_deltas", return_value={}),
    ):
        chain = MagicMock()
        chain.order_by.return_value.limit.return_value.all.return_value = scores
        # A consulta faz join com a tabela do ativo para filtrar por preço,
        # ciclo e carteira.
        mock_scores.join.return_value.filter.return_value = chain
        mock_fiis.filter.return_value.all.return_value = fiis
        return list_opportunities(profile, limit, asset_type)


def test_a_vitrine_de_fii_volta_ranqueada(app):
    with app.app_context():
        scores = [_FiiScore("HGLG11", 84.0), _FiiScore("KNRI11", 71.0)]
        response, status = _run_list(scores, [_fii("HGLG11"), _fii("KNRI11")])

        assert status == 200
        body = response.get_json()
        assert [card["ticker"] for card in body["data"]] == ["HGLG11", "KNRI11"]


def test_o_card_de_fii_traz_os_indicadores_de_fundo_e_nao_os_de_acao(app):
    # Graham e ROE não existem num FII. Se vazassem para o card, a tela
    # mostraria campos vazios em vez de reclamar.
    with app.app_context():
        response, _ = _run_list([_FiiScore("HGLG11", 84.0)], [_fii("HGLG11")])
        card = response.get_json()["data"][0]

        assert card["vacancia_media"] == 2.41
        assert card["qtd_imoveis"] == 37
        assert card["p_vp"] == 0.89
        assert "graham_formula" not in card
        assert "roe" not in card
        assert "p_l" not in card


def test_o_card_carrega_motivo_e_alerta(app):
    with app.app_context():
        response, _ = _run_list([_FiiScore("HGLG11", 84.0)], [_fii("HGLG11")])
        score = response.get_json()["data"][0]["score"]

        assert score["reasons"][0]["code"] == "DY_SAUDAVEL"
        assert score["red_flags"][0]["code"] == "AGIO"


def test_fundo_nao_tem_classe_de_cota_entao_nada_e_deduplicado(app):
    # A dedupe de ON/PN existe porque POMO3 e POMO4 são a mesma empresa.
    # ALZR11 e ALZM11 são fundos diferentes e as duas vagas são legítimas.
    with app.app_context():
        scores = [_FiiScore("ALZR11", 80.0), _FiiScore("ALZM11", 78.0)]
        response, _ = _run_list(scores, [_fii("ALZR11"), _fii("ALZM11")])

        assert len(response.get_json()["data"]) == 2


def test_perfil_de_acao_nao_vale_para_fii(app):
    # CRESCIMENTO existe para ações e não para fundos. Aceitar em silêncio
    # devolveria uma lista pontuada por pesos que não são os pedidos.
    with app.app_context():
        response, status = _run_list([], [], profile="CRESCIMENTO")

        assert status == 400
        assert response.get_json()["profiles"] == ["EQUILIBRADO", "RENDA", "VALOR"]


def test_o_perfil_renda_e_aceito(app):
    with app.app_context():
        response, status = _run_list(
            [_FiiScore("HGLG11", 84.0)], [_fii("HGLG11")], profile="RENDA"
        )

        assert status == 200
        assert response.get_json()["profile"] == "RENDA"


def test_tipo_de_ativo_desconhecido_e_rejeitado(app):
    with app.app_context():
        response, status = _run_list([], [], asset_type="CRIPTO")

        assert status == 400
        assert response.get_json()["asset_types"] == ["ACAO", "FII"]


def test_sem_asset_type_a_vitrine_continua_sendo_a_de_acoes(app):
    # Compatibilidade: a tela de oportunidades existente chama sem o parâmetro.
    with app.app_context():
        with (
            patch("services.opportunity_service.StockScore.query") as mock_scores,
            patch("services.opportunity_service.Stock.query") as mock_stocks,
        ):
            chain = MagicMock()
            chain.order_by.return_value.limit.return_value.all.return_value = []
            mock_scores.join.return_value.filter.return_value = chain
            mock_stocks.filter.return_value.all.return_value = []

            response, status = list_opportunities()

        assert status == 200
        assert response.get_json()["profile"] == "EQUILIBRADO"


def test_os_perfis_de_fii_sao_outros(app):
    with app.app_context():
        response, status = list_profiles("FII")

        assert status == 200
        keys = [profile["key"] for profile in response.get_json()["data"]]
        assert keys == ["EQUILIBRADO", "RENDA", "VALOR"]


def test_os_pilares_de_fii_aparecem_nos_pesos_do_perfil(app):
    with app.app_context():
        response, _ = list_profiles("FII")
        weights = response.get_json()["data"][0]["weights"]

        assert sorted(weights) == [
            "ciclo",
            "estrutura",
            "liquidez",
            "renda",
            "valuation",
        ]


def test_o_score_de_um_fundo_isolado(app):
    with app.app_context():
        with patch("services.opportunity_service.FiiScore.query") as mock_query:
            mock_query.filter_by.return_value.first.return_value = _FiiScore(
                "HGLG11", 84.0
            )
            response, status = get_stock_score("HGLG11", "EQUILIBRADO", "FII")

        assert status == 200
        assert response.get_json()["ticker"] == "HGLG11"


def test_o_payload_do_fii_e_serializavel(app):
    with app.app_context():
        response, _ = _run_list([_FiiScore("HGLG11", 84.0)], [_fii("HGLG11")])
        assert json.dumps(response.get_json())
