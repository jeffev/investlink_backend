from flask import request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from models.portfolio import Portfolio
from models.portfolio_fii import PortfolioFii

from services.score_backtest_service import backtest_score
from services.opportunity_service import (
    DEFAULT_LIMIT,
    get_stock_score,
    list_opportunities,
    list_profiles,
)


def _tickers_da_carteira(asset_type):
    """
    O que o usuário já tem, para poder sumir da vitrine.

    Falha de leitura devolve conjunto vazio: esconder a carteira é conforto,
    ver a lista é o produto.
    """
    user_id = get_jwt_identity()
    try:
        if (asset_type or "").upper() == "FII":
            return {p.fii_ticker for p in PortfolioFii.query.filter_by(user_id=user_id)}
        return {p.ticker for p in Portfolio.query.filter_by(user_id=user_id)}
    except SQLAlchemyError:
        return set()


def list_opportunities_json():
    profile = request.args.get("profile", None)
    limit = request.args.get("limit", DEFAULT_LIMIT, type=int)
    asset_type = request.args.get("asset_type", None)

    filters = {
        "max_price": request.args.get("max_price", type=float),
        "only_drawdown": request.args.get("only_drawdown") == "true",
    }
    if request.args.get("exclude_portfolio") == "true":
        filters["exclude_tickers"] = _tickers_da_carteira(asset_type)

    return list_opportunities(profile, limit, asset_type, filters)


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
