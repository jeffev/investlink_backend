import datetime
from unittest.mock import MagicMock, patch

from models.transaction import Transaction  # noqa: F401
from models.user import User  # noqa: F401
from services.transaction_service import (
    create_transaction,
    delete_transaction,
    list_transactions,
)


def _make_tx(id=1, user_id=1, ticker="PETR4", tx_type="COMPRA", total=1000.0):
    t = MagicMock(spec=Transaction)
    t.id = id
    t.user_id = user_id
    t.ticker = ticker
    t.asset_type = "STOCK"
    t.type = tx_type
    t.quantity = 10.0
    t.price = 100.0
    t.total = total
    t.date = datetime.date(2024, 1, 15)
    t.created_at = None
    t.to_json.return_value = {
        "id": id,
        "user_id": user_id,
        "ticker": ticker,
        "asset_type": "STOCK",
        "type": tx_type,
        "quantity": 10.0,
        "price": 100.0,
        "total": total,
        "date": "2024-01-15",
        "created_at": None,
    }
    return t


class TestTransactionService:

    def test_list_empty(self, app):
        """Sem transações → 200 com data=[] e summary zerado."""
        with app.app_context():
            with patch("services.transaction_service.Transaction.query") as mock_q:
                mock_q.filter_by.return_value.order_by.return_value.all.return_value = (
                    []
                )
                result, status = list_transactions(1)
                assert status == 200
                body = result.get_json()
                assert body["data"] == []
                assert body["summary"]["total_compras"] == 0
                assert body["summary"]["resultado_realizado"] == 0

    def test_list_with_transactions(self, app):
        """Calcula summary corretamente: compra 1000, venda 1500 → resultado 500."""
        with app.app_context():
            txs = [
                _make_tx(tx_type="COMPRA", total=1000.0),
                _make_tx(id=2, tx_type="VENDA", total=1500.0),
            ]
            with patch("services.transaction_service.Transaction.query") as mock_q:
                mock_q.filter_by.return_value.order_by.return_value.all.return_value = (
                    txs
                )
                result, status = list_transactions(1)
                assert status == 200
                s = result.get_json()["summary"]
                assert s["total_compras"] == 1000.0
                assert s["total_vendas"] == 1500.0
                assert s["resultado_realizado"] == 500.0

    def test_create_success(self, app):
        """Dados válidos → 201."""
        with app.app_context():
            with patch("services.transaction_service.db.session") as mock_s:
                result, status = create_transaction(
                    1,
                    {
                        "ticker": "PETR4",
                        "type": "COMPRA",
                        "asset_type": "STOCK",
                        "quantity": 10,
                        "price": 28.50,
                        "date": "2024-01-15",
                    },
                )
                assert status == 201
                mock_s.add.assert_called_once()
                mock_s.commit.assert_called_once()

    def test_create_invalid_type(self, app):
        """type inválido → 400."""
        with app.app_context():
            result, status = create_transaction(
                1,
                {
                    "ticker": "PETR4",
                    "type": "HOLD",
                    "asset_type": "STOCK",
                    "quantity": 10,
                    "price": 28.50,
                    "date": "2024-01-15",
                },
            )
            assert status == 400

    def test_create_missing_ticker(self, app):
        """Ticker ausente → 400."""
        with app.app_context():
            result, status = create_transaction(
                1,
                {
                    "ticker": "",
                    "type": "COMPRA",
                    "asset_type": "STOCK",
                    "quantity": 10,
                    "price": 28.50,
                    "date": "2024-01-15",
                },
            )
            assert status == 400

    def test_delete_success(self, app):
        """Delete do próprio usuário → 200."""
        with app.app_context():
            tx = _make_tx(user_id=1)
            with patch("services.transaction_service.db.session") as mock_s:
                mock_s.get.return_value = tx
                result, status = delete_transaction(1, 1)
                assert status == 200
                mock_s.delete.assert_called_once_with(tx)

    def test_delete_not_found(self, app):
        """Transação inexistente → 404."""
        with app.app_context():
            with patch("services.transaction_service.db.session") as mock_s:
                mock_s.get.return_value = None
                result, status = delete_transaction(1, 999)
                assert status == 404

    def test_delete_unauthorized(self, app):
        """Transação de outro usuário → 403."""
        with app.app_context():
            tx = _make_tx(user_id=2)
            with patch("services.transaction_service.db.session") as mock_s:
                mock_s.get.return_value = tx
                result, status = delete_transaction(1, 1)
                assert status == 403
