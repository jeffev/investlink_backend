from unittest.mock import MagicMock, patch

from models.stock import Stock  # noqa: F401
from models.user import User  # noqa: F401
from models.favorite import Favorite  # noqa: F401
from services.stock_services import bulk_view_stocks


def _make_stock(ticker, price=30.0):
    s = MagicMock(spec=Stock)
    s.ticker = ticker
    s.to_json.return_value = {"ticker": ticker, "price": price, "p_l": 10.0}
    return s


class TestBulkViewStocks:

    def test_multiple_valid_tickers(self, app):
        """Tickers válidos → 200 com array de todos."""
        with app.app_context():
            stocks = [_make_stock("PETR4"), _make_stock("VALE3")]
            with (
                patch("services.stock_services.Stock.query") as mock_query,
                patch(
                    "services.stock_services.get_latest_predictions_map"
                ) as mock_pred,
            ):
                mock_query.filter.return_value.all.return_value = stocks
                mock_pred.return_value = {}

                result, status = bulk_view_stocks(["PETR4", "VALE3"])

                assert status == 200
                data = result.get_json()
                assert len(data) == 2
                tickers = [d["ticker"] for d in data]
                assert "PETR4" in tickers
                assert "VALE3" in tickers

    def test_partially_invalid_tickers(self, app):
        """Tickers parcialmente inválidos → 200 com só os encontrados."""
        with app.app_context():
            stocks = [_make_stock("PETR4")]
            with (
                patch("services.stock_services.Stock.query") as mock_query,
                patch(
                    "services.stock_services.get_latest_predictions_map"
                ) as mock_pred,
            ):
                mock_query.filter.return_value.all.return_value = stocks
                mock_pred.return_value = {}

                result, status = bulk_view_stocks(["PETR4", "INVALID"])

                assert status == 200
                data = result.get_json()
                assert len(data) == 1
                assert data[0]["ticker"] == "PETR4"

    def test_empty_tickers(self, app):
        """Lista vazia → 200 com array vazio, sem consulta ao banco."""
        with app.app_context():
            result, status = bulk_view_stocks([])
            assert status == 200
            assert result.get_json() == []
