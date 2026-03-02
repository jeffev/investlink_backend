import pytest
from unittest.mock import patch, MagicMock
from services.user_layout_service import (
    get_user_layout,
    save_user_layout,
    delete_user_layout,
)
from models.user_layout import UserLayout


class TestUserLayoutService:

    def test_get_user_layout_with_layout_success(self, app, sample_layout, sample_user):
        """Test getting a specific user layout"""
        with app.app_context():
            mock_layout = MagicMock(spec=UserLayout)
            mock_layout.estado = {
                "layout": "Default",
                "columns": ["ticker", "price"],
                "sorting": ["ticker"],
            }

            with (
                patch(
                    "services.user_layout_service.UserLayout.query"
                ) as mock_layout_query,
                patch("services.user_layout_service.db"),
            ):
                mock_layout_query.filter_by.return_value.first.return_value = (
                    mock_layout
                )

                result, status_code = get_user_layout(sample_user.id, "Default")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["layout"] == "Default"

    def test_get_user_layout_with_layout_not_found(self, app):
        """Test getting a specific user layout that doesn't exist"""
        with app.app_context():
            with patch(
                "services.user_layout_service.UserLayout.query"
            ) as mock_layout_query:
                mock_layout_query.filter_by.return_value.first.return_value = None

                result, status_code = get_user_layout(1, "NonExistent")

                assert status_code == 400
                result_data = result.get_json()
                assert result_data is None

    def test_get_user_layout_without_layout_success(
        self, app, sample_layout, sample_user
    ):
        """Test getting all user layouts"""
        with app.app_context():
            mock_layout = MagicMock(spec=UserLayout)
            mock_layout.to_json.return_value = {
                "id": 1,
                "user_id": 1,
                "layout": "Default",
                "estado": {"columns": ["ticker", "price"], "sorting": ["ticker"]},
            }

            with patch(
                "services.user_layout_service.UserLayout.query"
            ) as mock_layout_query:
                mock_layout_query.filter_by.return_value.all.return_value = [
                    mock_layout
                ]

                result, status_code = get_user_layout(sample_user.id)

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1
                assert result_data[0]["layout"] == "Default"

    def test_get_user_layout_without_layout_empty(self, app):
        """Test getting all user layouts when none exist"""
        with app.app_context():
            with patch(
                "services.user_layout_service.UserLayout.query"
            ) as mock_layout_query:
                mock_layout_query.filter_by.return_value.all.return_value = []

                result, status_code = get_user_layout(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data == []

    def test_get_user_layout_with_exception(self, app):
        """Test getting user layout when an exception occurs"""
        with app.app_context():
            with patch(
                "services.user_layout_service.UserLayout.query"
            ) as mock_layout_query:
                mock_layout_query.filter_by.side_effect = Exception("Database error")

                result, status_code = get_user_layout(1, "Default")

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in get_user_layout" in result_data["message"]

    def test_save_user_layout_new_success(self, app):
        """Test saving a new user layout"""
        with app.app_context():
            layout_data = {"columns": ["ticker", "price", "dy"], "sorting": ["ticker"]}

            with (
                patch(
                    "services.user_layout_service.UserLayout.query"
                ) as mock_layout_query,
                patch("services.user_layout_service.db.session") as mock_db_session,
            ):

                mock_layout_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()

                result, status_code = save_user_layout(1, "NewLayout", layout_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "User layout added successfully"

    def test_save_user_layout_update_success(self, app):
        """Test updating an existing user layout"""
        with app.app_context():
            layout_data = {"columns": ["ticker", "price", "dy"], "sorting": ["ticker"]}

            mock_layout = MagicMock(spec=UserLayout)

            with (
                patch(
                    "services.user_layout_service.UserLayout.query"
                ) as mock_layout_query,
                patch("services.user_layout_service.db.session") as mock_db_session,
            ):

                mock_layout_query.filter_by.return_value.first.return_value = (
                    mock_layout
                )
                mock_db_session.commit = MagicMock()

                result, status_code = save_user_layout(1, "Default", layout_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "User layout updated successfully"

                # Verify that the estado was updated
                assert mock_layout.estado == layout_data

    def test_save_user_layout_with_exception(self, app):
        """Test saving user layout when an exception occurs"""
        with app.app_context():
            layout_data = {"columns": ["ticker", "price"], "sorting": ["ticker"]}

            with (
                patch(
                    "services.user_layout_service.UserLayout.query"
                ) as mock_layout_query,
                patch("services.user_layout_service.db.session") as mock_db_session,
            ):

                mock_layout_query.filter_by.return_value.first.return_value = None
                mock_db_session.add.side_effect = Exception("Database error")

                result, status_code = save_user_layout(1, "TestLayout", layout_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in save_user_layout" in result_data["message"]

    def test_delete_user_layout_success(self, app):
        """Test deleting an existing user layout"""
        with app.app_context():
            mock_layout = MagicMock(spec=UserLayout)

            with (
                patch(
                    "services.user_layout_service.UserLayout.query"
                ) as mock_layout_query,
                patch("services.user_layout_service.db.session") as mock_db_session,
            ):

                mock_layout_query.get.return_value = mock_layout
                mock_db_session.delete = MagicMock()

                result, status_code = delete_user_layout(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Layout deleted successfully"

    def test_delete_user_layout_not_found(self, app):
        """Test deleting a user layout that doesn't exist"""
        with app.app_context():
            with patch(
                "services.user_layout_service.UserLayout.query"
            ) as mock_layout_query:
                mock_layout_query.get.return_value = None

                result, status_code = delete_user_layout(999)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Layout not found"

    def test_delete_user_layout_with_exception(self, app):
        """Test deleting user layout when an exception occurs"""
        with app.app_context():
            with (
                patch(
                    "services.user_layout_service.UserLayout.query"
                ) as mock_layout_query,
                patch("services.user_layout_service.db.session") as mock_db_session,
            ):

                mock_layout_query.get.return_value = MagicMock()
                mock_db_session.delete.side_effect = Exception("Database error")

                result, status_code = delete_user_layout(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error in delete_user_layout" in result_data["message"]
