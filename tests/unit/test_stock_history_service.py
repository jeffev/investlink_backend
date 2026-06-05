import datetime
from unittest.mock import MagicMock, patch

from services.stock_history_service import get_stock_price_history


class TestStockHistoryService:

    def test_success_with_data(self, app, sample_stock):
        """Ticker válido com registros → 200 e lista com data no formato ISO."""
        with app.app_context():
            mock_record = MagicMock()
            mock_record.date = datetime.date(2024, 1, 15)
            mock_record.open_price = 24.5
            mock_record.high = 25.5
            mock_record.low = 24.3
            mock_record.close_price = 25.1
            mock_record.volume = 1_000_000.0

            with (
                patch("services.stock_history_service.Stock.query") as mock_stock_query,
                patch(
                    "services.stock_history_service.StockPriceHistory.query"
                ) as mock_history_query,
            ):
                mock_stock_query.get.return_value = sample_stock
                (
                    mock_history_query.filter_by.return_value.filter.return_value.order_by.return_value.all.return_value
                ) = [mock_record]

                result, status_code = get_stock_price_history("PETR4", 90)

                assert status_code == 200
                data = result.get_json()
                assert data["ticker"] == "PETR4"
                assert len(data["data"]) == 1
                assert data["data"][0]["date"] == "2024-01-15"
                assert data["data"][0]["open"] == 24.5
                assert data["data"][0]["close"] == 25.1

    def test_success_no_data(self, app, sample_stock):
        """Ticker válido sem histórico → 200 com data=[]."""
        with app.app_context():
            with (
                patch("services.stock_history_service.Stock.query") as mock_stock_query,
                patch(
                    "services.stock_history_service.StockPriceHistory.query"
                ) as mock_history_query,
            ):
                mock_stock_query.get.return_value = sample_stock
                (
                    mock_history_query.filter_by.return_value.filter.return_value.order_by.return_value.all.return_value
                ) = []

                result, status_code = get_stock_price_history("PETR4", 90)

                assert status_code == 200
                assert result.get_json()["data"] == []

    def test_ticker_not_found(self, app):
        """Ticker inexistente → 404."""
        with app.app_context():
            with patch(
                "services.stock_history_service.Stock.query"
            ) as mock_stock_query:
                mock_stock_query.get.return_value = None

                result, status_code = get_stock_price_history("INVALID", 90)

                assert status_code == 404
                assert result.get_json()["message"] == "Stock not found"

    def test_days_zero_returns_all(self, app, sample_stock):
        """days=0 → query sem filtro de data, retorna tudo."""
        with app.app_context():
            with (
                patch("services.stock_history_service.Stock.query") as mock_stock_query,
                patch(
                    "services.stock_history_service.StockPriceHistory.query"
                ) as mock_history_query,
            ):
                mock_stock_query.get.return_value = sample_stock
                (
                    mock_history_query.filter_by.return_value.order_by.return_value.all.return_value
                ) = []

                result, status_code = get_stock_price_history("PETR4", 0)

                assert status_code == 200
                mock_history_query.filter_by.return_value.filter.assert_not_called()

    def test_exception_returns_500(self, app, sample_stock):
        """Exceção no banco → 500."""
        with app.app_context():
            with (
                patch("services.stock_history_service.Stock.query") as mock_stock_query,
                patch(
                    "services.stock_history_service.StockPriceHistory.query"
                ) as mock_history_query,
            ):
                mock_stock_query.get.return_value = sample_stock
                mock_history_query.filter_by.side_effect = Exception("DB error")

                result, status_code = get_stock_price_history("PETR4", 90)

                assert status_code == 500
                assert (
                    result.get_json()["message"]
                    == "An error occurred, please try again later"
                )
