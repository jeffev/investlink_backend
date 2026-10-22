from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.historical_context_service import (
    get_historical_context,
    _percentile_of,
    _verdict,
)


def _history(values, key="p_l", start_year=2021):
    """Builds fake StockIndicatorHistory rows carrying `values` under `key`."""
    return [
        SimpleNamespace(year=start_year + offset, **{key: value})
        for offset, value in enumerate(values)
    ]


def _run(stock, history_rows):
    """Calls the service with Stock.query and the history query both mocked."""
    with (
        patch("services.historical_context_service.Stock.query") as mock_stock_query,
        patch(
            "services.historical_context_service.StockIndicatorHistory.query"
        ) as mock_history_query,
    ):
        mock_stock_query.get.return_value = stock
        chain = MagicMock()
        chain.order_by.return_value.all.return_value = history_rows
        mock_history_query.filter.return_value = chain
        return get_historical_context("PETR4")


def test_percentile_of_counts_values_below_current():
    assert _percentile_of([10, 12, 14, 16], 13) == 50.0
    assert _percentile_of([10, 12, 14, 16], 9) == 0.0
    assert _percentile_of([10, 12, 14, 16], 20) == 100.0


def test_percentile_of_returns_none_without_history():
    assert _percentile_of([], 10) is None


def test_verdict_respects_direction_of_the_indicator():
    # A multiple below its own median is cheap when lower is better...
    assert _verdict(-35.0, lower_is_better=True) == "BARATO"
    assert _verdict(35.0, lower_is_better=True) == "CARO"
    # ...and the reverse for dividend yield, where higher is better.
    assert _verdict(-35.0, lower_is_better=False) == "CARO"
    assert _verdict(35.0, lower_is_better=False) == "BARATO"


def test_verdict_is_in_line_inside_the_band():
    assert _verdict(5.0, lower_is_better=True) == "EM_LINHA"
    assert _verdict(-9.99, lower_is_better=False) == "EM_LINHA"


def test_returns_404_when_stock_does_not_exist(app):
    with app.app_context():
        result, status_code = _run(None, [])
        assert status_code == 404
        assert result.get_json()["message"] == "Stock not found"


def test_reports_discount_against_the_company_own_median(app):
    with app.app_context():
        stock = SimpleNamespace(p_l=8.2, p_vp=None, ev_ebit=None, dy=None)
        result, status_code = _run(stock, _history([11.0, 12.6, 14.0, 12.6, 13.2]))

        assert status_code == 200
        data = result.get_json()
        p_l = next(i for i in data["indicators"] if i["key"] == "p_l")

        assert p_l["median"] == 12.6
        assert p_l["current"] == 8.2
        assert p_l["deviation_percent"] == -34.92
        assert p_l["verdict"] == "BARATO"
        assert p_l["percentile"] == 0.0
        assert p_l["min"] == 11.0
        assert p_l["max"] == 14.0


def test_skips_indicator_without_enough_closed_years(app):
    with app.app_context():
        stock = SimpleNamespace(p_l=8.2, p_vp=None, ev_ebit=None, dy=None)
        # Only two usable years — below MIN_YEARS, so the median is noise.
        result, status_code = _run(stock, _history([11.0, 12.6]))

        assert status_code == 200
        assert result.get_json()["indicators"] == []


def test_skips_indicator_when_current_value_is_missing(app):
    with app.app_context():
        stock = SimpleNamespace(p_l=None, p_vp=None, ev_ebit=None, dy=None)
        result, status_code = _run(stock, _history([11.0, 12.6, 14.0]))

        assert status_code == 200
        assert result.get_json()["indicators"] == []


def test_ignores_years_where_the_indicator_is_null(app):
    with app.app_context():
        stock = SimpleNamespace(p_l=8.2, p_vp=None, ev_ebit=None, dy=None)
        rows = _history([11.0, None, 12.6, None, 14.0])
        result, status_code = _run(stock, rows)

        data = result.get_json()
        p_l = next(i for i in data["indicators"] if i["key"] == "p_l")
        assert p_l["years"] == [2021, 2023, 2025]
        assert p_l["median"] == 12.6


def test_dividend_yield_below_its_median_is_reported_as_expensive(app):
    with app.app_context():
        stock = SimpleNamespace(p_l=None, p_vp=None, ev_ebit=None, dy=3.0)
        result, status_code = _run(stock, _history([8.0, 9.0, 10.0], key="dy"))

        data = result.get_json()
        dy = next(i for i in data["indicators"] if i["key"] == "dy")
        assert dy["verdict"] == "CARO"
        assert dy["lower_is_better"] is False


def test_returns_500_on_unexpected_error(app):
    with app.app_context():
        with patch("services.historical_context_service.Stock.query") as mock_query:
            mock_query.get.side_effect = Exception("boom")

            result, status_code = get_historical_context("PETR4")

            assert status_code == 500
            assert "An error occurred" in result.get_json()["message"]
