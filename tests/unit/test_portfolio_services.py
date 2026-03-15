from unittest.mock import patch, MagicMock
from services.portfolio_services import (
    list_portfolio,
    get_portfolio_summary,
    add_position,
    edit_position,
    delete_position,
)
from models.portfolio import Portfolio


class TestPortfolioServices:

    def test_list_portfolio_success(self, app, sample_stock):
        with app.app_context():
            mock_position = MagicMock(spec=Portfolio)
            mock_position.stock = sample_stock
            mock_position.to_json.return_value = {
                "id": 1,
                "user_id": 1,
                "ticker": "PETR4",
                "quantity": 10.0,
                "average_price": 25.0,
                "total_invested": 250.0,
                "created_at": "2026-03-14T10:00:00",
                "updated_at": "2026-03-14T10:00:00",
            }

            with patch(
                "services.portfolio_services.Portfolio.query"
            ) as mock_portfolio_query:
                mock_portfolio_query.filter_by.return_value.all.return_value = [
                    mock_position
                ]

                result, status_code = list_portfolio(1)

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1
                assert result_data[0]["ticker"] == "PETR4"

    def test_list_portfolio_empty(self, app):
        with app.app_context():
            with patch(
                "services.portfolio_services.Portfolio.query"
            ) as mock_portfolio_query:
                mock_portfolio_query.filter_by.return_value.all.return_value = []

                result, status_code = list_portfolio(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data == []

    def test_add_position_success(self, app):
        with app.app_context():
            position_data = {
                "user_id": 1,
                "ticker": "PETR4",
                "quantity": 10.0,
                "average_price": 25.0,
            }

            with patch("services.portfolio_services.db") as mock_db:
                mock_db.session = MagicMock()
                mock_db.session.get.side_effect = [
                    MagicMock(),
                    MagicMock(),
                ]

                result, status_code = add_position(position_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "Position added successfully"

    def test_add_position_missing_fields(self, app):
        with app.app_context():
            position_data = {
                "user_id": 1,
                "ticker": "PETR4",
            }

            result, status_code = add_position(position_data)

            assert status_code == 400
            result_data = result.get_json()
            assert result_data["message"] == "Missing required fields"

    def test_edit_position_success(self, app):
        with app.app_context():
            position_data = {"quantity": 20.0, "average_price": 30.0}
            mock_position = MagicMock(spec=Portfolio)

            with patch("services.portfolio_services.db") as mock_db:
                mock_db.session = MagicMock()
                mock_db.session.get.return_value = mock_position

                result, status_code = edit_position(1, position_data)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Position updated successfully"

    def test_delete_position_success(self, app):
        with app.app_context():
            mock_position = MagicMock(spec=Portfolio)

            with patch("services.portfolio_services.db") as mock_db:
                mock_db.session = MagicMock()
                mock_db.session.get.return_value = mock_position

                result, status_code = delete_position(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Position deleted successfully"

    def test_get_portfolio_summary_success(self, app, sample_stock):
        with app.app_context():
            mock_position = MagicMock(spec=Portfolio)
            mock_position.quantity = 10.0
            mock_position.average_price = 25.0
            mock_position.total_invested = 250.0
            mock_position.stock = sample_stock
            mock_position.stock.price = 30.0

            with patch(
                "services.portfolio_services.Portfolio.query"
            ) as mock_portfolio_query:
                mock_portfolio_query.filter_by.return_value.all.return_value = [
                    mock_position
                ]

                result, status_code = get_portfolio_summary(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["total_invested"] == 250.0
