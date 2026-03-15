from unittest.mock import patch, MagicMock
from services.favorite_services import get_price_alerts
from models.favorite import Favorite
from models.stock import Stock


class TestGetPriceAlerts:
    """Tests for get_price_alerts function"""

    def test_get_price_alerts_returns_triggered(self, app):
        """Test get_price_alerts returns triggered alerts with correct calculation"""
        with app.app_context():
            # Build mock stock
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "PETR4"
            mock_stock.companyname = "Petrobras"
            mock_stock.price = 24.0

            # Build mock favorite with ceiling_price set
            mock_fav = MagicMock(spec=Favorite)
            mock_fav.stock = mock_stock
            mock_fav.ceiling_price = 30.0
            mock_fav.target_price = None

            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = [mock_fav]

                result, status_code = get_price_alerts(user_id=1)

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1
                assert result_data[0]["ticker"] == "PETR4"
                assert result_data[0]["companyname"] == "Petrobras"
                assert result_data[0]["current_price"] == 24.0
                assert result_data[0]["ceiling_price"] == 30.0
                assert result_data[0]["discount_to_ceiling_percent"] == 20.0

    def test_get_price_alerts_empty_when_no_triggers(self, app):
        """Test get_price_alerts returns empty list when no price alerts triggered"""
        with app.app_context():
            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = []

                result, status_code = get_price_alerts(user_id=1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data == []

    def test_get_price_alerts_discount_calculation(self, app):
        """Test discount_to_ceiling_percent calculation is correct"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "VALE3"
            mock_stock.companyname = "Vale"
            mock_stock.price = 32.0

            mock_fav = MagicMock(spec=Favorite)
            mock_fav.stock = mock_stock
            mock_fav.ceiling_price = 40.0
            mock_fav.target_price = None

            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = [mock_fav]

                result, status_code = get_price_alerts(user_id=2)

                assert status_code == 200
                result_data = result.get_json()
                # (40 - 32) / 40 * 100 = 20%
                assert result_data[0]["discount_to_ceiling_percent"] == 20.0

    def test_get_price_alerts_no_ceiling_price(self, app):
        """Test discount_to_ceiling_percent is None when ceiling_price not set"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "ITUB4"
            mock_stock.companyname = "Itaú"
            mock_stock.price = 28.0

            # Favorite with only target_price, no ceiling_price
            mock_fav = MagicMock(spec=Favorite)
            mock_fav.stock = mock_stock
            mock_fav.ceiling_price = None
            mock_fav.target_price = 30.0

            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = [mock_fav]

                result, status_code = get_price_alerts(user_id=3)

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1
                assert result_data[0]["discount_to_ceiling_percent"] is None
                assert result_data[0]["ceiling_price"] is None
                assert result_data[0]["target_price"] == 30.0

    def test_get_price_alerts_multiple_alerts(self, app):
        """Test get_price_alerts returns multiple triggered alerts"""
        with app.app_context():
            # First alert
            mock_stock1 = MagicMock(spec=Stock)
            mock_stock1.ticker = "PETR4"
            mock_stock1.companyname = "Petrobras"
            mock_stock1.price = 24.0

            mock_fav1 = MagicMock(spec=Favorite)
            mock_fav1.stock = mock_stock1
            mock_fav1.ceiling_price = 30.0
            mock_fav1.target_price = 25.0

            # Second alert
            mock_stock2 = MagicMock(spec=Stock)
            mock_stock2.ticker = "VALE3"
            mock_stock2.companyname = "Vale"
            mock_stock2.price = 32.0

            mock_fav2 = MagicMock(spec=Favorite)
            mock_fav2.stock = mock_stock2
            mock_fav2.ceiling_price = 40.0
            mock_fav2.target_price = None

            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = [mock_fav1, mock_fav2]

                result, status_code = get_price_alerts(user_id=1)

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 2
                assert result_data[0]["ticker"] == "PETR4"
                assert result_data[0]["discount_to_ceiling_percent"] == 20.0
                assert result_data[1]["ticker"] == "VALE3"
                assert result_data[1]["discount_to_ceiling_percent"] == 20.0

    def test_get_price_alerts_precision_rounding(self, app):
        """Test discount calculation is rounded to 2 decimal places"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "ABEV3"
            mock_stock.companyname = "Ambev"
            mock_stock.price = 13.33

            mock_fav = MagicMock(spec=Favorite)
            mock_fav.stock = mock_stock
            mock_fav.ceiling_price = 15.5
            mock_fav.target_price = None

            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = [mock_fav]

                result, status_code = get_price_alerts(user_id=4)

                assert status_code == 200
                result_data = result.get_json()
                # (15.5 - 13.33) / 15.5 * 100 = 13.99...% -> rounded to 13.99
                discount = result_data[0]["discount_to_ceiling_percent"]
                assert isinstance(discount, float)
                # Check it's rounded to 2 decimals
                assert discount == round(((15.5 - 13.33) / 15.5) * 100, 2)

    def test_get_price_alerts_db_error_on_query(self, app):
        """Test get_price_alerts handles database errors gracefully"""
        with app.app_context():
            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_query.join.side_effect = Exception("Database connection error")

                result, status_code = get_price_alerts(user_id=1)

                assert status_code == 500
                result_data = result.get_json()
                assert (
                    result_data["message"]
                    == "An error occurred, please try again later"
                )

    def test_get_price_alerts_db_error_on_filter(self, app):
        """Test get_price_alerts handles filter errors"""
        with app.app_context():
            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.side_effect = Exception("Filter error")

                result, status_code = get_price_alerts(user_id=1)

                assert status_code == 500
                result_data = result.get_json()
                assert (
                    result_data["message"]
                    == "An error occurred, please try again later"
                )

    def test_get_price_alerts_preserves_all_fields(self, app):
        """Test get_price_alerts includes all expected fields in response"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "MGLU3"
            mock_stock.companyname = "Magazine Luiza"
            mock_stock.price = 5.0

            mock_fav = MagicMock(spec=Favorite)
            mock_fav.stock = mock_stock
            mock_fav.ceiling_price = 7.5
            mock_fav.target_price = 6.0

            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = [mock_fav]

                result, status_code = get_price_alerts(user_id=5)

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1

                alert = result_data[0]
                expected_fields = {
                    "ticker",
                    "companyname",
                    "current_price",
                    "ceiling_price",
                    "target_price",
                    "discount_to_ceiling_percent",
                }
                assert set(alert.keys()) == expected_fields

    def test_get_price_alerts_zero_discount(self, app):
        """Test discount calculation when price equals ceiling (0% discount)"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "GOLL4"
            mock_stock.companyname = "Gol"
            mock_stock.price = 10.0

            mock_fav = MagicMock(spec=Favorite)
            mock_fav.stock = mock_stock
            mock_fav.ceiling_price = 10.0
            mock_fav.target_price = None

            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = [mock_fav]

                result, status_code = get_price_alerts(user_id=6)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data[0]["discount_to_ceiling_percent"] == 0.0

    def test_get_price_alerts_by_user_id(self, app):
        """Test get_price_alerts correctly filters by user_id"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "PETR4"
            mock_stock.companyname = "Petrobras"
            mock_stock.price = 24.0

            mock_fav = MagicMock(spec=Favorite)
            mock_fav.stock = mock_stock
            mock_fav.ceiling_price = 30.0
            mock_fav.target_price = None

            with patch("services.favorite_services.Favorite.query") as mock_query:
                mock_chain = MagicMock()
                mock_query.join.return_value = mock_chain
                mock_chain.filter.return_value = mock_chain
                mock_chain.all.return_value = [mock_fav]

                # Call with specific user_id
                result, status_code = get_price_alerts(user_id=42)

                # Verify the query was called with the correct filter conditions
                mock_query.join.assert_called_once()
                mock_chain.filter.assert_called_once()

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1
