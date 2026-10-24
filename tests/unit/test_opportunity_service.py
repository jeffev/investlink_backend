import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.opportunity_service import (
    get_stock_score,
    list_opportunities,
    list_profiles,
)


class _Score:
    """Minimal stand-in with the same to_json contract as StockScore."""

    def __init__(self, ticker, total, eligible=True):
        self.ticker = ticker
        self.profile = "EQUILIBRADO"
        self.run_date = datetime(2026, 9, 9)
        self.score_total = total
        self.eligible = eligible

    def to_json(self):
        return {
            "ticker": self.ticker,
            "profile": self.profile,
            "score_total": self.score_total,
            "eligible": self.eligible,
            "pillars": [{"key": "valuation", "label": "Valuation", "value": 70.0}],
            "reasons": [{"code": "PILAR_VALUATION", "message": "Múltiplos baratos"}],
            "red_flags": [],
            "exclusion_reasons": [],
        }


def _stock(ticker):
    return SimpleNamespace(
        ticker=ticker,
        companyname=f"Empresa {ticker}",
        sectorname="Bens Industriais",
        price=10.0,
        p_l=5.0,
        p_vp=1.0,
        dy=6.0,
        roe=20.0,
        roic=18.0,
        graham_formula=15.0,
        discount_to_graham=-33.0,
        fundamentals_source="CVM",
        fundamentals_date=date(2026, 6, 30),
    )


def _run_list(scores, stocks, profile=None, limit=12):
    with (
        patch("services.opportunity_service.StockScore.query") as mock_scores,
        patch("services.opportunity_service.Stock.query") as mock_stocks,
        patch("services.opportunity_service.get_score_deltas", return_value={}),
    ):
        chain = MagicMock()
        chain.order_by.return_value.limit.return_value.all.return_value = scores
        # A consulta faz join com a tabela do ativo para filtrar por preço,
        # ciclo e carteira.
        mock_scores.join.return_value.filter.return_value = chain
        mock_stocks.filter.return_value.all.return_value = stocks
        return list_opportunities(profile, limit)


def test_opportunities_come_back_ranked(app):
    with app.app_context():
        scores = [_Score("AAAA3", 80.0), _Score("BBBB3", 70.0)]
        stocks = [_stock("AAAA3"), _stock("BBBB3")]

        result, status = _run_list(scores, stocks)

        assert status == 200
        data = result.get_json()["data"]
        assert [card["ticker"] for card in data] == ["AAAA3", "BBBB3"]


def test_each_card_carries_its_reasons(app):
    with app.app_context():
        result, _ = _run_list([_Score("AAAA3", 80.0)], [_stock("AAAA3")])
        card = result.get_json()["data"][0]
        assert card["score"]["reasons"][0]["code"] == "PILAR_VALUATION"
        assert card["score"]["score_total"] == 80.0


def test_only_one_share_class_of_a_company_takes_a_slot(app):
    with app.app_context():
        # POMO3 e POMO4 pontuam quase igual; gastar dois cards nelas mostraria
        # onze ideias num espaço de doze.
        scores = [_Score("POMO4", 80.0), _Score("POMO3", 79.0), _Score("AAAA3", 70.0)]
        stocks = [_stock("POMO4"), _stock("POMO3"), _stock("AAAA3")]

        result, _ = _run_list(scores, stocks)

        tickers = [card["ticker"] for card in result.get_json()["data"]]
        assert tickers == ["POMO4", "AAAA3"]


def test_the_best_scoring_class_is_the_one_kept(app):
    with app.app_context():
        scores = [_Score("POMO4", 80.0), _Score("POMO3", 79.0)]
        stocks = [_stock("POMO4"), _stock("POMO3")]

        result, _ = _run_list(scores, stocks)

        assert [c["ticker"] for c in result.get_json()["data"]] == ["POMO4"]


def test_an_unknown_profile_is_rejected_with_the_valid_ones(app):
    with app.app_context():
        result, status = list_opportunities("AGRESSIVO", 12)
        assert status == 400
        assert "EQUILIBRADO" in result.get_json()["profiles"]


def test_no_profile_falls_back_to_the_default(app):
    with app.app_context():
        result, status = _run_list([], [], profile=None)
        assert status == 200
        assert result.get_json()["profile"] == "EQUILIBRADO"


def test_an_empty_ranking_is_not_an_error(app):
    with app.app_context():
        result, status = _run_list([], [])
        assert status == 200
        assert result.get_json()["data"] == []


def test_a_score_without_its_stock_is_dropped(app):
    with app.app_context():
        result, _ = _run_list([_Score("AAAA3", 80.0)], [])
        assert result.get_json()["data"] == []


def test_the_limit_is_capped(app):
    with app.app_context():
        result, status = _run_list([], [], limit=100000)
        assert status == 200


# ── get_stock_score ──────────────────────────────────────────────────────────


def test_score_of_one_ticker(app):
    with app.app_context():
        with patch("services.opportunity_service.StockScore.query") as mock_query:
            mock_query.filter_by.return_value.first.return_value = _Score("AAAA3", 80.0)

            result, status = get_stock_score("AAAA3", "EQUILIBRADO")

        assert status == 200
        assert result.get_json()["score_total"] == 80.0


def test_an_excluded_company_still_answers_why(app):
    # A pergunta "por que PETR4 não está na lista?" é a que um screener que
    # simplesmente esconde o ativo não consegue responder.
    with app.app_context():
        excluded = _Score("AAAA3", None, eligible=False)
        with patch("services.opportunity_service.StockScore.query") as mock_query:
            mock_query.filter_by.return_value.first.return_value = excluded

            result, status = get_stock_score("AAAA3", None)

        assert status == 200
        assert result.get_json()["eligible"] is False


def test_a_ticker_without_score_returns_404(app):
    with app.app_context():
        with patch("services.opportunity_service.StockScore.query") as mock_query:
            mock_query.filter_by.return_value.first.return_value = None

            _, status = get_stock_score("ZZZZ4", None)

        assert status == 404


# ── list_profiles ────────────────────────────────────────────────────────────


def test_profiles_are_offered_with_their_weights(app):
    with app.app_context():
        result, status = list_profiles()
        data = result.get_json()["data"]

        assert status == 200
        assert {entry["key"] for entry in data} >= {"VALOR", "DIVIDENDOS"}
        assert sum(1 for entry in data if entry["default"]) == 1
        assert all(entry["weights"] for entry in data)


def test_score_payload_is_json_serialisable(app):
    with app.app_context():
        result, _ = _run_list([_Score("AAAA3", 80.0)], [_stock("AAAA3")])
        json.dumps(result.get_json())
