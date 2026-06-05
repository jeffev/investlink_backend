from flask import request
from flask_jwt_extended import get_jwt_identity

from services.backtest_service import run_backtest


def run_backtest_json(strategy_id):
    user_id = get_jwt_identity()
    start_date_str = request.args.get("start_date")
    return run_backtest(strategy_id, user_id, start_date_str)
