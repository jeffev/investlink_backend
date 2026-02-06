import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Ensure the app folder is on sys.path so imports match runtime
ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "app")
)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.user import User  # noqa: E402
from services.user_services import (  # noqa: E402
    validate_email,
    validate_username,
)


def test_validate_email_with_valid_format():
    """Test email validation with valid email format"""
    assert validate_email("user@example.com") is True
    assert validate_email("john.doe@company.co.uk") is True
    assert validate_email("test+tag@domain.com") is True


def test_validate_email_with_invalid_format():
    """Test email validation with invalid email formats"""
    assert validate_email("invalid.email") is False
    assert validate_email("@example.com") is False
    assert validate_email("user@") is False
    assert validate_email("user@@example.com") is False


def test_validate_username_with_valid_format():
    """Test username validation with valid format (3+ chars, alphanumeric)"""
    assert validate_username("john") is True
    assert validate_username("user123") is True
    assert validate_username("abc") is True


def test_validate_username_with_invalid_format():
    """Test username validation with invalid format (too short or special chars)"""
    assert validate_username("ab") is False
    assert validate_username("user@name") is False
    assert validate_username("user-name") is False
    assert validate_username("") is False


def test_validate_username_with_special_characters():
    """Test username validation rejects special characters"""
    assert validate_username("user!") is False
    assert validate_username("user#name") is False
    assert validate_username("user name") is False


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_list_users_returns_jsonified_list(mock_session, mock_query):
    """Test list_users returns all users as JSON list"""
    from services.user_services import list_users

    user1 = User(
        id=1, user_name="john", name="John", email="j@example.com", profile="USER"
    )
    user2 = User(
        id=2, user_name="jane", name="Jane", email="ja@example.com", profile="USER"
    )
    mock_query.all.return_value = [user1, user2]

    response = list_users()
    data = response.get_json()

    assert len(data) == 2
    assert data[0]["user_name"] == "john"
    assert data[1]["user_name"] == "jane"


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_view_user_with_valid_id(mock_session, mock_query):
    """Test view_user returns user data when user exists"""
    from services.user_services import view_user

    user = User(
        id=1, user_name="john", name="John", email="j@example.com", profile="USER"
    )
    mock_query.get.return_value = user

    response = view_user(1)
    data = response.get_json()

    assert data["user_name"] == "john"
    assert data["email"] == "j@example.com"


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_view_user_returns_404_when_not_found(mock_session, mock_query):
    """Test view_user returns 404 when user doesn't exist"""
    from services.user_services import view_user

    mock_query.get.return_value = None

    response = view_user(999)
    status = response[1]

    assert status == 404


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_new_user_validates_email_required(mock_session, mock_query):
    """Test new_user returns 400 when email is missing"""
    from services.user_services import new_user

    user_data = {
        "user_name": "john",
        "name": "John",
        "password": "secure123",
    }

    response = new_user(user_data)
    status = response[1]

    assert status == 400
    assert "Email is required" in response[0].get_json()["message"]


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_new_user_validates_username_required(mock_session, mock_query):
    """Test new_user returns 400 when username is missing"""
    from services.user_services import new_user

    user_data = {
        "name": "John",
        "email": "j@example.com",
        "password": "secure123",
    }

    response = new_user(user_data)
    status = response[1]

    assert status == 400
    assert "User name is required" in response[0].get_json()["message"]


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_new_user_validates_email_format(mock_session, mock_query):
    """Test new_user validates email format"""
    from services.user_services import new_user

    user_data = {
        "user_name": "john",
        "name": "John",
        "email": "invalid-email",
        "password": "secure123",
    }

    response = new_user(user_data)
    status = response[1]

    assert status == 400
    assert "Invalid email format" in response[0].get_json()["message"]


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_new_user_validates_username_format(mock_session, mock_query):
    """Test new_user validates username format"""
    from services.user_services import new_user

    user_data = {
        "user_name": "ab",  # too short
        "name": "John",
        "email": "j@example.com",
        "password": "secure123",
    }

    response = new_user(user_data)
    status = response[1]

    assert status == 400
    assert "Invalid username format" in response[0].get_json()["message"]


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_new_user_rejects_duplicate_username(mock_session, mock_query):
    """Test new_user returns 400 when username already exists"""
    from services.user_services import new_user

    existing_user = User(
        id=1, user_name="john", name="John", email="j@example.com", profile="USER"
    )
    mock_query.filter_by.return_value.first.return_value = existing_user

    user_data = {
        "user_name": "john",
        "name": "John",
        "email": "newj@example.com",
        "password": "secure123",
    }

    response = new_user(user_data)
    status = response[1]

    assert status == 400
    assert "User already exists" in response[0].get_json()["message"]


@patch("services.user_services.User.query")
@patch("services.user_services.db.session")
def test_delete_user_returns_404_when_not_found(mock_session, mock_query):
    """Test delete_user returns 404 when user doesn't exist"""
    from services.user_services import delete_user

    mock_query.get.return_value = None

    response = delete_user(999)
    status = response[1]

    assert status == 404
