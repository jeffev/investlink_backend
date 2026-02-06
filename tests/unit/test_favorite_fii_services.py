import sys
import os
from unittest.mock import Mock, patch

# Ensure the app folder is on sys.path so imports match runtime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.favorite_fiis import Favorite_FII  # noqa: E402
from models.user import User  # noqa: E402
from models.fii import FII  # noqa: E402


@patch("services.favorite_fii_services.Favorite_FII.query")
@patch("services.favorite_fii_services.db.session")
def test_list_favorite_fiis_returns_user_favorites(mock_session, mock_query):
    """Test list_favorite_fiis returns favorites for specific user"""
    from services.favorite_fii_services import list_favorite_fiis

    fav1 = Favorite_FII(
        id=1,
        user_id=1,
        fii_ticker="KNRI11",
        ceiling_price=110.0,
        target_price=100.0,
    )
    fav2 = Favorite_FII(
        id=2,
        user_id=1,
        fii_ticker="XPML11",
        ceiling_price=85.0,
        target_price=75.0,
    )
    mock_query.filter_by.return_value.all.return_value = [fav1, fav2]

    response = list_favorite_fiis(user_id=1)
    data = response.get_json()

    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[1]["id"] == 2


@patch("services.favorite_fii_services.Favorite_FII.query")
@patch("services.favorite_fii_services.db.session")
def test_view_favorite_fii_returns_404_when_not_found(mock_session, mock_query):
    """Test view_favorite_fii returns 404 when favorite doesn't exist"""
    from services.favorite_fii_services import view_favorite_fii

    mock_query.get.return_value = None

    response = view_favorite_fii(999)
    status = response[1]

    assert status == 404


@patch("services.favorite_fii_services.User.query")
@patch("services.favorite_fii_services.FII.query")
@patch("services.favorite_fii_services.Favorite_FII.query")
@patch("services.favorite_fii_services.db.session")
def test_new_favorite_fii_validates_user_exists(
    mock_session, mock_fav_query, mock_fii_query, mock_user_query
):
    """Test new_favorite_fii returns 404 when user doesn't exist"""
    from services.favorite_fii_services import new_favorite_fii

    mock_user_query.get.return_value = None

    fav_data = {
        "user_id": 999,
        "fii_ticker": "KNRI11",
        "ceiling_price": 110.0,
        "target_price": 100.0,
    }

    response = new_favorite_fii(fav_data)
    status = response[1]

    assert status == 404


@patch("services.favorite_fii_services.User.query")
@patch("services.favorite_fii_services.FII.query")
@patch("services.favorite_fii_services.Favorite_FII.query")
@patch("services.favorite_fii_services.db.session")
def test_new_favorite_fii_validates_fii_exists(
    mock_session, mock_fav_query, mock_fii_query, mock_user_query
):
    """Test new_favorite_fii returns 404 when FII doesn't exist"""
    from services.favorite_fii_services import new_favorite_fii

    user = User(
        id=1, user_name="john", name="John", email="j@example.com", profile="USER"
    )
    mock_user_query.get.return_value = user
    mock_fii_query.get.return_value = None

    fav_data = {
        "user_id": 1,
        "fii_ticker": "INVALID",
        "ceiling_price": 110.0,
        "target_price": 100.0,
    }

    response = new_favorite_fii(fav_data)
    status = response[1]

    assert status == 404


@patch("services.favorite_fii_services.Favorite_FII.query")
@patch("services.favorite_fii_services.db.session")
def test_delete_favorite_fii_returns_404_when_not_found(mock_session, mock_query):
    """Test delete_favorite_fii returns 404 when favorite doesn't exist"""
    from services.favorite_fii_services import delete_favorite_fii

    mock_query.get.return_value = None

    response = delete_favorite_fii(999)
    status = response[1]

    assert status == 404


def test_favorite_fii_to_json_contains_expected_fields():
    """Test Favorite_FII.to_json() returns expected fields"""
    fii = FII(ticker="KNRI11", name="Knewin", price=100.0)
    favorite = Favorite_FII(
        id=1,
        user_id=1,
        fii_ticker="KNRI11",
        ceiling_price=110.0,
        target_price=100.0,
    )
    favorite.fii = fii

    json = favorite.to_json()

    assert json["id"] == 1
    assert json["user_id"] == 1
    assert json["ceiling_price"] == 110.0
    assert json["target_price"] == 100.0
