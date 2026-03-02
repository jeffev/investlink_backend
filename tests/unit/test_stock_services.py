from unittest.mock import patch, MagicMock
from services.stock_services import (
    list_stocks,
    view_stock,
    new_stock,
    edit_stock,
    delete_stock,
    get_all_stocks_from_statusinvest,
    update_all_stocks,
    calculate_ey,
)
from models.stock import Stock
from models.favorite import Favorite


class TestStockServices:

    def test_list_stocks_success(self, app, sample_user):
        """Test successful listing of stocks with favorites"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "PETR4"
            mock_stock.to_json.return_value = {
                "ticker": "PETR4",
                "companyname": "Petrobras",
                "price": 25.0,
                "lpa": 5.0,
                "vpa": 20.0,
                "p_l": 5.0,
                "dy": 0.08,
            }

            mock_favorite = MagicMock(spec=Favorite)
            mock_favorite.stock_ticker = "PETR4"

            mock_paginated = MagicMock()
            mock_paginated.items = [mock_stock]
            mock_paginated.total = 1
            mock_paginated.pages = 1
            mock_paginated.page = 1

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.Favorite.query") as mock_favorite_query,
            ):

                mock_stock_query.paginate.return_value = mock_paginated
                mock_favorite_query.filter_by.return_value.all.return_value = [
                    mock_favorite
                ]

                result, status_code = list_stocks(sample_user.id)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["pagination"]["total"] == 1
                assert result_data["pagination"]["current_page"] == 1
                assert len(result_data["data"]) == 1
                assert result_data["data"][0]["ticker"] == "PETR4"
                assert result_data["data"][0]["favorita"] is True

    def test_list_stocks_empty(self, app):
        """Test listing stocks when no stocks exist"""
        with app.app_context():
            mock_paginated = MagicMock()
            mock_paginated.items = []
            mock_paginated.total = 0
            mock_paginated.pages = 0
            mock_paginated.page = 1

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.Favorite.query") as mock_favorite_query,
            ):

                mock_stock_query.paginate.return_value = mock_paginated
                mock_favorite_query.filter_by.return_value.all.return_value = []

                result, status_code = list_stocks(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["data"] == []
                assert result_data["pagination"]["total"] == 0

    def test_list_stocks_with_exception(self, app):
        """Test listing stocks when an exception occurs"""
        with app.app_context():
            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.Favorite.query") as mock_favorite_query,
            ):
                mock_favorite_query.filter_by.return_value.all.return_value = []
                mock_stock_query.paginate.side_effect = Exception("Database error")

                result, status_code = list_stocks(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_view_stock_success(self, app, sample_stock):
        """Test viewing a specific stock"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.to_json.return_value = {
                "ticker": "PETR4",
                "companyname": "Petrobras",
                "price": 25.0,
                "lpa": 5.0,
                "vpa": 20.0,
                "p_l": 5.0,
                "dy": 0.08,
            }

            with patch("services.stock_services.Stock.query") as mock_stock_query:
                mock_stock_query.get.return_value = mock_stock

                result, status_code = view_stock("PETR4")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["ticker"] == "PETR4"

    def test_view_stock_not_found(self, app):
        """Test viewing a stock that doesn't exist"""
        with app.app_context():
            with patch("services.stock_services.Stock.query") as mock_stock_query:
                mock_stock_query.get.return_value = None

                result, status_code = view_stock("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Stock not found"

    def test_view_stock_with_exception(self, app):
        """Test viewing a stock when an exception occurs"""
        with app.app_context():
            with patch("services.stock_services.Stock.query") as mock_stock_query:
                mock_stock_query.get.side_effect = Exception("Database error")

                result, status_code = view_stock("PETR4")

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_new_stock_success(self, app):
        """Test creating a new stock"""
        with app.app_context():
            stock_data = {
                "ticker": "NEWSTK4",
                "companyname": "New Stock",
                "price": 30.0,
                "lpa": 3.0,
                "vpa": 15.0,
                "p_l": 10.0,
                "dy": 0.05,
            }

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_stock_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = new_stock(stock_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "Stock added successfully"

    def test_new_stock_already_exists(self, app):
        """Test creating a stock that already exists"""
        with app.app_context():
            stock_data = {
                "ticker": "EXISTING4",
                "companyname": "Existing Stock",
                "price": 30.0,
                "lpa": 3.0,
                "vpa": 15.0,
                "p_l": 10.0,
                "dy": 0.05,
            }

            with patch("services.stock_services.Stock.query") as mock_stock_query:
                mock_stock_query.filter_by.return_value.first.return_value = MagicMock()

                result, status_code = new_stock(stock_data)

                assert status_code == 400
                result_data = result.get_json()
                assert result_data["message"] == "Stock already exists"

    def test_new_stock_with_exception(self, app):
        """Test creating a stock when an exception occurs"""
        with app.app_context():
            stock_data = {
                "ticker": "ERRORSTK4",
                "companyname": "Error Stock",
                "price": 30.0,
                "lpa": 3.0,
                "vpa": 15.0,
                "p_l": 10.0,
                "dy": 0.05,
            }

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_stock_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = new_stock(stock_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_edit_stock_success(self, app):
        """Test editing an existing stock"""
        with app.app_context():
            stock_data = {
                "companyname": "Updated Stock",
                "price": 35.0,
                "lpa": 4.0,
                "dy": 0.06,
            }

            mock_stock = MagicMock(spec=Stock)
            mock_stock.get_graham_formula.return_value = 20.0
            mock_stock.get_discount_to_graham.return_value = 10.0

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_stock_query.get.return_value = mock_stock
                mock_db_session.commit = MagicMock()

                result, status_code = edit_stock("PETR4", stock_data)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Stock edited successfully"

                # Verify that the attributes were set
                for key, value in stock_data.items():
                    assert getattr(mock_stock, key) == value

                # Verify that graham_formula and discount_to_graham were recalculated
                assert mock_stock.graham_formula == 20.0
                assert mock_stock.discount_to_graham == 10.0

    def test_edit_stock_not_found(self, app):
        """Test editing a stock that doesn't exist"""
        with app.app_context():
            stock_data = {"companyname": "Updated Stock"}

            with patch("services.stock_services.Stock.query") as mock_stock_query:
                mock_stock_query.get.return_value = None

                result, status_code = edit_stock("INVALID", stock_data)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Stock not found"

    def test_edit_stock_with_exception(self, app):
        """Test editing a stock when an exception occurs"""
        with app.app_context():
            stock_data = {"companyname": "Updated Stock"}

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_stock_query.get.return_value = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = edit_stock("PETR4", stock_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_delete_stock_success(self, app):
        """Test deleting an existing stock"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_stock_query.get.return_value = mock_stock
                mock_db_session.delete = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = delete_stock("PETR4")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Stock deleted successfully"

    def test_delete_stock_not_found(self, app):
        """Test deleting a stock that doesn't exist"""
        with app.app_context():
            with patch("services.stock_services.Stock.query") as mock_stock_query:
                mock_stock_query.get.return_value = None

                result, status_code = delete_stock("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Stock not found"

    def test_delete_stock_with_exception(self, app):
        """Test deleting a stock when an exception occurs"""
        with app.app_context():
            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_stock_query.get.return_value = MagicMock()
                mock_db_session.delete = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = delete_stock("PETR4")

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    @patch("services.stock_services.requests.get")
    def test_get_all_stocks_from_statusinvest_success(self, mock_get):
        """Test successful retrieval of stocks from StatusInvest"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [
                {
                    "ticker": "PETR4",
                    "companyname": "Petrobras",
                    "price": 25.0,
                    "lpa": 5.0,
                    "vpa": 20.0,
                    "p_l": 5.0,
                    "dy": 0.08,
                }
            ]
        }
        mock_get.return_value = mock_response

        result = get_all_stocks_from_statusinvest()

        assert result is not None
        assert "list" in result
        assert len(result["list"]) == 1
        assert result["list"][0]["ticker"] == "PETR4"

    @patch("services.stock_services.requests.get")
    def test_get_all_stocks_from_statusinvest_http_error(self, mock_get):
        """Test retrieval of stocks when HTTP error occurs"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_all_stocks_from_statusinvest()

        assert result is None

    @patch("services.stock_services.requests.get")
    def test_get_all_stocks_from_statusinvest_exception(self, mock_get):
        """Test retrieval of stocks when an exception occurs"""
        mock_get.side_effect = Exception("Network error")

        result = get_all_stocks_from_statusinvest()

        assert result is None

    def test_calculate_ey(self):
        """Test calculation of earnings yield"""
        # Test normal case
        stock_data = {"lpa": 5.0, "price": 25.0}
        result = calculate_ey(stock_data)
        expected = 5.0 / 25.0
        assert result == expected

        # Test zero price (should return 0)
        stock_data = {"lpa": 5.0, "price": 0.0}
        result = calculate_ey(stock_data)
        assert result == 0.0

        # Test zero lpa (should return 0)
        stock_data = {"lpa": 0.0, "price": 25.0}
        result = calculate_ey(stock_data)
        assert result == 0.0

        # Test missing values (should return 0)
        stock_data = {}
        result = calculate_ey(stock_data)
        assert result == 0.0

    @patch("services.stock_services.get_all_stocks_from_statusinvest")
    def test_update_all_stocks_success(self, mock_get_stocks, app):
        """Test successful update of all stocks"""
        with app.app_context():
            mock_stock_data = {
                "list": [
                    {
                        "ticker": "PETR4",
                        "companyname": "Petrobras",
                        "price": 25.0,
                        "lpa": 5.0,
                        "vpa": 20.0,
                        "p_l": 5.0,
                        "dy": 0.08,
                        "roic": 0.15,
                        "ey": 0.20,
                    }
                ]
            }

            mock_existing_stock = MagicMock(spec=Stock)
            mock_existing_stock.ticker = "PETR4"
            mock_existing_stock.get_graham_formula.return_value = 20.0
            mock_existing_stock.get_discount_to_graham.return_value = 10.0

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_get_stocks.return_value = mock_stock_data
                mock_stock_query.filter.return_value.all.return_value = [
                    mock_existing_stock
                ]
                mock_db_session.add_all = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = update_all_stocks()

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Stocks updated successfully"

    @patch("services.stock_services.get_all_stocks_from_statusinvest")
    def test_update_all_stocks_no_data(self, mock_get_stocks, app):
        """Test update of stocks when no data is returned"""
        with app.app_context():
            mock_get_stocks.return_value = None

            result, status_code = update_all_stocks()

            assert status_code == 500
            result_data = result.get_json()
            assert "Error fetching stock data" in result_data["error"]

    @patch("services.stock_services.get_all_stocks_from_statusinvest")
    def test_update_all_stocks_with_exception(self, mock_get_stocks, app):
        """Test update of stocks when an exception occurs"""
        with app.app_context():
            mock_get_stocks.return_value = {"list": []}

            with patch("services.stock_services.db.session") as mock_db_session:
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = update_all_stocks()

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]
