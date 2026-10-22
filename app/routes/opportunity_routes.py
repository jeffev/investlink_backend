from flask import request

from services.score_backtest_service import backtest_score
from services.opportunity_service import (
    DEFAULT_LIMIT,
    get_stock_score,
    list_opportunities,
    list_profiles,
)


def list_opportunities_json():
    profile = request.args.get("profile", None)
    limit = request.args.get("limit", DEFAULT_LIMIT, type=int)
    asset_type = request.args.get("asset_type", None)
    return list_opportunities(profile, limit, asset_type)


def list_profiles_json():
    asset_type = request.args.get("asset_type", None)
    return list_profiles(asset_type)


def get_stock_score_json(ticker):
    profile = request.args.get("profile", None)
    asset_type = request.args.get("asset_type", None)
    return get_stock_score(ticker.upper(), profile, asset_type)


def backtest_score_json():
    profile = request.args.get("profile", None)
    return backtest_score(profile)
