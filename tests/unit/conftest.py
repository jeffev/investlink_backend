import sys
import os
import pytest
from unittest.mock import MagicMock
from flask import Flask

# Ensure the app folder is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# Flask application context fixture
@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


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
    )


@pytest.fixture
def sample_fii():
    """Fixture for sample FII"""
    from models.fii import Fii

    return Fii(
        ticker="KNRI11",
        companyname="Knewin",
        price=100.0,
        sectorid=1,
        sectorname="Real Estate",
        subsectorid=1,
        subsectorname="Real Estate",
        segment="Real Estate",
        segmentid=1,
        gestao=1,
        gestao_f="Gestão",
        dy=0.06,
        p_vp=1.2,
        valorpatrimonialcota=100.0,
        liquidezmediadiaria=1000.0,
        percentualcaixa=0.1,
        dividend_cagr=0.05,
        cota_cagr=0.04,
        numerocotistas=1000,
        numerocotas=10000,
        patrimonio=1000000.0,
        lastdividend=5.0,
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
    from models.favorite_fiis import FavoriteFii

    fav = FavoriteFii(
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
        layout="Default",
        estado=None,
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
