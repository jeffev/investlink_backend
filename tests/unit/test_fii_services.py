import sys
import os
from unittest.mock import patch

# Ensure the app folder is on sys.path so imports match runtime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.fii import FII  # noqa: E402


@patch("services.fii_services.FII.query")
@patch("services.fii_services.Favorite_FII.query")
@patch("services.fii_services.db.session")
def test_list_fiis_returns_all_fiis(mock_session, mock_fav_query, mock_query):
    """Test list_fiis returns all FIIs with favorita flag"""
    from services.fii_services import list_fiis

    fii1 = FII(ticker="KNRI11", name="Knewin", price=100.0)
    fii2 = FII(ticker="XPML11", name="XP Malls", price=80.0)
    mock_query.all.return_value = [fii1, fii2]
    mock_fav_query.filter_by.return_value.all.return_value = []

    response = list_fiis(user_id=1)
    data = response.get_json()

    assert len(data) == 2
    assert data[0]["ticker"] == "KNRI11"
    assert data[1]["ticker"] == "XPML11"


@patch("services.fii_services.FII.query")
@patch("services.fii_services.db.session")
def test_view_fii_with_valid_ticker(mock_session, mock_query):
    """Test view_fii returns FII data when exists"""
    from services.fii_services import view_fii

    fii = FII(ticker="KNRI11", name="Knewin", price=100.0)
    mock_query.get.return_value = fii

    response = view_fii("KNRI11")
    data = response.get_json()

    assert data["ticker"] == "KNRI11"
    assert data["name"] == "Knewin"


@patch("services.fii_services.FII.query")
@patch("services.fii_services.db.session")
def test_view_fii_returns_404_when_not_found(mock_session, mock_query):
    """Test view_fii returns 404 when FII doesn't exist"""
    from services.fii_services import view_fii

    mock_query.get.return_value = None

    response = view_fii("INVALID")
    status = response[1]

    assert status == 404


@patch("services.fii_services.FII.query")
@patch("services.fii_services.db.session")
def test_new_fii_rejects_duplicate_ticker(mock_session, mock_query):
    """Test new_fii returns 400 when ticker already exists"""
    from services.fii_services import new_fii

    existing_fii = FII(ticker="KNRI11", name="Knewin", price=100.0)
    mock_query.filter_by.return_value.first.return_value = existing_fii

    fii_data = {
        "ticker": "KNRI11",
        "name": "Knewin",
        "price": 101.0,
    }

    response = new_fii(fii_data)
    status = response[1]

    assert status == 400
    assert "already exists" in response[0].get_json()["message"]


@patch("services.fii_services.FII.query")
@patch("services.fii_services.db.session")
def test_delete_fii_returns_404_when_not_found(mock_session, mock_query):
    """Test delete_fii returns 404 when FII doesn't exist"""
    from services.fii_services import delete_fii

    mock_query.get.return_value = None

    response = delete_fii("INVALID")
    status = response[1]

    assert status == 404


def test_fii_to_json_contains_expected_fields():
    """Test FII.to_json() returns expected fields"""
    fii = FII(
        ticker="KNRI11",
        name="Knewin",
        price=100.0,
        dy=0.05,
        p_vp=1.2,
    )

    json = fii.to_json()

    assert json["ticker"] == "KNRI11"
    assert json["name"] == "Knewin"
    assert json["price"] == 100.0
    assert json["dy"] == 0.05
