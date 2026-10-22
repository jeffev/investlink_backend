from unittest.mock import MagicMock, patch

from models.fii import Fii  # noqa: F401
from models.stock import Stock  # noqa: F401
from models.portfolio import Portfolio  # noqa: F401
from models.portfolio_fii import PortfolioFii  # noqa: F401

from services.portfolio_fii_services import (
    add_fii_position,
    delete_fii_position,
    edit_fii_position,
    get_portfolio_fii_summary,
    list_portfolio_fii,
)


class TestPortfolioFiiServices:

    def test_list_portfolio_fii_empty(self, app):
        """Portfólio FII vazio → 200 com lista vazia."""
        with app.app_context():
            with patch(
                "services.portfolio_fii_services.PortfolioFii.query"
            ) as mock_query:
                paged = mock_query.filter_by.return_value
                paged.count.return_value = 0
                paged.offset.return_value.limit.return_value.all.return_value = []
                result, status = list_portfolio_fii(1)
                assert status == 200
                assert result.get_json()["data"] == []
                assert result.get_json()["pagination"]["total"] == 0

    def test_list_portfolio_fii_with_position(self, app, sample_fii):
        """Posição FII com lastdividend calcula monthly_income corretamente."""
        with app.app_context():
            sample_fii.price = 100.0
            sample_fii.lastdividend = 0.80
            sample_fii.dy = 9.6

            mock_pos = MagicMock()
            mock_pos.to_json.return_value = {
                "id": 1,
                "user_id": 1,
                "fii_ticker": "KNRI11",
                "quantity": 50.0,
                "average_price": 98.0,
                "total_invested": 4900.0,
                "created_at": None,
                "updated_at": None,
            }
            mock_pos.fii = sample_fii

            with patch(
                "services.portfolio_fii_services.PortfolioFii.query"
            ) as mock_query:
                # A listagem agora pagina: conta e recorta em vez de .all().
                paged = mock_query.filter_by.return_value
                paged.count.return_value = 1
                paged.offset.return_value.limit.return_value.all.return_value = [
                    mock_pos
                ]
                result, status = list_portfolio_fii(1)

                assert status == 200
                data = result.get_json()["data"]
                assert len(data) == 1
                assert data[0]["monthly_income"] == round(50.0 * 0.80, 2)
                assert data[0]["current_price"] == 100.0

    def test_get_portfolio_fii_summary(self, app, sample_fii):
        """Summary agrega total_invested e current_value corretamente."""
        with app.app_context():
            sample_fii.price = 110.0

            mock_pos = MagicMock()
            mock_pos.total_invested = 5000.0
            mock_pos.quantity = 50.0
            mock_pos.fii = sample_fii

            with patch(
                "services.portfolio_fii_services.PortfolioFii.query"
            ) as mock_query:
                mock_query.filter_by.return_value.all.return_value = [mock_pos]
                result, status = get_portfolio_fii_summary(1)

                assert status == 200
                data = result.get_json()
                assert data["total_invested"] == 5000.0
                assert data["current_value"] == round(50.0 * 110.0, 2)

    def test_add_fii_position_missing_fields(self, app):
        """Campos obrigatórios ausentes → 400."""
        with app.app_context():
            result, status = add_fii_position({"user_id": 1})
            assert status == 400

    def test_add_fii_position_fii_not_found(self, app):
        """FII inexistente → 404."""
        with app.app_context():
            with patch("services.portfolio_fii_services.db.session") as mock_session:
                mock_session.get.side_effect = lambda model, pk: (
                    MagicMock() if model.__name__ == "User" else None
                )
                result, status = add_fii_position(
                    {
                        "user_id": 1,
                        "fii_ticker": "INVALID11",
                        "quantity": 10,
                        "average_price": 100.0,
                    }
                )
                assert status == 404

    def test_add_fii_position_invalid_quantity(self, app):
        """Quantity negativa → 400."""
        with app.app_context():
            with patch("services.portfolio_fii_services.db.session") as mock_session:
                mock_session.get.return_value = MagicMock()
                result, status = add_fii_position(
                    {
                        "user_id": 1,
                        "fii_ticker": "KNRI11",
                        "quantity": -5,
                        "average_price": 100.0,
                    }
                )
                assert status == 400

    def test_edit_fii_position_not_found(self, app):
        """Position inexistente → 404."""
        with app.app_context():
            with patch("services.portfolio_fii_services.db.session") as mock_session:
                mock_session.get.return_value = None
                result, status = edit_fii_position(999, {"quantity": 10})
                assert status == 404

    def test_delete_fii_position_not_found(self, app):
        """Position inexistente → 404."""
        with app.app_context():
            with patch("services.portfolio_fii_services.db.session") as mock_session:
                mock_session.get.return_value = None
                result, status = delete_fii_position(999)
                assert status == 404

    def test_delete_fii_position_success(self, app):
        """Delete bem-sucedido → 200."""
        with app.app_context():
            mock_pos = MagicMock()
            with patch("services.portfolio_fii_services.db.session") as mock_session:
                mock_session.get.return_value = mock_pos
                result, status = delete_fii_position(1)
                assert status == 200
                mock_session.delete.assert_called_once_with(mock_pos)
