"""
A conta compartilhada da demo pública volta ao estado de vitrine.

Todo visitante entra na mesma conta. Sem reset, o primeiro que apaga a
carteira deixa a demo vazia para todos os seguintes, e o que um visitante
grava (estratégia, layout, favorito) aparece para quem chegar depois.

O preço médio sai do preço atual da base vezes um fator fixo: a carteira fica
com ganhos e perdas plausíveis qualquer que seja o mês em que o reset rode,
sem cotação inventada que envelhece.
"""

import logging
from datetime import date, timedelta

from config import db
from models.favorite import Favorite
from models.favorite_fiis import FavoriteFii
from models.fii import Fii
from models.portfolio import Portfolio
from models.portfolio_fii import PortfolioFii
from models.stock import Stock
from models.strategy import Strategy
from models.transaction import Transaction
from models.user import User
from models.user_layout import UserLayout

logger = logging.getLogger(__name__)

# (ticker, quantidade, preço médio / preço atual)
DEMO_STOCKS = [
    ("ITUB4", 300, 0.86),
    ("WEGE3", 200, 1.12),
    ("BBAS3", 400, 0.93),
    ("PETR4", 150, 0.81),
    ("EGIE3", 250, 1.05),
    ("BBSE3", 180, 0.95),
]
DEMO_FIIS = [
    ("HGLG11", 40, 1.04),
    ("KNRI11", 30, 0.97),
    ("MXRF11", 800, 1.02),
    ("XPML11", 50, 0.91),
    ("BTLG11", 45, 0.99),
]
# (ticker, preço teto / preço atual, preço alvo / preço atual)
DEMO_FAVORITE_STOCKS = [
    ("VALE3", 0.92, 1.20),
    ("TAEE11", 1.05, 1.18),
    ("ITUB4", 0.95, 1.15),
    ("WEGE3", 0.85, 1.10),
]
DEMO_FAVORITE_FIIS = [
    ("VISC11", 0.97, 1.12),
    ("HGLG11", 0.95, 1.10),
]
# Uma operação encerrada, para o extrato mostrar resultado realizado.
DEMO_CLOSED_TRADE = ("TAEE11", 200, 0.88, 0.95)

USER_OWNED_MODELS = (
    Transaction,
    Portfolio,
    PortfolioFii,
    Favorite,
    FavoriteFii,
    Strategy,
    UserLayout,
)


def _current_prices(model, tickers):
    rows = model.query.filter(model.ticker.in_(tickers)).all()
    return {row.ticker: row.price for row in rows if row.price and row.price > 0}


def _buy_history(user_id, ticker, asset_type, quantity, average_price, today):
    """Duas compras que somam a posição e dão exatamente o preço médio dela."""
    first_quantity = round(quantity * 0.6)
    second_quantity = quantity - first_quantity
    first_price = round(average_price * 0.97, 2)
    second_price = round(
        (average_price * quantity - first_price * first_quantity) / second_quantity, 2
    )
    return [
        Transaction(
            user_id=user_id,
            ticker=ticker,
            asset_type=asset_type,
            type="COMPRA",
            quantity=first_quantity,
            price=first_price,
            date=today - timedelta(days=300),
        ),
        Transaction(
            user_id=user_id,
            ticker=ticker,
            asset_type=asset_type,
            type="COMPRA",
            quantity=second_quantity,
            price=second_price,
            date=today - timedelta(days=120),
        ),
    ]


def _positions(user_id, model, holdings, prices, today):
    asset_type = "STOCK" if model is Portfolio else "FII"
    ticker_field = "ticker" if model is Portfolio else "fii_ticker"
    rows = []
    for ticker, quantity, factor in holdings:
        if ticker not in prices:
            continue
        average_price = round(prices[ticker] * factor, 2)
        rows.append(
            model(
                user_id=user_id,
                quantity=quantity,
                average_price=average_price,
                **{ticker_field: ticker},
            )
        )
        rows += _buy_history(
            user_id, ticker, asset_type, quantity, average_price, today
        )
    return rows


def _favorites(user_id, model, favorites, prices):
    ticker_field = "stock_ticker" if model is Favorite else "fii_ticker"
    return [
        model(
            user_id=user_id,
            ceiling_price=round(prices[ticker] * ceiling, 2),
            target_price=round(prices[ticker] * target, 2),
            **{ticker_field: ticker},
        )
        for ticker, ceiling, target in favorites
        if ticker in prices
    ]


def _closed_trade(user_id, prices, today):
    ticker, quantity, buy_factor, sell_factor = DEMO_CLOSED_TRADE
    if ticker not in prices:
        return []
    return [
        Transaction(
            user_id=user_id,
            ticker=ticker,
            asset_type="STOCK",
            type=tx_type,
            quantity=quantity,
            price=round(prices[ticker] * factor, 2),
            date=today - timedelta(days=days_ago),
        )
        for tx_type, factor, days_ago in (
            ("COMPRA", buy_factor, 240),
            ("VENDA", sell_factor, 60),
        )
    ]


def reset_demo_account(user_name, today=None):
    """
    Apaga tudo o que a conta demo guarda e grava a carteira de vitrine.

    Ativo que não está na base (ou está sem preço) fica de fora em vez de
    entrar com preço zero. Devolve quantas linhas foram gravadas.
    """
    user = User.query.filter_by(user_name=user_name).first()
    if user is None:
        return 0
    today = today or date.today()

    for model in USER_OWNED_MODELS:
        model.query.filter_by(user_id=user.id).delete(synchronize_session=False)

    stock_tickers = {t for t, *_ in DEMO_STOCKS + DEMO_FAVORITE_STOCKS}
    stock_tickers.add(DEMO_CLOSED_TRADE[0])
    fii_tickers = {t for t, *_ in DEMO_FIIS + DEMO_FAVORITE_FIIS}
    stock_prices = _current_prices(Stock, stock_tickers)
    fii_prices = _current_prices(Fii, fii_tickers)

    rows = (
        _positions(user.id, Portfolio, DEMO_STOCKS, stock_prices, today)
        + _positions(user.id, PortfolioFii, DEMO_FIIS, fii_prices, today)
        + _favorites(user.id, Favorite, DEMO_FAVORITE_STOCKS, stock_prices)
        + _favorites(user.id, FavoriteFii, DEMO_FAVORITE_FIIS, fii_prices)
        + _closed_trade(user.id, stock_prices, today)
    )
    db.session.add_all(rows)
    db.session.commit()
    logger.info(f"Conta demo '{user_name}' restaurada com {len(rows)} registros.")
    return len(rows)
