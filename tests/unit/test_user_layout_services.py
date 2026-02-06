import sys
import os
from unittest.mock import Mock, patch

# Ensure the app folder is on sys.path so imports match runtime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.user_layout import UserLayout  # noqa: E402
from models.user import User  # noqa: E402


def test_user_layout_to_json_contains_expected_fields():
    """Test UserLayout.to_json() returns expected fields"""
    layout = UserLayout(
        id=1,
        user_id=1,
        layout_name="Default",
        layout_config={"columns": ["ticker", "price"]},
    )

    json = layout.to_json()

    assert json["id"] == 1
    assert json["user_id"] == 1
    assert json["layout_name"] == "Default"


@patch('services.user_layout_service.UserLayout.query')
@patch('services.user_layout_service.db.session')
def test_get_user_layout_returns_user_layouts(mock_session, mock_query):
    """Test get_user_layout returns layouts for specific user"""
    from services.user_layout_service import get_user_layout

    layout1 = UserLayout(id=1, user_id=1, layout_name="Stocks", layout_config={})
    layout2 = UserLayout(id=2, user_id=1, layout_name="FIIs", layout_config={})
    mock_query.filter_by.return_value.all.return_value = [layout1, layout2]

    response = get_user_layout(user_id=1)
    data = response.get_json()

    assert len(data) == 2
    assert data[0]["layout_name"] == "Stocks"
    assert data[1]["layout_name"] == "FIIs"


@patch('services.user_layout_service.UserLayout.query')
@patch('services.user_layout_service.db.session')
def test_save_user_layout_creates_new_layout(mock_session, mock_query):
    """Test save_user_layout creates new layout when doesn't exist"""
    from services.user_layout_service import save_user_layout

    mock_query.filter_by.return_value.first.return_value = None

    layout_data = {
        "user_id": 1,
        "layout_name": "Custom",
        "layout_config": {"columns": ["ticker", "price", "dy"]},
    }

    response = save_user_layout(layout_data)
    status = response[1]

    assert status == 201 or status == 200


@patch('services.user_layout_service.UserLayout.query')
@patch('services.user_layout_service.db.session')
def test_save_user_layout_updates_existing_layout(mock_session, mock_query):
    """Test save_user_layout updates existing layout"""
    from services.user_layout_service import save_user_layout

    existing_layout = UserLayout(id=1, user_id=1, layout_name="Custom", layout_config={})
    mock_query.filter_by.return_value.first.return_value = existing_layout

    layout_data = {
        "user_id": 1,
        "layout_name": "Custom",
        "layout_config": {"columns": ["ticker", "price", "dy"]},
    }

    response = save_user_layout(layout_data)
    status = response[1]

    assert status == 200 or status == 201


@patch('services.user_layout_service.UserLayout.query')
@patch('services.user_layout_service.db.session')
def test_delete_user_layout_returns_404_when_not_found(mock_session, mock_query):
    """Test delete_user_layout returns 404 when layout doesn't exist"""
    from services.user_layout_service import delete_user_layout

    mock_query.get.return_value = None

    response = delete_user_layout(layout_id=999)
    status = response[1]

    assert status == 404
