import sys
import os

# Ensure app package is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

import services.favorite_services as fav_srv


class QueryStub:
    def __init__(self, first=None, get=None, all_list=None):
        self._first = first
        self._get = get
        self._all = all_list or []

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self._first

    def get(self, key):
        return self._get

    def all(self):
        return self._all


class DummySession:
    def __init__(self):
        self.added = []
        self.deleted = []

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        return None

    def rollback(self):
        return None


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    # Replace jsonify to return plain data for assertions
    monkeypatch.setattr(fav_srv, 'jsonify', lambda x: x)
    # Replace db.session with dummy session
    dummy = DummySession()
    monkeypatch.setattr(fav_srv.db, 'session', dummy)
    return monkeypatch


def test_add_favorite_already_exists():
    # Simulate existing favorite present
    fav_srv.Favorite.query = QueryStub(first=object())
    result = fav_srv.add_favorite(1, 'TST')
    assert result == ({'message': 'This stock is already favorited by this user'}, 400)


def test_add_favorite_success():
    # No existing favorite
    fav_srv.Favorite.query = QueryStub(first=None)
    # Ensure new Favorite construction does not require DB
    result = fav_srv.add_favorite(1, 'TST')
    assert result == ({'message': 'Favorite added successfully'}, 201)


def test_remove_favorite_not_found():
    fav_srv.Favorite.query = QueryStub(first=None)
    result = fav_srv.remove_favorite(1, 'TST')
    assert result == ({'message': 'Favorite not found'}, 404)


def test_remove_favorite_success():
    # Simulate favorite exists
    fav_srv.Favorite.query = QueryStub(first=object())
    result = fav_srv.remove_favorite(1, 'TST')
    assert result == ({'message': 'Favorite deleted successfully'}, 200)
