from unittest.mock import patch, MagicMock
from services.user_services import (
    list_users,
    view_user,
    new_user,
    edit_user,
    delete_user,
    login_user,
    validate_email,
    validate_username,
)
from models.user import User


class TestUserServices:

    def test_list_users_success(self, app, sample_user):
        """Test successful listing of users"""
        with app.app_context():
            mock_user = MagicMock(spec=User)
            mock_user.to_json.return_value = {
                "id": 1,
                "user_name": "testuser",
                "name": "Test User",
                "email": "test@example.com",
                "profile": "USER",
            }

            with patch("services.user_services.User.query") as mock_user_query:
                mock_user_query.all.return_value = [mock_user]

                result, status_code = list_users()

                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1
                assert result_data[0]["user_name"] == "testuser"

    def test_list_users_empty(self, app):
        """Test listing users when no users exist"""
        with app.app_context():
            with patch("services.user_services.User.query") as mock_user_query:
                mock_user_query.all.return_value = []

                result, status_code = list_users()

                assert status_code == 200
                result_data = result.get_json()
                assert result_data == []

    def test_list_users_with_exception(self, app):
        """Test listing users when an exception occurs"""
        with app.app_context():
            with patch("services.user_services.User.query") as mock_user_query:
                mock_user_query.all.side_effect = Exception("Database error")

                result, status_code = list_users()

                assert status_code == 500
                result_data = result.get_json()
                assert "Error listing users" in result_data["message"]

    def test_view_user_success(self, app, sample_user):
        """Test viewing a specific user"""
        with app.app_context():
            mock_user = MagicMock(spec=User)
            mock_user.to_json.return_value = {
                "id": 1,
                "user_name": "testuser",
                "name": "Test User",
                "email": "test@example.com",
                "profile": "USER",
            }

            with patch("services.user_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = mock_user

                result, status_code = view_user(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["user_name"] == "testuser"

    def test_view_user_not_found(self, app):
        """Test viewing a user that doesn't exist"""
        with app.app_context():
            with patch("services.user_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = view_user(999)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "User not found"

    def test_view_user_with_exception(self, app):
        """Test viewing a user when an exception occurs"""
        with app.app_context():
            with patch("services.user_services.User.query") as mock_user_query:
                mock_user_query.get.side_effect = Exception("Database error")

                result, status_code = view_user(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error viewing user" in result_data["message"]

    def test_new_user_success(self, app):
        """Test creating a new user"""
        with app.app_context():
            user_data = {
                "user_name": "newuser",
                "name": "New User",
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "profile": "USER",
            }

            with (
                patch("services.user_services.User.query") as mock_user_query,
                patch("services.user_services.db.session") as mock_db_session,
                patch("services.user_services.bcrypt.hashpw") as mock_hashpw,
                patch(
                    "services.user_services.create_access_token"
                ) as mock_create_token,
            ):

                mock_user_query.filter_by.return_value.first.return_value = None
                mock_hashpw.return_value.decode.return_value = "hashed_password"
                mock_create_token.return_value = "access_token_123"
                mock_db_session.add = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = new_user(user_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["user_name"] == "newuser"
                assert result_data["access_token"] == "access_token_123"

    def test_new_user_missing_username(self, app):
        """Test creating a user without username"""
        with app.app_context():
            user_data = {
                "name": "New User",
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "profile": "USER",
            }

            result, status_code = new_user(user_data)

            assert status_code == 400
            result_data = result.get_json()
            assert result_data["message"] == "User name is required"

    def test_new_user_missing_email(self, app):
        """Test creating a user without email"""
        with app.app_context():
            user_data = {
                "user_name": "newuser",
                "name": "New User",
                "password": "SecurePass123",
                "profile": "USER",
            }

            result, status_code = new_user(user_data)

            assert status_code == 400
            result_data = result.get_json()
            assert result_data["message"] == "Email is required"

    def test_new_user_invalid_email(self, app):
        """Test creating a user with invalid email format"""
        with app.app_context():
            user_data = {
                "user_name": "newuser",
                "name": "New User",
                "email": "invalid-email",
                "password": "SecurePass123",
                "profile": "USER",
            }

            result, status_code = new_user(user_data)

            assert status_code == 400
            result_data = result.get_json()
            assert result_data["message"] == "Invalid email format"

    def test_new_user_invalid_username(self, app):
        """Test creating a user with invalid username format"""
        with app.app_context():
            user_data = {
                "user_name": "ab",  # too short
                "name": "New User",
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "profile": "USER",
            }

            result, status_code = new_user(user_data)

            assert status_code == 400
            result_data = result.get_json()
            assert result_data["message"] == "Invalid username format"

    def test_new_user_already_exists(self, app):
        """Test creating a user that already exists"""
        with app.app_context():
            user_data = {
                "user_name": "existinguser",
                "name": "Existing User",
                "email": "existing@example.com",
                "password": "SecurePass123",
                "profile": "USER",
            }

            with patch("services.user_services.User.query") as mock_user_query:
                mock_user_query.filter_by.return_value.first.return_value = MagicMock()

                result, status_code = new_user(user_data)

                assert status_code == 400
                result_data = result.get_json()
                assert result_data["message"] == "User already exists"

    def test_new_user_with_exception(self, app):
        """Test creating a user when an exception occurs"""
        with app.app_context():
            user_data = {
                "user_name": "erroruser",
                "name": "Error User",
                "email": "error@example.com",
                "password": "SecurePass123",
                "profile": "USER",
            }

            with (
                patch("services.user_services.User.query") as mock_user_query,
                patch("services.user_services.db.session") as mock_db_session,
            ):

                mock_user_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = new_user(user_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error adding user" in result_data["message"]

    def test_edit_user_success(self, app):
        """Test editing an existing user"""
        with app.app_context():
            user_data = {
                "name": "Updated User",
                "email": "updated@example.com",
                "profile": "ADMIN",
            }

            mock_user = MagicMock(spec=User)

            with (
                patch("services.user_services.User.query"),
                patch("services.user_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = mock_user

                result, status_code = edit_user(1, user_data)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "User edited successfully"

                # Verify that the attributes were set
                for key, value in user_data.items():
                    assert getattr(mock_user, key) == value

    def test_edit_user_not_found(self, app):
        """Test editing a user that doesn't exist"""
        with app.app_context():
            user_data = {"name": "Updated User"}

            with patch("services.user_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = edit_user(999, user_data)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "User not found"

    def test_edit_user_with_exception(self, app):
        """Test editing a user when an exception occurs"""
        with app.app_context():
            user_data = {"name": "Updated User"}

            with (
                patch("services.user_services.User.query"),
                patch("services.user_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = edit_user(1, user_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error editing user" in result_data["message"]

    def test_delete_user_success(self, app):
        """Test deleting an existing user"""
        with app.app_context():
            mock_user = MagicMock(spec=User)

            with (
                patch("services.user_services.User.query"),
                patch("services.user_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = mock_user

                result, status_code = delete_user(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "User deleted successfully"

    def test_delete_user_not_found(self, app):
        """Test deleting a user that doesn't exist"""
        with app.app_context():
            with patch("services.user_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = delete_user(999)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "User not found"

    def test_delete_user_with_exception(self, app):
        """Test deleting a user when an exception occurs"""
        with app.app_context():
            with (
                patch("services.user_services.User.query"),
                patch("services.user_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = delete_user(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error deleting user" in result_data["message"]

    def test_login_user_success(self, app):
        """Test successful user login"""
        with app.app_context():
            login_data = {"user_name": "testuser", "password": "SecurePass123"}

            mock_user = MagicMock(spec=User)
            mock_user.id = 1
            mock_user.user_name = "testuser"
            mock_user.name = "Test User"
            mock_user.profile = "USER"
            mock_user.password = "hashed_password"

            with (
                patch("services.user_services.User.query") as mock_user_query,
                patch("services.user_services.bcrypt.checkpw") as mock_checkpw,
                patch(
                    "services.user_services.create_access_token"
                ) as mock_create_token,
            ):

                mock_user_query.filter_by.return_value.first.return_value = mock_user
                mock_checkpw.return_value = True
                mock_create_token.return_value = "access_token_123"

                result, status_code = login_user(login_data)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["user_name"] == "testuser"
                assert result_data["access_token"] == "access_token_123"

    def test_login_user_missing_username(self, app):
        """Test login without username"""
        with app.app_context():
            login_data = {"password": "SecurePass123"}

            result, status_code = login_user(login_data)

            assert status_code == 400
            result_data = result.get_json()
            assert "Both user name and password are required" in result_data["message"]

    def test_login_user_missing_password(self, app):
        """Test login without password"""
        with app.app_context():
            login_data = {"user_name": "testuser"}

            result, status_code = login_user(login_data)

            assert status_code == 400
            result_data = result.get_json()
            assert "Both user name and password are required" in result_data["message"]

    def test_login_user_invalid_username(self, app):
        """Test login with invalid username"""
        with app.app_context():
            login_data = {"user_name": "invaliduser", "password": "SecurePass123"}

            with patch("services.user_services.User.query") as mock_user_query:
                mock_user_query.filter_by.return_value.first.return_value = None

                result, status_code = login_user(login_data)

                assert status_code == 401
                result_data = result.get_json()
                assert result_data["message"] == "Invalid username or password"

    def test_login_user_invalid_password(self, app):
        """Test login with invalid password"""
        with app.app_context():
            login_data = {"user_name": "testuser", "password": "WrongPassword"}

            mock_user = MagicMock(spec=User)
            mock_user.password = "hashed_password"

            with (
                patch("services.user_services.User.query") as mock_user_query,
                patch("services.user_services.bcrypt.checkpw") as mock_checkpw,
            ):

                mock_user_query.filter_by.return_value.first.return_value = mock_user
                mock_checkpw.return_value = False

                result, status_code = login_user(login_data)

                assert status_code == 401
                result_data = result.get_json()
                assert result_data["message"] == "Invalid username or password"

    def test_login_user_with_exception(self, app):
        """Test login when an exception occurs"""
        with app.app_context():
            login_data = {"user_name": "testuser", "password": "SecurePass123"}

            with patch("services.user_services.User.query") as mock_user_query:
                mock_user_query.filter_by.side_effect = Exception("Database error")

                result, status_code = login_user(login_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "Error logging in user" in result_data["message"]

    def test_validate_email_valid(self):
        """Test email validation with valid email"""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.co.uk") is True
        assert validate_email("user+tag@example.org") is True

    def test_validate_email_invalid(self):
        """Test email validation with invalid email"""
        assert validate_email("invalid-email") is False
        assert validate_email("@example.com") is False
        assert validate_email("user@") is False
        assert validate_email("user..name@example.com") is False
        assert validate_email("") is False

    def test_validate_username_valid(self):
        """Test username validation with valid username"""
        assert validate_username("user123") is True
        assert validate_username("user_name") is True
        assert validate_username("user-name") is True
        assert validate_username("user.name") is True
        assert validate_username("user123_name-test") is True

    def test_validate_username_invalid(self):
        """Test username validation with invalid username"""
        assert validate_username("ab") is False  # too short
        assert validate_username("user name") is False  # contains space
        assert validate_username("user@name") is False  # contains special char
        assert validate_username("") is False
        assert validate_username("a") is False  # too short
