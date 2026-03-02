from unittest.mock import patch, MagicMock
from services.fii_services import (
    list_fiis,
    view_fii,
    new_fii,
    edit_fii,
    delete_fii,
    get_all_fiis_from_statusinvest,
    update_all_fiis,
)
from models.fii import Fii
from models.favorite_fiis import FavoriteFii


class TestFiiServices:

    def test_list_fiis_success(self, app, sample_user):
        """Test successful listing of FIIs with favorites"""
        with app.app_context():
            mock_fii = MagicMock(spec=Fii)
            mock_fii.ticker = "KNRI11"
            mock_fii.to_json.return_value = {
                "ticker": "KNRI11",
                "name": "Knewin",
                "price": 100.0,
                "dy": 0.06,
                "p_vp": 1.2,
            }

            mock_favorite = MagicMock(spec=FavoriteFii)
            mock_favorite.fii_ticker = "KNRI11"

            mock_paginated = MagicMock()
            mock_paginated.items = [mock_fii]
            mock_paginated.total = 1
            mock_paginated.pages = 1
            mock_paginated.page = 1

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.FavoriteFii.query") as mock_favorite_query,
            ):

                mock_fii_query.paginate.return_value = mock_paginated
                mock_favorite_query.filter_by.return_value.all.return_value = [
                    mock_favorite
                ]

                result, status_code = list_fiis(sample_user.id)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["pagination"]["total"] == 1
                assert result_data["pagination"]["current_page"] == 1
                assert len(result_data["data"]) == 1
                assert result_data["data"][0]["ticker"] == "KNRI11"
                assert result_data["data"][0]["favorita"] is True

    def test_list_fiis_empty(self, app):
        """Test listing FIIs when no FIIs exist"""
        with app.app_context():
            mock_paginated = MagicMock()
            mock_paginated.items = []
            mock_paginated.total = 0
            mock_paginated.pages = 0
            mock_paginated.page = 1

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.FavoriteFii.query") as mock_favorite_query,
            ):

                mock_fii_query.paginate.return_value = mock_paginated
                mock_favorite_query.filter_by.return_value.all.return_value = []

                result, status_code = list_fiis(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["data"] == []
                assert result_data["pagination"]["total"] == 0

    def test_list_fiis_with_exception(self, app):
        """Test listing FIIs when an exception occurs"""
        with app.app_context():
            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.FavoriteFii.query") as mock_favorite_query,
            ):
                mock_favorite_query.filter_by.return_value.all.return_value = []
                mock_fii_query.paginate.side_effect = Exception("Database error")

                result, status_code = list_fiis(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_view_fii_success(self, app, sample_fii):
        """Test viewing a specific FII"""
        with app.app_context():
            mock_fii = MagicMock(spec=Fii)
            mock_fii.to_json.return_value = {
                "ticker": "KNRI11",
                "name": "Knewin",
                "price": 100.0,
                "dy": 0.06,
                "p_vp": 1.2,
            }

            with patch("services.fii_services.Fii.query") as mock_fii_query:
                mock_fii_query.get.return_value = mock_fii

                result, status_code = view_fii("KNRI11")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["ticker"] == "KNRI11"

    def test_view_fii_not_found(self, app):
        """Test viewing a FII that doesn't exist"""
        with app.app_context():
            with patch("services.fii_services.Fii.query") as mock_fii_query:
                mock_fii_query.get.return_value = None

                result, status_code = view_fii("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "FII not found"

    def test_view_fii_with_exception(self, app):
        """Test viewing a FII when an exception occurs"""
        with app.app_context():
            with patch("services.fii_services.Fii.query") as mock_fii_query:
                mock_fii_query.get.side_effect = Exception("Database error")

                result, status_code = view_fii("KNRI11")

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_new_fii_success(self, app, mock_db_session):
        """Test creating a new FII"""
        with app.app_context():
            fii_data = {
                "ticker": "NEWFII11",
                "name": "New FII",
                "price": 50.0,
                "dy": 0.08,
                "p_vp": 1.0,
            }

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.FavoriteFii.query"),
                patch("services.fii_services.db") as mock_db,
            ):

                mock_fii_query.filter_by.return_value.first.return_value = None
                mock_db.session = mock_db_session

                result, status_code = new_fii(fii_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "FII added successfully"

    def test_new_fii_already_exists(self, app):
        """Test creating a FII that already exists"""
        with app.app_context():
            fii_data = {
                "ticker": "EXISTING11",
                "name": "Existing FII",
                "price": 50.0,
                "dy": 0.08,
                "p_vp": 1.0,
            }

            with patch("services.fii_services.Fii.query") as mock_fii_query:
                mock_fii_query.filter_by.return_value.first.return_value = MagicMock()

                result, status_code = new_fii(fii_data)

                assert status_code == 400
                result_data = result.get_json()
                assert result_data["message"] == "FII already exists"

    def test_new_fii_with_exception(self, app):
        """Test creating a FII when an exception occurs"""
        with app.app_context():
            fii_data = {
                "ticker": "ERRORFII11",
                "name": "Error FII",
                "price": 50.0,
                "dy": 0.08,
                "p_vp": 1.0,
            }

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = new_fii(fii_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_edit_fii_success(self, app):
        """Test editing an existing FII"""
        with app.app_context():
            fii_data = {"name": "Updated FII", "price": 60.0, "dy": 0.09}

            mock_fii = MagicMock(spec=Fii)

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.get.return_value = mock_fii
                mock_db_session.commit = MagicMock()

                result, status_code = edit_fii("KNRI11", fii_data)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "FII edited successfully"

                # Verify that the attributes were set
                for key, value in fii_data.items():
                    assert getattr(mock_fii, key) == value

    def test_edit_fii_not_found(self, app):
        """Test editing a FII that doesn't exist"""
        with app.app_context():
            fii_data = {"name": "Updated FII"}

            with patch("services.fii_services.Fii.query") as mock_fii_query:
                mock_fii_query.get.return_value = None

                result, status_code = edit_fii("INVALID", fii_data)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "FII not found"

    def test_edit_fii_with_exception(self, app):
        """Test editing a FII when an exception occurs"""
        with app.app_context():
            fii_data = {"name": "Updated FII"}

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.get.return_value = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = edit_fii("KNRI11", fii_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_delete_fii_success(self, app):
        """Test deleting an existing FII"""
        with app.app_context():
            mock_fii = MagicMock(spec=Fii)

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.get.return_value = mock_fii
                mock_db_session.delete = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = delete_fii("KNRI11")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "FII deleted successfully"

    def test_delete_fii_not_found(self, app):
        """Test deleting a FII that doesn't exist"""
        with app.app_context():
            with patch("services.fii_services.Fii.query") as mock_fii_query:
                mock_fii_query.get.return_value = None

                result, status_code = delete_fii("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "FII not found"

    def test_delete_fii_with_exception(self, app):
        """Test deleting a FII when an exception occurs"""
        with app.app_context():
            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.get.return_value = MagicMock()
                mock_db_session.delete = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = delete_fii("KNRI11")

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    @patch("services.fii_services.requests.get")
    def test_get_all_fiis_from_statusinvest_success(self, mock_get):
        """Test successful retrieval of FIIs from StatusInvest"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [
                {
                    "ticker": "KNRI11",
                    "name": "Knewin",
                    "price": 100.0,
                    "dy": 0.06,
                    "p_vp": 1.2,
                }
            ]
        }
        mock_get.return_value = mock_response

        result = get_all_fiis_from_statusinvest()

        assert result is not None
        assert "list" in result
        assert len(result["list"]) == 1
        assert result["list"][0]["ticker"] == "KNRI11"

    @patch("services.fii_services.requests.get")
    def test_get_all_fiis_from_statusinvest_http_error(self, mock_get):
        """Test retrieval of FIIs when HTTP error occurs"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_all_fiis_from_statusinvest()

        assert result is None

    @patch("services.fii_services.requests.get")
    def test_get_all_fiis_from_statusinvest_exception(self, mock_get):
        """Test retrieval of FIIs when an exception occurs"""
        mock_get.side_effect = Exception("Network error")

        result = get_all_fiis_from_statusinvest()

        assert result is None

    @patch("services.fii_services.get_all_fiis_from_statusinvest")
    def test_update_all_fiis_success(self, mock_get_fiis, app):
        """Test successful update of all FIIs"""
        with app.app_context():
            mock_fii_data = {
                "list": [
                    {
                        "ticker": "KNRI11",
                        "name": "Knewin",
                        "price": 100.0,
                        "dy": 0.06,
                        "p_vp": 1.2,
                    }
                ]
            }

            mock_existing_fii = MagicMock(spec=Fii)
            mock_existing_fii.ticker = "KNRI11"

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_get_fiis.return_value = mock_fii_data
                mock_fii_query.filter.return_value.all.return_value = [
                    mock_existing_fii
                ]
                mock_db_session.add_all = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = update_all_fiis()

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "FIIs updated successfully."

    @patch("services.fii_services.get_all_fiis_from_statusinvest")
    def test_update_all_fiis_no_data(self, mock_get_fiis, app):
        """Test update of FIIs when no data is returned"""
        with app.app_context():
            mock_get_fiis.return_value = None

            result, status_code = update_all_fiis()

            assert status_code == 500
            result_data = result.get_json()
            assert "Error fetching FII data" in result_data["error"]

    @patch("services.fii_services.get_all_fiis_from_statusinvest")
    def test_update_all_fiis_with_exception(self, mock_get_fiis, app):
        """Test update of FIIs when an exception occurs"""
        with app.app_context():
            mock_get_fiis.return_value = {"list": []}

            with patch("services.fii_services.db.session") as mock_db_session:
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = update_all_fiis()

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]
