from unittest.mock import patch, MagicMock
from services.fii_services import (
    list_fiis,
    view_fii,
    new_fii,
    edit_fii,
    delete_fii,
    get_all_fiis_from_statusinvest,
    update_all_fiis,
)
from models.fii import Fii
from models.favorite_fiis import FavoriteFii


class TestFiiServices:

    def test_list_fiis_success(self, app, sample_user):
        """Test successful listing of FIIs with favorites"""
        with app.app_context():
            mock_fii = MagicMock(spec=Fii)
            mock_fii.ticker = "KNRI11"
            mock_fii.to_json.return_value = {
                "ticker": "KNRI11",
                "name": "Knewin",
                "price": 100.0,
                "dy": 0.06,
                "p_vp": 1.2,
            }

            mock_favorite = MagicMock(spec=FavoriteFii)
            mock_favorite.fii_ticker = "KNRI11"

            mock_paginated = MagicMock()
            mock_paginated.items = [mock_fii]
            mock_paginated.total = 1
            mock_paginated.pages = 1
            mock_paginated.page = 1

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.FavoriteFii.query") as mock_favorite_query,
                patch("services.fii_services.get_score_map", return_value={}),
            ):

                # A listagem passou a fazer outerjoin com fii_scores para
                # poder ordenar pelo score, então a paginação já não pende
                # direto da query.
                mock_fii_query.outerjoin.return_value.paginate.return_value = (
                    mock_paginated
                )
                mock_favorite_query.filter_by.return_value.all.return_value = [
                    mock_favorite
                ]

                result, status_code = list_fiis(sample_user.id)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["pagination"]["total"] == 1
                assert result_data["pagination"]["current_page"] == 1
                assert len(result_data["data"]) == 1
                assert result_data["data"][0]["ticker"] == "KNRI11"
                assert result_data["data"][0]["favorita"] is True

    def test_list_fiis_empty(self, app):
        """Test listing FIIs when no FIIs exist"""
        with app.app_context():
            mock_paginated = MagicMock()
            mock_paginated.items = []
            mock_paginated.total = 0
            mock_paginated.pages = 0
            mock_paginated.page = 1

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.FavoriteFii.query") as mock_favorite_query,
                patch("services.fii_services.get_score_map", return_value={}),
            ):

                # A listagem passou a fazer outerjoin com fii_scores para
                # poder ordenar pelo score, então a paginação já não pende
                # direto da query.
                mock_fii_query.outerjoin.return_value.paginate.return_value = (
                    mock_paginated
                )
                mock_favorite_query.filter_by.return_value.all.return_value = []

                result, status_code = list_fiis(1)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["data"] == []
                assert result_data["pagination"]["total"] == 0

    def test_list_fiis_with_exception(self, app):
        """Test listing FIIs when an exception occurs"""
        with app.app_context():
            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.FavoriteFii.query") as mock_favorite_query,
            ):
                mock_favorite_query.filter_by.return_value.all.return_value = []
                mock_fii_query.paginate.side_effect = Exception("Database error")

                result, status_code = list_fiis(1)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_view_fii_success(self, app, sample_fii):
        """Test viewing a specific FII"""
        with app.app_context():
            mock_fii = MagicMock(spec=Fii)
            mock_fii.to_json.return_value = {
                "ticker": "KNRI11",
                "name": "Knewin",
                "price": 100.0,
                "dy": 0.06,
                "p_vp": 1.2,
            }

            with patch("services.fii_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = mock_fii

                result, status_code = view_fii("KNRI11")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["ticker"] == "KNRI11"

    def test_view_fii_not_found(self, app):
        """Test viewing a FII that doesn't exist"""
        with app.app_context():
            with patch("services.fii_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = view_fii("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "FII not found"

    def test_view_fii_with_exception(self, app):
        """Test viewing a FII when an exception occurs"""
        with app.app_context():
            with patch("services.fii_services.Fii.query") as mock_fii_query:
                mock_fii_query.get.side_effect = Exception("Database error")

                result, status_code = view_fii("KNRI11")

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_new_fii_success(self, app, mock_db_session):
        """Test creating a new FII"""
        with app.app_context():
            fii_data = {
                "ticker": "NEWFII11",
                "name": "New FII",
                "price": 50.0,
                "dy": 0.08,
                "p_vp": 1.0,
            }

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.FavoriteFii.query"),
                patch("services.fii_services.db") as mock_db,
            ):

                mock_fii_query.filter_by.return_value.first.return_value = None
                mock_db.session = mock_db_session

                result, status_code = new_fii(fii_data)

                assert status_code == 201
                result_data = result.get_json()
                assert result_data["message"] == "FII added successfully"

    def test_new_fii_already_exists(self, app):
        """Test creating a FII that already exists"""
        with app.app_context():
            fii_data = {
                "ticker": "EXISTING11",
                "name": "Existing FII",
                "price": 50.0,
                "dy": 0.08,
                "p_vp": 1.0,
            }

            with patch("services.fii_services.Fii.query") as mock_fii_query:
                mock_fii_query.filter_by.return_value.first.return_value = MagicMock()

                result, status_code = new_fii(fii_data)

                assert status_code == 400
                result_data = result.get_json()
                assert result_data["message"] == "FII already exists"

    def test_new_fii_with_exception(self, app):
        """Test creating a FII when an exception occurs"""
        with app.app_context():
            fii_data = {
                "ticker": "ERRORFII11",
                "name": "Error FII",
                "price": 50.0,
                "dy": 0.08,
                "p_vp": 1.0,
            }

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = new_fii(fii_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_edit_fii_success(self, app):
        """Test editing an existing FII"""
        with app.app_context():
            fii_data = {"name": "Updated FII", "price": 60.0, "dy": 0.09}

            mock_fii = MagicMock(spec=Fii)

            with (
                patch("services.fii_services.Fii.query"),
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_db_session.get.return_value = mock_fii

                result, status_code = edit_fii("KNRI11", fii_data)

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "FII edited successfully"

                # Verify that the attributes were set
                for key, value in fii_data.items():
                    assert getattr(mock_fii, key) == value

    def test_edit_fii_not_found(self, app):
        """Test editing a FII that doesn't exist"""
        with app.app_context():
            fii_data = {"name": "Updated FII"}

            with patch("services.fii_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = edit_fii("INVALID", fii_data)

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "FII not found"

    def test_edit_fii_with_exception(self, app):
        """Test editing a FII when an exception occurs"""
        with app.app_context():
            fii_data = {"name": "Updated FII"}

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.get.return_value = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = edit_fii("KNRI11", fii_data)

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    def test_delete_fii_success(self, app):
        """Test deleting an existing FII"""
        with app.app_context():
            mock_fii = MagicMock(spec=Fii)

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.get.return_value = mock_fii
                mock_db_session.delete = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = delete_fii("KNRI11")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "FII deleted successfully"

    def test_delete_fii_not_found(self, app):
        """Test deleting a FII that doesn't exist"""
        with app.app_context():
            with patch("services.fii_services.db.session") as mock_db_session:
                mock_db_session.get.return_value = None

                result, status_code = delete_fii("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "FII not found"

    def test_delete_fii_with_exception(self, app):
        """Test deleting a FII when an exception occurs"""
        with app.app_context():
            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_fii_query.get.return_value = MagicMock()
                mock_db_session.delete = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = delete_fii("KNRI11")

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]

    @patch("services.fii_services.cloudscraper.create_scraper")
    def test_get_all_fiis_from_statusinvest_success(self, mock_create_scraper):
        mock_get = mock_create_scraper.return_value.get
        """Test successful retrieval of FIIs from StatusInvest"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [
                {
                    "ticker": "KNRI11",
                    "name": "Knewin",
                    "price": 100.0,
                    "dy": 0.06,
                    "p_vp": 1.2,
                }
            ]
        }
        mock_get.return_value = mock_response

        result = get_all_fiis_from_statusinvest()

        assert result is not None
        assert "list" in result
        assert len(result["list"]) == 1
        assert result["list"][0]["ticker"] == "KNRI11"

    @patch("services.fii_services.cloudscraper.create_scraper")
    def test_get_all_fiis_from_statusinvest_http_error(self, mock_create_scraper):
        mock_get = mock_create_scraper.return_value.get
        """Test retrieval of FIIs when HTTP error occurs"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_all_fiis_from_statusinvest()

        assert result is None

    @patch("services.fii_services.cloudscraper.create_scraper")
    def test_get_all_fiis_from_statusinvest_exception(self, mock_create_scraper):
        mock_get = mock_create_scraper.return_value.get
        """Test retrieval of FIIs when an exception occurs"""
        mock_get.side_effect = Exception("Network error")

        result = get_all_fiis_from_statusinvest()

        assert result is None

    @patch("services.fii_services.get_all_fiis_from_statusinvest")
    def test_update_all_fiis_success(self, mock_get_fiis, app):
        """Test successful update of all FIIs"""
        with app.app_context():
            mock_fii_data = {
                "list": [
                    {
                        "ticker": "KNRI11",
                        "name": "Knewin",
                        "price": 100.0,
                        "dy": 0.06,
                        "p_vp": 1.2,
                    }
                ]
            }

            mock_existing_fii = MagicMock(spec=Fii)
            mock_existing_fii.ticker = "KNRI11"

            with (
                patch("services.fii_services.Fii.query") as mock_fii_query,
                patch("services.fii_services.db.session") as mock_db_session,
            ):

                mock_get_fiis.return_value = mock_fii_data
                mock_fii_query.filter.return_value.all.return_value = [
                    mock_existing_fii
                ]
                mock_db_session.add_all = MagicMock()
                mock_db_session.commit = MagicMock()

                result, status_code = update_all_fiis()

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["message"] == "FIIs updated successfully."

    @patch("services.fii_services.get_all_fiis_from_fundamentus")
    @patch("services.fii_services.get_all_fiis_from_statusinvest")
    def test_update_all_fiis_no_data(self, mock_get_fiis, mock_get_fundamentus, app):
        """Test update of FIIs when both sources return no data"""
        with app.app_context():
            mock_get_fundamentus.return_value = None
            mock_get_fiis.return_value = None

            result, status_code = update_all_fiis()

            assert status_code == 500
            result_data = result.get_json()
            assert "Error fetching FII data" in result_data["error"]

    @patch("services.fii_services.get_all_fiis_from_statusinvest")
    def test_update_all_fiis_with_exception(self, mock_get_fiis, app):
        """Test update of FIIs when an exception occurs"""
        with app.app_context():
            mock_get_fiis.return_value = {"list": []}

            with patch("services.fii_services.db.session") as mock_db_session:
                mock_db_session.commit.side_effect = Exception("Database error")
                mock_db_session.rollback = MagicMock()

                result, status_code = update_all_fiis()

                assert status_code == 500
                result_data = result.get_json()
                assert "An error occurred" in result_data["message"]


class _FiiScoreStub:
    """Dublê com o contrato to_json do FiiScore."""

    def __init__(self, ticker, total):
        self.ticker = ticker
        self.score_total = total

    def to_json(self):
        return {
            "ticker": self.ticker,
            "profile": "EQUILIBRADO",
            "score_total": self.score_total,
            "eligible": True,
            "pillars": [{"key": "renda", "label": "Renda", "value": 80.0}],
            "reasons": [],
            "red_flags": [],
            "exclusion_reasons": [],
        }


def _listar(sort_by=None, profile=None, score=None):
    fii = MagicMock(spec=Fii)
    fii.ticker = "HGLG11"
    fii.to_json.return_value = {"ticker": "HGLG11", "p_vp": 0.89}

    paginated = MagicMock()
    paginated.items = [fii]
    paginated.total = 1
    paginated.pages = 1
    paginated.page = 1

    with (
        patch("services.fii_services.Fii.query") as fii_query,
        patch("services.fii_services.FavoriteFii.query") as favorite_query,
        patch(
            "services.fii_services.get_score_map",
            return_value={"HGLG11": score} if score else {},
        ),
    ):
        joined = fii_query.outerjoin.return_value
        joined.paginate.return_value = paginated
        joined.order_by.return_value.paginate.return_value = paginated
        favorite_query.filter_by.return_value.all.return_value = []

        response, status = list_fiis(
            1, sort_by=sort_by, sort_dir="desc", profile=profile
        )
        return response, status, joined


def test_a_tabela_de_fii_carrega_o_score(app):
    # A camada densa e a vitrine precisam mostrar a mesma nota; sem isto o
    # investidor veria 84 no card e nada na tabela.
    with app.app_context():
        response, status, _ = _listar(score=_FiiScoreStub("HGLG11", 84.2))

        assert status == 200
        linha = response.get_json()["data"][0]
        assert linha["score_total"] == 84.2
        assert linha["score_pillars"][0]["key"] == "renda"


def test_fundo_sem_score_continua_na_tabela(app):
    # O join é à esquerda de propósito: sumir com o fundo esconderia o ativo
    # em vez de esconder a nota.
    with app.app_context():
        response, status, _ = _listar()

        assert status == 200
        assert response.get_json()["data"][0]["score_total"] is None


def test_ordenar_por_score_usa_a_coluna_da_tabela_de_score(app):
    with app.app_context():
        _, _, joined = _listar(sort_by="score_total")
        joined.order_by.assert_called()


def test_perfil_invalido_cai_no_padrao(app):
    # CRESCIMENTO é perfil de ação. Aceitar em silêncio devolveria a tabela
    # ordenada por uma nota que não é a pedida.
    with app.app_context():
        response, status, _ = _listar(
            profile="CRESCIMENTO", score=_FiiScoreStub("HGLG11", 84.2)
        )
        assert status == 200
        assert response.get_json()["data"][0]["score_profile"] == "EQUILIBRADO"
