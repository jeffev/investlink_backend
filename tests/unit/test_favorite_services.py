import pytest
from unittest.mock import patch, MagicMock
from services.favorite_services import (
    list_favorites,
    view_favorite,
    new_favorite,
    edit_favorite,
    delete_favorite,
    add_favorite,
    remove_favorite,
)
from models.favorite import Favorite
from models.stock import Stock
from models.user import User


class TestFavoriteServices:

    def test_list_favorites_success(self, app, sample_favorite, sample_user):
        """Test successful listing of favorites"""
        with app.app_context():
            mock_favorite = MagicMock(spec=Favorite)
            mock_favorite.to_json.return_value = {
                "id": 1,
                "user_id": 1,
                "stock_ticker": "PETR4",
                "ceiling_price": 30.0,
                "target_price": 25.0,
            }

            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.filter_by.return_value.all.return_value = [
                    mock_favorite
                ]

                result, status_code = list_favorites(sample_user.id)

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1
                assert result_data[0]["stock_ticker"] == "PETR4"

    def test_list_favorites_empty(self, app):
        """Test listing favorites when no favorites exist"""
        with app.app_context():
            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.filter_by.return_value.all.return_value = []

                result, status_code = list_favorites(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data == []

    def test_list_favorites_with_exception(self, app):
        """Test listing favorites when an exception occurs"""
        with app.app_context():
            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.filter_by.side_effect = Exception("Database error")

                result, status_code = list_favorites(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in list_favorites" in result_data["message"]

    def test_view_favorite_success(self, app, sample_favorite):
        """Test viewing a specific favorite"""
        with app.app_context():
            mock_favorite = MagicMock(spec=Favorite)
            mock_favorite.to_json.return_value = {
                "id": 1,
                "user_id": 1,
                "stock_ticker": "PETR4",
                "ceiling_price": 30.0,
                "target_price": 25.0,
            }

            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.get.return_value = mock_favorite

                result, status_code = view_favorite(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["stock_ticker"] == "PETR4"

    def test_view_favorite_not_found(self, app):
        """Test viewing a favorite that doesn't exist"""
        with app.app_context():
            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.get.return_value = None

                result, status_code = view_favorite(999)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Favorite not found"

    def test_view_favorite_with_exception(self, app):
        """Test viewing a favorite when an exception occurs"""
        with app.app_context():
            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.get.side_effect = Exception("Database error")

                result, status_code = view_favorite(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in view_favorite" in result_data["message"]

    def test_new_favorite_success(self, app):
        """Test creating a new favorite"""
        with app.app_context():
            favorite_data = {
                "user_id": 1,
                "stock_ticker": "PETR4",
                "ceiling_price": 30.0,
                "target_price": 25.0,
            }

            with (
                patch("services.favorite_services.User.query") as mock_user_query,
                patch("services.favorite_services.Stock.query") as mock_stock_query,
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_user_query.get.return_value = MagicMock()
                mock_stock_query.get.return_value = MagicMock()
                mock_favorite_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()

                result, status_code = new_favorite(favorite_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "Favorite added successfully"

    def test_new_favorite_user_not_found(self, app):
        """Test creating a favorite with non-existent user"""
        with app.app_context():
            favorite_data = {
                "user_id": 999,
                "stock_ticker": "PETR4",
                "ceiling_price": 30.0,
                "target_price": 25.0,
            }

            with patch("services.favorite_services.User.query") as mock_user_query:
                mock_user_query.get.return_value = None

                result, status_code = new_favorite(favorite_data)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "User not found"

    def test_new_favorite_stock_not_found(self, app):
        """Test creating a favorite with non-existent stock"""
        with app.app_context():
            favorite_data = {
                "user_id": 1,
                "stock_ticker": "INVALID",
                "ceiling_price": 30.0,
                "target_price": 25.0,
            }

            with (
                patch("services.favorite_services.User.query") as mock_user_query,
                patch("services.favorite_services.Stock.query") as mock_stock_query,
            ):

                mock_user_query.get.return_value = MagicMock()
                mock_stock_query.get.return_value = None

                result, status_code = new_favorite(favorite_data)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Stock not found"

    def test_new_favorite_already_exists(self, app):
        """Test creating a favorite that already exists"""
        with app.app_context():
            favorite_data = {
                "user_id": 1,
                "stock_ticker": "PETR4",
                "ceiling_price": 30.0,
                "target_price": 25.0,
            }

            with (
                patch("services.favorite_services.User.query") as mock_user_query,
                patch("services.favorite_services.Stock.query") as mock_stock_query,
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
            ):

                mock_user_query.get.return_value = MagicMock()
                mock_stock_query.get.return_value = MagicMock()
                mock_favorite_query.filter_by.return_value.first.return_value = (
                    MagicMock()
                )

                result, status_code = new_favorite(favorite_data)

                assert status_code == 400
                result_data = result.get_json()
                assert (
                    result_data["message"]
                    == "This stock is already favorited by this user"
                )

    def test_new_favorite_with_exception(self, app):
        """Test creating a favorite when an exception occurs"""
        with app.app_context():
            favorite_data = {
                "user_id": 1,
                "stock_ticker": "PETR4",
                "ceiling_price": 30.0,
                "target_price": 25.0,
            }

            with (
                patch("services.favorite_services.User.query") as mock_user_query,
                patch("services.favorite_services.Stock.query") as mock_stock_query,
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_user_query.get.return_value = MagicMock()
                mock_stock_query.get.return_value = MagicMock()
                mock_favorite_query.filter_by.return_value.first.return_value = None
                mock_db_session.add.side_effect = Exception("Database error")

                result, status_code = new_favorite(favorite_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in new_favorite" in result_data["message"]

    def test_edit_favorite_success(self, app):
        """Test editing an existing favorite"""
        with app.app_context():
            favorite_data = {"ceiling_price": 35.0, "target_price": 28.0}

            mock_favorite = MagicMock(spec=Favorite)

            with (
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_favorite_query.get.return_value = mock_favorite
                mock_db_session.commit = MagicMock()

                result, status_code = edit_favorite(1, favorite_data)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Favorite edited successfully"

                # Verify that the attributes were set
                for key, value in favorite_data.items():
                    assert getattr(mock_favorite, key) == value

    def test_edit_favorite_not_found(self, app):
        """Test editing a favorite that doesn't exist"""
        with app.app_context():
            favorite_data = {"ceiling_price": 35.0}

            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.get.return_value = None

                result, status_code = edit_favorite(999, favorite_data)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Favorite not found"

    def test_edit_favorite_with_exception(self, app):
        """Test editing a favorite when an exception occurs"""
        with app.app_context():
            favorite_data = {"ceiling_price": 35.0}

            with (
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_favorite_query.get.return_value = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")

                result, status_code = edit_favorite(1, favorite_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in edit_favorite" in result_data["message"]

    def test_delete_favorite_success(self, app):
        """Test deleting an existing favorite"""
        with app.app_context():
            mock_favorite = MagicMock(spec=Favorite)

            with (
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_favorite_query.get.return_value = mock_favorite
                mock_db_session.delete = MagicMock()

                result, status_code = delete_favorite(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Favorite deleted successfully"

    def test_delete_favorite_not_found(self, app):
        """Test deleting a favorite that doesn't exist"""
        with app.app_context():
            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.get.return_value = None

                result, status_code = delete_favorite(999)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Favorite not found"

    def test_delete_favorite_with_exception(self, app):
        """Test deleting a favorite when an exception occurs"""
        with app.app_context():
            with (
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_favorite_query.get.return_value = MagicMock()
                mock_db_session.delete.side_effect = Exception("Database error")

                result, status_code = delete_favorite(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in delete_favorite" in result_data["message"]

    def test_add_favorite_success(self, app):
        """Test adding a favorite"""
        with app.app_context():
            with (
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_favorite_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()

                result, status_code = add_favorite(1, "PETR4")

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "Favorite added successfully"

    def test_add_favorite_already_exists(self, app):
        """Test adding a favorite that already exists"""
        with app.app_context():
            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.filter_by.return_value.first.return_value = (
                    MagicMock()
                )

                result, status_code = add_favorite(1, "PETR4")

                assert status_code == 400
                result_data = result.get_json()
                assert (
                    result_data["message"]
                    == "This stock is already favorited by this user"
                )

    def test_add_favorite_with_exception(self, app):
        """Test adding a favorite when an exception occurs"""
        with app.app_context():
            with (
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_favorite_query.filter_by.return_value.first.return_value = None
                mock_db_session.add.side_effect = Exception("Database error")

                result, status_code = add_favorite(1, "PETR4")

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in add_favorite" in result_data["message"]

    def test_remove_favorite_success(self, app):
        """Test removing a favorite"""
        with app.app_context():
            mock_favorite = MagicMock(spec=Favorite)

            with (
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_favorite_query.filter_by.return_value.first.return_value = (
                    mock_favorite
                )
                mock_db_session.delete = MagicMock()

                result, status_code = remove_favorite(1, "PETR4")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Favorite deleted successfully"

    def test_remove_favorite_not_found(self, app):
        """Test removing a favorite that doesn't exist"""
        with app.app_context():
            with patch(
                "services.favorite_services.Favorite.query"
            ) as mock_favorite_query:
                mock_favorite_query.filter_by.return_value.first.return_value = None

                result, status_code = remove_favorite(1, "INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Favorite not found"

    def test_remove_favorite_with_exception(self, app):
        """Test removing a favorite when an exception occurs"""
        with app.app_context():
            with (
                patch(
                    "services.favorite_services.Favorite.query"
                ) as mock_favorite_query,
                patch("services.favorite_services.db.session") as mock_db_session,
            ):

                mock_favorite_query.filter_by.return_value.first.return_value = (
                    MagicMock()
                )
                mock_db_session.delete.side_effect = Exception("Database error")

                result, status_code = remove_favorite(1, "PETR4")

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in remove_favorite" in result_data["message"]
