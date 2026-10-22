from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from services.score_backtest_service import (
    MIN_UNIVERSE,
    _annual_return,
    _caveats,
    _compound,
    _evaluate_year,
    _score_year,
    _summarise,
    _year_end_prices,
    backtest_score,
)


def _indicator(ticker, year=2021, **overrides):
    values = {
        "ticker": ticker,
        "year": year,
        "p_l": 10.0,
        "p_vp": 1.5,
        "ev_ebit": 8.0,
        "roe": 15.0,
        "m_liquida": 10.0,
        "div_liq_ebit": 1.5,
        "dy": 5.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _price_row(ticker, day, close):
    return SimpleNamespace(ticker=ticker, date=day, close_price=close)


# ── Retorno anual ────────────────────────────────────────────────────────────


def test_annual_return_goes_from_one_year_end_to_the_next():
    prices = {("PETR4", 2021): 100.0, ("PETR4", 2022): 130.0}
    assert _annual_return("PETR4", 2021, prices) == 30.0


def test_no_return_without_both_ends():
    prices = {("PETR4", 2021): 100.0}
    assert _annual_return("PETR4", 2021, prices) is None


def test_no_return_from_a_zero_price():
    prices = {("PETR4", 2021): 0.0, ("PETR4", 2022): 10.0}
    assert _annual_return("PETR4", 2021, prices) is None


# ── Preço de fim de ano ──────────────────────────────────────────────────────


def _run_prices(rows, years, tickers):
    with patch("services.score_backtest_service.StockPriceHistory.query") as mock_query:
        mock_query.filter.return_value.order_by.return_value.all.return_value = rows
        return _year_end_prices(years, tickers)


def test_the_last_traded_week_of_the_year_wins(app):
    with app.app_context():
        rows = [
            _price_row("PETR4", date(2021, 12, 20), 90.0),
            _price_row("PETR4", date(2021, 12, 27), 100.0),
        ]
        prices = _run_prices(rows, [2021], ["PETR4"])
        assert prices[("PETR4", 2021)] == 100.0


def test_a_week_outside_the_window_is_ignored(app):
    # Papel que parou de negociar em junho não herda preço de fim de ano.
    with app.app_context():
        rows = [_price_row("PETR4", date(2021, 6, 1), 50.0)]
        assert _run_prices(rows, [2021], ["PETR4"]) == {}


def test_no_query_without_tickers(app):
    with app.app_context():
        assert _year_end_prices([2021], []) == {}


# ── Score de um ano ──────────────────────────────────────────────────────────


def test_the_year_is_scored_with_its_own_multiples(app):
    # O ponto do módulo: 2021 é pontuado com 2021. Nada de look-ahead.
    with app.app_context():
        rows = [_indicator(f"AAA{i}", p_l=float(i + 1)) for i in range(6)]
        sectors = {row.ticker: "Bens Industriais" for row in rows}

        scores = _score_year(rows, sectors, "EQUILIBRADO")

        assert len(scores) == 6
        # P/L menor é melhor: o primeiro pontua acima do último.
        assert scores["AAA0"] > scores["AAA5"]


def test_scoring_happens_inside_the_sector(app):
    with app.app_context():
        utilidade = [_indicator(f"UTIL{i}", p_l=float(20 + i)) for i in range(5)]
        tecnologia = [_indicator(f"TECH{i}", p_l=float(4 + i)) for i in range(5)]
        rows = utilidade + tecnologia
        sectors = {
            r.ticker: ("Utilidade" if r.ticker.startswith("UTIL") else "Tec")
            for r in rows
        }

        scores = _score_year(rows, sectors, "EQUILIBRADO")

        # O P/L 20 da elétrica é o melhor do setor dela, apesar de alto.
        assert scores["UTIL0"] == max(scores[t] for t in scores if t.startswith("UTIL"))


# ── Avaliação de um ano ──────────────────────────────────────────────────────


def _universe(size, winner_return=100.0, other_return=0.0):
    scores = {f"AAA{i}": float(size - i) for i in range(size)}
    prices = {}
    for i in range(size):
        retorno = winner_return if i == 0 else other_return
        prices[(f"AAA{i}", 2021)] = 100.0
        prices[(f"AAA{i}", 2022)] = 100.0 * (1 + retorno / 100)
    return scores, prices


def test_the_top_decile_is_compared_with_the_universe_average():
    scores, prices = _universe(40)
    resultado = _evaluate_year(2021, scores, prices)

    assert resultado["selected"] == 4
    assert resultado["universe_size"] == 40
    assert resultado["excess_return"] > 0


def test_a_universe_too_small_is_refused():
    # Decil de dez ações é uma ação: isso é sorte, não resultado.
    scores, prices = _universe(MIN_UNIVERSE - 1)
    assert _evaluate_year(2021, scores, prices) is None


def test_the_period_held_is_stated():
    scores, prices = _universe(40)
    assert _evaluate_year(2021, scores, prices)["holding_period"] == (
        "2021-12-31 → 2022-12-31"
    )


# ── Resumo ───────────────────────────────────────────────────────────────────


def test_returns_compound_rather_than_add():
    # Dois anos de 10% dão 21%, não 20%.
    assert _compound([10.0, 10.0]) == 21.0


def test_the_summary_annualises_over_the_years_measured():
    resultados = [
        {"top_decile_return": 21.0, "universe_return": 0.0, "excess_return": 21.0},
        {"top_decile_return": 21.0, "universe_return": 0.0, "excess_return": 21.0},
    ]
    resumo = _summarise(resultados)

    assert resumo["years"] == 2
    assert resumo["top_decile_annualised"] == 21.0
    assert resumo["beat_universe_in"] == 2


def test_no_summary_without_any_year():
    assert _summarise([]) is None


# ── Ressalvas ────────────────────────────────────────────────────────────────


def test_the_survivorship_bias_travels_with_the_number():
    # Um backtest sem as limitações ao lado é propaganda.
    codigos = [c["code"] for c in _caveats()]
    assert "VIES_SOBREVIVENCIA" in codigos
    assert "COMPARADOR_NAO_E_IBOV" in codigos
    assert all(c["message"] for c in _caveats())


# ── Serviço ──────────────────────────────────────────────────────────────────


def test_an_unknown_profile_is_refused(app):
    with app.app_context():
        _, status = backtest_score("AGRESSIVO")
        assert status == 400


def test_without_history_the_service_says_what_to_run(app):
    with app.app_context():
        with patch(
            "services.score_backtest_service.StockIndicatorHistory.query"
        ) as mock_query:
            mock_query.all.return_value = []

            result, status = backtest_score()

        assert status == 409
        assert "run_price_history" in result.get_json()["message"]


def test_the_response_carries_the_caveats(app):
    with app.app_context():
        with (
            patch(
                "services.score_backtest_service.StockIndicatorHistory.query"
            ) as mock_query,
            patch("services.score_backtest_service._run_years") as mock_run,
        ):
            mock_query.all.return_value = [_indicator("PETR4")]
            mock_run.return_value = []

            result, status = backtest_score()

        assert status == 200
        assert result.get_json()["caveats"]
