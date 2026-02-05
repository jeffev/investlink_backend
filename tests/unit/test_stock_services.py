import sys
import os

# Ensure app package is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import types
import services.stock_services as stock_srv


def test_calculate_ey_zero_price():
    data = {"lpa": 10.0, "price": 0}
    assert stock_srv.calculate_ey(data) == 0


def test_calculate_ey_normal():
    data = {"lpa": 2.0, "price": 50.0}
    assert stock_srv.calculate_ey(data) == 2.0 / 50.0


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
