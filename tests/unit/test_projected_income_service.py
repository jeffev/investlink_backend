from unittest.mock import MagicMock, patch

from models.fii import Fii  # noqa: F401
from models.stock import Stock  # noqa: F401
from models.portfolio import Portfolio  # noqa: F401
from models.portfolio_fii import PortfolioFii  # noqa: F401

from services.projected_income_service import get_projected_income


def _make_stock_position(qty, price, dy):
    stock = MagicMock()
    stock.price = price
    stock.dy = dy
    pos = MagicMock()
    pos.quantity = qty
    pos.stock = stock
    return pos


def _make_fii_position(qty, price, dy, lastdividend):
    fii = MagicMock()
    fii.price = price
    fii.dy = dy
    fii.lastdividend = lastdividend
    pos = MagicMock()
    pos.quantity = qty
    pos.fii = fii
    return pos


class TestProjectedIncomeService:

    def test_only_stocks(self, app):
        """Só ações → income calculado via DY anual / 12."""
        with app.app_context():
            # qty=100, price=30.0, dy=12.0 → mensal = (100*30*0.12)/12 = 30.0
            stock_pos = _make_stock_position(100, 30.0, 12.0)

            with (
                patch("services.projected_income_service.Portfolio.query") as mock_pq,
                patch(
                    "services.projected_income_service.PortfolioFii.query"
                ) as mock_fq,
            ):
                mock_pq.filter_by.return_value.all.return_value = [stock_pos]
                mock_fq.filter_by.return_value.all.return_value = []

                result, status = get_projected_income(1)

                assert status == 200
                data = result.get_json()
                assert data["stocks_monthly"] == 30.0
                assert data["fiis_monthly"] == 0.0
                assert data["monthly"] == 30.0
                assert data["yearly"] == round(30.0 * 12, 2)

    def test_only_fiis_with_lastdividend(self, app):
        """Só FIIs com lastdividend → income = qty × lastdividend."""
        with app.app_context():
            # qty=50, lastdividend=0.80 → mensal = 50*0.80 = 40.0
            fii_pos = _make_fii_position(50, 100.0, 9.6, 0.80)

            with (
                patch("services.projected_income_service.Portfolio.query") as mock_pq,
                patch(
                    "services.projected_income_service.PortfolioFii.query"
                ) as mock_fq,
            ):
                mock_pq.filter_by.return_value.all.return_value = []
                mock_fq.filter_by.return_value.all.return_value = [fii_pos]

                result, status = get_projected_income(1)

                assert status == 200
                data = result.get_json()
                assert data["fiis_monthly"] == 40.0
                assert data["stocks_monthly"] == 0.0

    def test_fii_fallback_to_dy(self, app):
        """FII sem lastdividend usa DY como fallback."""
        with app.app_context():
            # qty=100, price=100.0, dy=12.0, lastdividend=None
            # mensal = (100*100*0.12)/12 = 100.0
            fii_pos = _make_fii_position(100, 100.0, 12.0, None)

            with (
                patch("services.projected_income_service.Portfolio.query") as mock_pq,
                patch(
                    "services.projected_income_service.PortfolioFii.query"
                ) as mock_fq,
            ):
                mock_pq.filter_by.return_value.all.return_value = []
                mock_fq.filter_by.return_value.all.return_value = [fii_pos]

                result, status = get_projected_income(1)

                assert status == 200
                assert result.get_json()["fiis_monthly"] == 100.0

    def test_position_with_null_dy_ignored(self, app):
        """Posição com dy=None não causa erro e contribui 0 ao total."""
        with app.app_context():
            stock_pos = _make_stock_position(100, 30.0, None)

            with (
                patch("services.projected_income_service.Portfolio.query") as mock_pq,
                patch(
                    "services.projected_income_service.PortfolioFii.query"
                ) as mock_fq,
            ):
                mock_pq.filter_by.return_value.all.return_value = [stock_pos]
                mock_fq.filter_by.return_value.all.return_value = []

                result, status = get_projected_income(1)

                assert status == 200
                assert result.get_json()["monthly"] == 0.0

    def test_empty_portfolio(self, app):
        """Portfólio vazio → monthly=0, yearly=0."""
        with app.app_context():
            with (
                patch("services.projected_income_service.Portfolio.query") as mock_pq,
                patch(
                    "services.projected_income_service.PortfolioFii.query"
                ) as mock_fq,
            ):
                mock_pq.filter_by.return_value.all.return_value = []
                mock_fq.filter_by.return_value.all.return_value = []

                result, status = get_projected_income(1)

                assert status == 200
                data = result.get_json()
                assert data["monthly"] == 0.0
                assert data["yearly"] == 0.0

    def test_combined_stocks_and_fiis(self, app):
        """Ações + FIIs → monthly é a soma de ambos."""
        with app.app_context():
            stock_pos = _make_stock_position(100, 30.0, 12.0)  # 30.0/mês
            fii_pos = _make_fii_position(50, 100.0, 9.6, 0.80)  # 40.0/mês

            with (
                patch("services.projected_income_service.Portfolio.query") as mock_pq,
                patch(
                    "services.projected_income_service.PortfolioFii.query"
                ) as mock_fq,
            ):
                mock_pq.filter_by.return_value.all.return_value = [stock_pos]
                mock_fq.filter_by.return_value.all.return_value = [fii_pos]

                result, status = get_projected_income(1)

                assert status == 200
                data = result.get_json()
                assert data["stocks_monthly"] == 30.0
                assert data["fiis_monthly"] == 40.0
                assert data["monthly"] == 70.0
