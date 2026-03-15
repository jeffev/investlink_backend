from unittest.mock import patch, MagicMock
from services.prediction_service import (
    get_all_predictions,
    get_prediction_by_ticker,
)
from models.stock_prediction import StockPrediction


class TestPredictionService:

    def test_get_all_predictions_success(self, app):
        with app.app_context():
            mock_pred = MagicMock(spec=StockPrediction)
            mock_pred.to_json.return_value = {
                "ticker": "PETR4",
                "label": "BARATA",
                "prob_barata": 0.7,
                "prob_neutra": 0.2,
                "prob_cara": 0.1,
                "composite_score": 75.0,
                "model_version": "v1.0",
                "run_date": "2026-03-14T10:00:00",
            }

            with patch(
                "services.prediction_service.get_latest_predictions_map"
            ) as mock_predictions_map:
                mock_predictions_map.return_value = {"PETR4": mock_pred}

                result, status_code = get_all_predictions()

                assert status_code == 200
                result_data = result.get_json()
                assert "data" in result_data
                assert len(result_data["data"]) == 1
                assert result_data["data"][0]["ticker"] == "PETR4"

    def test_get_all_predictions_empty(self, app):
        with app.app_context():
            with patch(
                "services.prediction_service.get_latest_predictions_map"
            ) as mock_predictions_map:
                mock_predictions_map.return_value = {}

                result, status_code = get_all_predictions()

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["data"] == []

    def test_get_all_predictions_with_exception(self, app):
        with app.app_context():
            with patch(
                "services.prediction_service.get_latest_predictions_map"
            ) as mock_predictions_map:
                mock_predictions_map.side_effect = Exception("Database error")

                result, status_code = get_all_predictions()

                assert status_code == 500
                result_data = result.get_json()
                assert (
                    result_data["message"]
                    == "An error occurred, please try again later"
                )

    def test_get_prediction_by_ticker_success(self, app):
        with app.app_context():
            mock_pred = MagicMock(spec=StockPrediction)
            mock_pred.to_json.return_value = {
                "ticker": "PETR4",
                "label": "BARATA",
                "prob_barata": 0.7,
                "prob_neutra": 0.2,
                "prob_cara": 0.1,
                "composite_score": 75.0,
                "model_version": "v1.0",
                "run_date": "2026-03-14T10:00:00",
            }

            with patch("services.prediction_service.db.session") as mock_session:
                query_result = mock_session.query.return_value
                filter_result = query_result.filter.return_value
                order_result = filter_result.order_by.return_value
                order_result.first.return_value = mock_pred

                result, status_code = get_prediction_by_ticker("PETR4")

                assert status_code == 200
                result_data = result.get_json()
                assert result_data["ticker"] == "PETR4"
                assert result_data["label"] == "BARATA"

    def test_get_prediction_by_ticker_not_found(self, app):
        with app.app_context():
            with patch("services.prediction_service.db.session") as mock_session:
                query_result = mock_session.query.return_value
                filter_result = query_result.filter.return_value
                order_result = filter_result.order_by.return_value
                order_result.first.return_value = None

                result, status_code = get_prediction_by_ticker("INVALID")

                assert status_code == 404
                result_data = result.get_json()
                assert result_data["message"] == "Prediction not found"

    def test_get_prediction_by_ticker_with_exception(self, app):
        with app.app_context():
            with patch("services.prediction_service.db.session") as mock_session:
                mock_session.query.side_effect = Exception("Database error")

                result, status_code = get_prediction_by_ticker("PETR4")

                assert status_code == 500
                result_data = result.get_json()
                assert (
                    result_data["message"]
                    == "An error occurred, please try again later"
                )
