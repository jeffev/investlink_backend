import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Ensure app package is importable
ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "app")
)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import services.stock_services as stock_srv  # noqa: E402
from models.stock import Stock  # noqa: E402


def test_calculate_ey_zero_price():
    data = {"lpa": 10.0, "price": 0}
    assert stock_srv.calculate_ey(data) == 0


def test_calculate_ey_normal():
    data = {"lpa": 2.0, "price": 50.0}
    assert stock_srv.calculate_ey(data) == 2.0 / 50.0


@patch("services.stock_services.Stock.query")
@patch("services.stock_services.db.session")
def test_list_stocks_includes_favorita_flag(mock_session, mock_query):
    """Test list_stocks adds favorita flag based on user favorites"""
    stock1 = Stock(ticker="PETR4", companyname="Petrobras", price=25.0)
    stock2 = Stock(ticker="VALE3", companyname="Vale", price=60.0)
    mock_query.all.return_value = [stock1, stock2]

    with patch("services.stock_services.Favorite.query") as mock_fav_query:
        mock_fav_query.filter_by.return_value.all.return_value = []
        response = stock_srv.list_stocks(user_id=1)
        data = response.get_json()

        assert len(data) == 2
        assert "favorita" in data[0]
        assert "favorita" in data[1]


@patch("services.stock_services.Stock.query")
@patch("services.stock_services.db.session")
def test_new_stock_calculates_graham_formula(mock_session, mock_query):
    """Test new_stock calculates Graham formula on creation"""
    mock_query.filter_by.return_value.first.return_value = None

    stock_data = {
        "ticker": "PETR4",
        "companyname": "Petrobras",
        "price": 25.0,
        "lpa": 5.0,
        "vpa": 20.0,
    }

    response = stock_srv.new_stock(stock_data)
    status = response[1]

    assert status == 201
    assert "Stock added successfully" in response[0].get_json()["message"]


@patch("services.stock_services.Stock.query")
@patch("services.stock_services.db.session")
def test_edit_stock_recalculates_graham_formula(mock_session, mock_query):
    """Test edit_stock recalculates Graham formula and discount"""
    stock = Stock(
        ticker="PETR4", companyname="Petrobras", price=25.0, lpa=5.0, vpa=20.0
    )
    mock_query.get.return_value = stock

    stock_data = {
        "price": 30.0,
        "lpa": 5.5,
    }

    response = stock_srv.edit_stock("PETR4", stock_data)
    status = response[1]

    assert status == 200


@patch("services.stock_services.Stock.query")
@patch("services.stock_services.db.session")
def test_delete_stock_success(mock_session, mock_query):
    """Test delete_stock removes stock from database"""
    stock = Stock(ticker="PETR4", companyname="Petrobras", price=25.0)
    mock_query.get.return_value = stock

    response = stock_srv.delete_stock("PETR4")
    status = response[1]

    assert status == 200
    assert "deleted successfully" in response[0].get_json()["message"]


def test_get_all_stocks_from_statusinvest_http_error(monkeypatch):
    class Resp:
        status_code = 500

    monkeypatch.setattr(stock_srv.requests, "get", lambda *a, **k: Resp())
    assert stock_srv.get_all_stocks_from_statusinvest() is None


def test_get_all_stocks_from_statusinvest_success(monkeypatch):
    class Resp:
        status_code = 200

        def json(self):
            return {"list": [{"ticker": "TST"}]}

    monkeypatch.setattr(stock_srv.requests, "get", lambda *a, **k: Resp())
    res = stock_srv.get_all_stocks_from_statusinvest()
    assert isinstance(res, dict)
    assert "list" in res


def test_view_stock_not_found(monkeypatch):
    # make jsonify return plain value
    monkeypatch.setattr(stock_srv, "jsonify", lambda x: x)

    class Q:
        def get(self, key):
            return None

    Dummy = type("Dummy", (), {"query": Q()})
    monkeypatch.setattr(stock_srv, "Stock", Dummy)
    result = stock_srv.view_stock("ABC")
    assert result == ({"message": "Stock not found"}, 404)


def test_view_stock_success(monkeypatch):
    monkeypatch.setattr(stock_srv, "jsonify", lambda x: x)

    class FakeStock:
        def to_json(self):
            return {"ticker": "ABC"}

    class Q:
        def get(self, key):
            return FakeStock()

    Dummy = type("Dummy", (), {"query": Q()})
    monkeypatch.setattr(stock_srv, "Stock", Dummy)
    result = stock_srv.view_stock("ABC")
    assert result == {"ticker": "ABC"}


def test_update_all_stocks_creates_and_commits(monkeypatch):
    # Prepare cached stocks
    cached = [
        {"ticker": "AAA", "price": 10.0, "lpa": 1.0, "roic": 0.5},
        {"ticker": "BBB", "price": 20.0, "lpa": 2.0, "roic": 0.2},
    ]

    # Mock the network call to return our cached list
    monkeypatch.setattr(
        stock_srv, "get_all_stocks_from_statusinvest", lambda: {"list": cached}
    )
    # Make jsonify return plain dict for assertion
    monkeypatch.setattr(stock_srv, "jsonify", lambda x: x)

    # Stub out Stock class and its query to simulate no existing stocks
    class Q:
        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class DummyStock:
        query = Q()

        class Ticker:
            def in_(self, items):
                return items

        ticker = Ticker()

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def get_graham_formula(self):
            return 0.0

        def get_discount_to_graham(self):
            return 0.0

    monkeypatch.setattr(stock_srv, "Stock", DummyStock)

    # Dummy DB session to capture add_all
    class DummySession:
        def __init__(self):
            self.added_all = None

        def add_all(self, items):
            self.added_all = items

        def commit(self):
            return None

        def rollback(self):
            return None

    dummy_session = DummySession()
    monkeypatch.setattr(stock_srv.db, "session", dummy_session)

    result = stock_srv.update_all_stocks()
    # Expect successful response
    assert result == ({"message": "Stocks updated successfully"}, 200)
    # Ensure add_all was called with created Stock objects
    assert dummy_session.added_all is not None
    assert len(dummy_session.added_all) == 2
