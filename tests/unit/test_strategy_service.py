import json
from unittest.mock import MagicMock, patch

from models.strategy import Strategy  # noqa: F401
from models.user import User  # noqa: F401
from services.strategy_service import create_strategy, delete_strategy, list_strategies


def _make_strategy(id=1, user_id=1, name="Bazin", asset_type="STOCK"):
    s = MagicMock(spec=Strategy)
    s.id = id
    s.user_id = user_id
    s.name = name
    s.asset_type = asset_type
    s.filters = '[{"id":"dy","value":[6,""]}]'
    s.sorting = None
    s.created_at = None
    s.to_json.return_value = {
        "id": id,
        "user_id": user_id,
        "name": name,
        "asset_type": asset_type,
        "filters": s.filters,
        "sorting": None,
        "created_at": None,
    }
    return s


class TestStrategyService:

    def test_list_strategies_empty(self, app):
        """Sem estratégias → 200 com lista vazia."""
        with app.app_context():
            with patch("services.strategy_service.Strategy.query") as mock_query:
                mock_query.filter_by.return_value.order_by.return_value.all.return_value = (
                    []
                )
                result, status = list_strategies(1, "STOCK")
                assert status == 200
                assert result.get_json() == []

    def test_list_strategies_returns_user_strategies(self, app):
        """Retorna estratégias filtradas por user_id e asset_type."""
        with app.app_context():
            strategy = _make_strategy()
            with patch("services.strategy_service.Strategy.query") as mock_query:
                mock_query.filter_by.return_value.order_by.return_value.all.return_value = [
                    strategy
                ]
                result, status = list_strategies(1, "STOCK")
                assert status == 200
                data = result.get_json()
                assert len(data) == 1
                assert data[0]["name"] == "Bazin"
                assert data[0]["asset_type"] == "STOCK"

    def test_create_strategy_success(self, app):
        """Dados válidos → 201."""
        with app.app_context():
            with patch("services.strategy_service.db.session") as mock_session:
                mock_session.add = MagicMock()
                mock_session.commit = MagicMock()

                result, status = create_strategy(
                    1,
                    {
                        "name": "Bazin",
                        "asset_type": "STOCK",
                        "filters": json.dumps([{"id": "dy", "value": [6, ""]}]),
                    },
                )
                assert status == 201
                assert "created" in result.get_json()["message"].lower()

    def test_create_strategy_missing_name(self, app):
        """Name ausente → 400."""
        with app.app_context():
            result, status = create_strategy(
                1,
                {
                    "name": "",
                    "asset_type": "STOCK",
                    "filters": json.dumps([{"id": "dy", "value": [6, ""]}]),
                },
            )
            assert status == 400

    def test_create_strategy_invalid_asset_type(self, app):
        """asset_type inválido → 400."""
        with app.app_context():
            result, status = create_strategy(
                1,
                {
                    "name": "Teste",
                    "asset_type": "CRYPTO",
                    "filters": json.dumps([{"id": "dy", "value": [6, ""]}]),
                },
            )
            assert status == 400

    def test_create_strategy_empty_filters(self, app):
        """Filters vazio → 400."""
        with app.app_context():
            result, status = create_strategy(
                1,
                {"name": "Teste", "asset_type": "STOCK", "filters": "[]"},
            )
            assert status == 400

    def test_delete_strategy_success(self, app):
        """Delete do próprio usuário → 200."""
        with app.app_context():
            strategy = _make_strategy(user_id=1)
            with patch("services.strategy_service.db.session") as mock_session:
                mock_session.get.return_value = strategy
                result, status = delete_strategy(1, 1)
                assert status == 200
                mock_session.delete.assert_called_once_with(strategy)

    def test_delete_strategy_not_found(self, app):
        """Strategy inexistente → 404."""
        with app.app_context():
            with patch("services.strategy_service.db.session") as mock_session:
                mock_session.get.return_value = None
                result, status = delete_strategy(1, 999)
                assert status == 404

    def test_delete_strategy_unauthorized(self, app):
        """Strategy de outro usuário → 403."""
        with app.app_context():
            strategy = _make_strategy(user_id=2)
            with patch("services.strategy_service.db.session") as mock_session:
                mock_session.get.return_value = strategy
                result, status = delete_strategy(1, 1)
                assert status == 403
