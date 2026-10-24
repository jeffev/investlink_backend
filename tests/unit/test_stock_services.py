from unittest.mock import patch, MagicMock

# Importado pelo efeito colateral: `utils` registra todos os mappers. Sem ele,
# `MagicMock(spec=Stock)` quebra ao resolver `Favorite -> User` — pegadinha
# conhecida deste projeto, documentada no CLAUDE.md do backend.
import utils  # noqa: F401
from services.stock_services import (
    list_stocks,
    view_stock,
    new_stock,
    edit_stock,
    delete_stock,
    get_all_stocks_from_statusinvest,
    update_all_stocks,
    calculate_ey,
)
from models.stock import Stock
from models.favorite import Favorite


class TestStockServices:

    def test_list_stocks_success(self, app, sample_user):
        """Test successful listing of stocks with favorites"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.ticker = "PETR4"
            mock_stock.to_json.return_value = {
                "ticker": "PETR4",
                "companyname": "Petrobras",
                "price": 25.0,
                "lpa": 5.0,
                "vpa": 20.0,
                "p_l": 5.0,
                "dy": 0.08,
            }

            mock_favorite = MagicMock(spec=Favorite)
            mock_favorite.stock_ticker = "PETR4"

            mock_paginated = MagicMock()
            mock_paginated.items = [mock_stock]
            mock_paginated.total = 1
            mock_paginated.pages = 1
            mock_paginated.page = 1

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.Favorite.query") as mock_favorite_query,
                patch("services.stock_services.get_latest_predictions_map") as mock_pm,
                patch(
                    "services.stock_services.attach_ml_fields",
                    side_effect=lambda s, p: s,
                ) as _,
                patch("services.stock_services.db") as mock_db,
                patch("services.stock_services.get_score_map", return_value={}),
            ):

                # A listagem filtra os ativos e faz outer join com
                # stock_scores para poder ordenar pelo score, então a paginação
                # sai da query já filtrada e unida.
                mock_stock_query.filter.return_value.outerjoin.return_value.paginate.return_value = (  # noqa: E501
                    mock_paginated
                )
                mock_favorite_query.filter_by.return_value.all.return_value = [
                    mock_favorite
                ]
                mock_pm.return_value = {}
                mock_db.session.query.return_value.filter.return_value.group_by.return_value.all.return_value = (
                    []
                )

                result, status_code = list_stocks(sample_user.id)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["pagination"]["total"] == 1
                assert result_data["pagination"]["current_page"] == 1
                assert len(result_data["data"]) == 1
                assert result_data["data"][0]["ticker"] == "PETR4"
                assert result_data["data"][0]["favorita"] is True

    def test_list_stocks_empty(self, app):
        """Test listing stocks when no stocks exist"""
        with app.app_context():
            mock_paginated = MagicMock()
            mock_paginated.items = []
            mock_paginated.total = 0
            mock_paginated.pages = 0
            mock_paginated.page = 1

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.Favorite.query") as mock_favorite_query,
                patch("services.stock_services.get_latest_predictions_map") as mock_pm,
                patch("services.stock_services.get_score_map", return_value={}),
            ):

                mock_stock_query.filter.return_value.outerjoin.return_value.paginate.return_value = (  # noqa: E501
                    mock_paginated
                )
                mock_favorite_query.filter_by.return_value.all.return_value = []
                mock_pm.return_value = {}

                result, status_code = list_stocks(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["data"] == []
                assert result_data["pagination"]["total"] == 0

    def test_list_stocks_with_exception(self, app):
        """Test listing stocks when an exception occurs"""
        with app.app_context():
            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.Favorite.query") as mock_favorite_query,
            ):
                mock_favorite_query.filter_by.return_value.all.return_value = []
                mock_stock_query.paginate.side_effect = Exception("Database error")

                result, status_code = list_stocks(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_view_stock_success(self, app, sample_stock):
        """Test viewing a specific stock"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)
            mock_stock.to_json.return_value = {
                "ticker": "PETR4",
                "companyname": "Petrobras",
                "price": 25.0,
                "lpa": 5.0,
                "vpa": 20.0,
                "p_l": 5.0,
                "dy": 0.08,
            }

            with (
                patch("services.stock_services.db.session") as mock_db_session,
                patch("services.stock_services.get_latest_predictions_map") as mock_pm,
                patch(
                    "services.stock_services.attach_ml_fields",
                    side_effect=lambda s, p: s,
                ) as _,
            ):
                mock_db_session.get.return_value = mock_stock
                mock_pm.return_value = {}

                result, status_code = view_stock("PETR4")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["ticker"] == "PETR4"

    def test_view_stock_not_found(self, app):
        """Test viewing a stock that doesn't exist"""
        with app.app_context():
            with patch("services.stock_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = view_stock("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Stock not found"

    def test_view_stock_with_exception(self, app):
        """Test viewing a stock when an exception occurs"""
        with app.app_context():
            with patch("services.stock_services.Stock.query") as mock_stock_query:
                mock_stock_query.get.side_effect = Exception("Database error")

                result, status_code = view_stock("PETR4")

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_new_stock_success(self, app):
        """Test creating a new stock"""
        with app.app_context():
            stock_data = {
                "ticker": "NEWSTK4",
                "companyname": "New Stock",
                "price": 30.0,
                "lpa": 3.0,
                "vpa": 15.0,
                "p_l": 10.0,
                "dy": 0.05,
            }

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_stock_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = new_stock(stock_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "Stock added successfully"

    def test_new_stock_already_exists(self, app):
        """Test creating a stock that already exists"""
        with app.app_context():
            stock_data = {
                "ticker": "EXISTING4",
                "companyname": "Existing Stock",
                "price": 30.0,
                "lpa": 3.0,
                "vpa": 15.0,
                "p_l": 10.0,
                "dy": 0.05,
            }

            with patch("services.stock_services.Stock.query") as mock_stock_query:
                mock_stock_query.filter_by.return_value.first.return_value = MagicMock()

                result, status_code = new_stock(stock_data)

                assert status_code == 400
                result_data = result.get_json()
                assert result_data["message"] == "Stock already exists"

    def test_new_stock_with_exception(self, app):
        """Test creating a stock when an exception occurs"""
        with app.app_context():
            stock_data = {
                "ticker": "ERRORSTK4",
                "companyname": "Error Stock",
                "price": 30.0,
                "lpa": 3.0,
                "vpa": 15.0,
                "p_l": 10.0,
                "dy": 0.05,
            }

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_stock_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = new_stock(stock_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_edit_stock_success(self, app):
        """Test editing an existing stock"""
        with app.app_context():
            stock_data = {
                "companyname": "Updated Stock",
                "price": 35.0,
                "lpa": 4.0,
                "dy": 0.06,
            }

            mock_stock = MagicMock(spec=Stock)
            mock_stock.get_graham_formula.return_value = 20.0
            mock_stock.get_discount_to_graham.return_value = 10.0

            with (
                patch("services.stock_services.Stock.query"),
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = mock_stock

                result, status_code = edit_stock("PETR4", stock_data)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Stock edited successfully"

                # Verify that the attributes were set
                for key, value in stock_data.items():
                    assert getattr(mock_stock, key) == value

                # Verify that graham_formula and discount_to_graham were recalculated
                assert mock_stock.graham_formula == 20.0
                assert mock_stock.discount_to_graham == 10.0

    def test_edit_stock_not_found(self, app):
        """Test editing a stock that doesn't exist"""
        with app.app_context():
            stock_data = {"companyname": "Updated Stock"}

            with patch("services.stock_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = edit_stock("INVALID", stock_data)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Stock not found"

    def test_edit_stock_with_exception(self, app):
        """Test editing a stock when an exception occurs"""
        with app.app_context():
            stock_data = {"companyname": "Updated Stock"}

            with (
                patch("services.stock_services.Stock.query"),
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = edit_stock("PETR4", stock_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_delete_stock_success(self, app):
        """Test deleting an existing stock"""
        with app.app_context():
            mock_stock = MagicMock(spec=Stock)

            with (
                patch("services.stock_services.Stock.query"),
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = mock_stock

                result, status_code = delete_stock("PETR4")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Stock deleted successfully"

    def test_delete_stock_not_found(self, app):
        """Test deleting a stock that doesn't exist"""
        with app.app_context():
            with patch("services.stock_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = delete_stock("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Stock not found"

    def test_delete_stock_with_exception(self, app):
        """Test deleting a stock when an exception occurs"""
        with app.app_context():
            with (
                patch("services.stock_services.Stock.query"),
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = MagicMock()
                mock_db_session.delete = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = delete_stock("PETR4")

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    @patch("services.stock_services.cloudscraper.create_scraper")
    def test_get_all_stocks_from_statusinvest_success(self, mock_create_scraper):
        mock_get = mock_create_scraper.return_value.get
        """Test successful retrieval of stocks from StatusInvest"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [
                {
                    "ticker": "PETR4",
                    "companyname": "Petrobras",
                    "price": 25.0,
                    "lpa": 5.0,
                    "vpa": 20.0,
                    "p_l": 5.0,
                    "dy": 0.08,
                }
            ]
        }
        mock_get.return_value = mock_response

        result = get_all_stocks_from_statusinvest()

        assert result is not None
        assert "list" in result
        assert len(result["list"]) == 1
        assert result["list"][0]["ticker"] == "PETR4"

    @patch("services.stock_services.cloudscraper.create_scraper")
    def test_get_all_stocks_from_statusinvest_http_error(self, mock_create_scraper):
        mock_get = mock_create_scraper.return_value.get
        """Test retrieval of stocks when HTTP error occurs"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_all_stocks_from_statusinvest()

        assert result is None

    @patch("services.stock_services.cloudscraper.create_scraper")
    def test_get_all_stocks_from_statusinvest_exception(self, mock_create_scraper):
        mock_get = mock_create_scraper.return_value.get
        """Test retrieval of stocks when an exception occurs"""
        mock_get.side_effect = Exception("Network error")

        result = get_all_stocks_from_statusinvest()

        assert result is None

    def test_calculate_ey(self):
        """Test calculation of earnings yield"""
        # Test normal case
        stock_data = {"lpa": 5.0, "price": 25.0}
        result = calculate_ey(stock_data)
        expected = 5.0 / 25.0
        assert result == expected

        # Test zero price (should return 0)
        stock_data = {"lpa": 5.0, "price": 0.0}
        result = calculate_ey(stock_data)
        assert result == 0.0

        # Test zero lpa (should return 0)
        stock_data = {"lpa": 0.0, "price": 25.0}
        result = calculate_ey(stock_data)
        assert result == 0.0

        # Test missing values (should return 0)
        stock_data = {}
        result = calculate_ey(stock_data)
        assert result == 0.0

    @patch("services.stock_services.get_all_stocks_from_fundamentus")
    def test_update_all_stocks_success(self, mock_get_stocks, app):
        """Test successful update of all stocks"""
        with app.app_context():
            mock_stock_data = {
                "list": [
                    {
                        "ticker": "PETR4",
                        "companyname": "Petrobras",
                        "price": 25.0,
                        "lpa": 5.0,
                        "vpa": 20.0,
                        "p_l": 5.0,
                        "dy": 0.08,
                        "roic": 0.15,
                        "ey": 0.20,
                    }
                ]
            }

            mock_existing_stock = MagicMock(spec=Stock)
            mock_existing_stock.ticker = "PETR4"
            # A deslistagem compara `missing_since` com uma data; o dublê
            # precisa trazer o campo preenchido como o model traz.
            mock_existing_stock.missing_since = None
            mock_existing_stock.get_graham_formula.return_value = 20.0
            mock_existing_stock.get_discount_to_graham.return_value = 10.0

            with (
                patch("services.stock_services.Stock.query") as mock_stock_query,
                patch("services.stock_services.db.session") as mock_db_session,
            ):

                mock_get_stocks.return_value = mock_stock_data
                mock_stock_query.filter.return_value.all.return_value = [
                    mock_existing_stock
                ]
                mock_db_session.add_all = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = update_all_stocks()

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "Stocks updated successfully"

    @patch("services.stock_services.get_all_stocks_from_statusinvest")
    @patch("services.stock_services.get_all_stocks_from_fundamentus")
    def test_update_all_stocks_no_data(self, mock_fundamentus, mock_status, app):
        """As duas fontes fora do ar."""
        with app.app_context():
            mock_fundamentus.return_value = None
            mock_status.return_value = None

            result, status_code = update_all_stocks()

            assert status_code == 500
            result_data = result.get_json()
            assert "Error fetching stock data" in result_data["error"]

    @patch("services.stock_services.get_all_stocks_from_fundamentus")
    def test_update_all_stocks_with_exception(self, mock_get_stocks, app):
        """Test update of stocks when an exception occurs"""
        with app.app_context():
            mock_get_stocks.return_value = {"list": []}

            with patch("services.stock_services.db.session") as mock_db_session:
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = update_all_stocks()

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]


class TestMarkDelisted:
    """
    E6 — o ticker que some da fonte é deslistado, não inalterado.
    Confirmado na prática: 618 linhas em stocks contra 617 no payload (TRAD3).
    """

    def _stock(self, ticker, active=True, delisted_at=None, missing_since=None):
        stock = MagicMock(spec=Stock)
        stock.ticker = ticker
        stock.active = active
        stock.delisted_at = delisted_at
        stock.missing_since = missing_since
        return stock

    def _run(self, returned, absent=(), revived=()):
        from services.stock_services import mark_delisted

        with patch("services.stock_services.Stock.query") as mock_query:
            mock_query.filter.return_value.all.side_effect = [
                list(absent),
                list(revived),
            ]
            return mark_delisted(returned)

    def test_a_ticker_that_vanished_is_only_flagged(self, app):
        # Ausência de um dia não é deslistagem: quando a coleta trocou de
        # fonte, 71 papéis sumiram da lista nova de uma vez — entre eles a
        # B3SA3, que é a própria bolsa.
        with app.app_context():
            ausente = self._stock("TRAD3")

            assert self._run({"PETR4"}, absent=[ausente]) == 0

            assert ausente.active is True
            assert ausente.missing_since is not None

    def test_a_ticker_that_came_back_is_reactivated(self, app):
        # Reaparecer sem reativar deixaria o papel contraditando o preço
        # fresco ao lado dele.
        with app.app_context():
            voltou = self._stock("AAAA3", active=False, delisted_at="2026-01-01")

            self._run({"AAAA3"}, revived=[voltou])

            assert voltou.active is True
            assert voltou.delisted_at is None

    def test_an_already_delisted_ticker_keeps_its_original_date(self, app):
        with app.app_context():
            antigo = self._stock("TRAD3", active=False, delisted_at="2026-01-01")

            self._run({"PETR4"}, absent=[antigo])

            assert antigo.delisted_at == "2026-01-01"

    def test_an_empty_payload_delists_nobody(self, app):
        # Payload vazio é falha de busca, não mercado que fechou.
        with app.app_context():
            assert self._run(set()) == 0


# ── Carência antes de considerar uma ação deslistada ─────────────────────────
#
# Quando a coleta trocou de fonte, 71 papéis que não aparecem na lista nova
# foram marcados como fora do pregão de uma vez — entre eles a B3SA3, que é a
# própria bolsa. Ausência de um dia numa fonte não é deslistagem.


class _AcaoFalsa:
    def __init__(self, ticker, active=True, missing_since=None):
        self.ticker = ticker
        self.active = active
        self.missing_since = missing_since
        self.delisted_at = None


def _marcar(ausentes, presentes, retornados=("PETR4",)):
    from services.stock_services import mark_delisted

    def consulta_mock():
        chain = MagicMock()
        chain.filter.side_effect = [
            MagicMock(all=MagicMock(return_value=ausentes)),
            MagicMock(all=MagicMock(return_value=presentes)),
        ]
        return chain

    with patch("services.stock_services.Stock") as mock_stock:
        mock_stock.query = consulta_mock()
        mock_stock.ticker = MagicMock()
        return mark_delisted(set(retornados))


def test_ausencia_de_um_dia_nao_deslista(app):
    with app.app_context():
        sumida = _AcaoFalsa("B3SA3")
        deslistados = _marcar(ausentes=[sumida], presentes=[])

        assert deslistados == 0
        assert sumida.active is True
        assert sumida.missing_since is not None


def test_ausencia_prolongada_deslista(app):
    from datetime import date, timedelta

    from services.stock_services import DELISTING_GRACE_DAYS

    with app.app_context():
        sumida = _AcaoFalsa(
            "MORT3",
            missing_since=date.today() - timedelta(days=DELISTING_GRACE_DAYS + 1),
        )
        deslistados = _marcar(ausentes=[sumida], presentes=[])

        assert deslistados == 1
        assert sumida.active is False


def test_papel_que_volta_limpa_a_marca_de_ausencia(app):
    from datetime import date

    with app.app_context():
        voltou = _AcaoFalsa("PETR4", active=False, missing_since=date(2026, 1, 1))
        _marcar(ausentes=[], presentes=[voltou])

        assert voltou.active is True
        assert voltou.missing_since is None
        assert voltou.delisted_at is None


def test_coleta_vazia_nao_deslista_o_pregao_inteiro(app):
    from services.stock_services import mark_delisted

    with app.app_context():
        assert mark_delisted(set()) == 0
