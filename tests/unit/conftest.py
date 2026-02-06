import sys
import os
import pytest
from unittest.mock import MagicMock

# Ensure the app folder is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# Mock database session
@pytest.fixture
def mock_db_session():
    """Fixture for mocked database session"""
    session = MagicMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


# Sample test data
@pytest.fixture
def sample_user():
    """Fixture for sample user"""
    from models.user import User

    return User(
        id=1,
        user_name="testuser",
        name="Test User",
        email="test@example.com",
        profile="USER",
        password="hashed_password",
    )


@pytest.fixture
def sample_stock():
    """Fixture for sample stock"""
    from models.stock import Stock

    return Stock(
        ticker="PETR4",
        companyname="Petrobras",
        price=25.0,
        lpa=5.0,
        vpa=20.0,
        p_l=5.0,
        dy=0.08,
    )


@pytest.fixture
def sample_fii():
    """Fixture for sample FII"""
    from models.fii import FII

    return FII(
        ticker="KNRI11",
        name="Knewin",
        price=100.0,
        dy=0.06,
        p_vp=1.2,
    )


@pytest.fixture
def sample_favorite(sample_user, sample_stock):
    """Fixture for sample favorite"""
    from models.favorite import Favorite

    fav = Favorite(
        id=1,
        user_id=sample_user.id,
        stock_ticker=sample_stock.ticker,
        ceiling_price=30.0,
        target_price=25.0,
    )
    fav.stock = sample_stock
    return fav


@pytest.fixture
def sample_favorite_fii(sample_user, sample_fii):
    """Fixture for sample favorite FII"""
    from models.favorite_fiis import Favorite_FII

    fav = Favorite_FII(
        id=1,
        user_id=sample_user.id,
        fii_ticker=sample_fii.ticker,
        ceiling_price=110.0,
        target_price=100.0,
    )
    fav.fii = sample_fii
    return fav


@pytest.fixture
def sample_layout(sample_user):
    """Fixture for sample user layout"""
    from models.user_layout import UserLayout

    return UserLayout(
        id=1,
        user_id=sample_user.id,
        layout_name="Default",
        layout_config={
            "columns": ["ticker", "price", "dy"],
            "sorting": ["ticker"],
        },
    )


# Authentication fixtures
@pytest.fixture
def auth_token():
    """Fixture for sample JWT token"""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGl0eSI6MX0.test_token"


@pytest.fixture
def valid_user_data():
    """Fixture for valid user creation data"""
    return {
        "user_name": "newuser",
        "name": "New User",
        "email": "newuser@example.com",
        "password": "SecurePass123",
        "profile": "USER",
    }


@pytest.fixture
def invalid_user_data():
    """Fixture for invalid user creation data"""
    return {
        "user_name": "ab",  # too short
        "name": "Invalid User",
        "email": "invalid-email",  # invalid format
        "password": "weak",
    }
