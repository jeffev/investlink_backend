"""
O reset da conta demo: apaga o que os visitantes gravaram, repõe a vitrine e
não toca em nenhuma outra conta.
"""

from datetime import date

import pytest

from config import db
from models.favorite import Favorite
from models.fii import Fii
from models.portfolio import Portfolio
from models.portfolio_fii import PortfolioFii
from models.stock import Stock
from models.strategy import Strategy
from models.transaction import Transaction
from models.user import User
from services.demo_account_service import (
    DEMO_FIIS,
    DEMO_STOCKS,
    reset_demo_account,
)


@pytest.fixture
def banco(app):
    db.init_app(app)
    db.create_all()
    for ticker in ("ITUB4", "WEGE3", "BBAS3", "PETR4", "EGIE3", "VALE3", "TAEE11"):
        db.session.add(Stock(ticker=ticker, companyname=ticker, price=50.0))
    db.session.add(Stock(ticker="BBSE3", companyname="BBSE3", price=None))
    for ticker, *_ in DEMO_FIIS:
        db.session.add(Fii(ticker=ticker, price=100.0))
    db.session.add(User(id=1, user_name="visitante", password="x", profile="USER"))
    db.session.add(User(id=2, user_name="outro", password="x", profile="USER"))
    db.session.commit()
    yield db
    db.session.remove()
    db.drop_all()


def test_apaga_o_que_o_visitante_gravou(banco):
    banco.session.add(
        Strategy(user_id=1, name="lixo", asset_type="STOCK", filters="[]")
    )
    banco.session.add(Portfolio(user_id=1, ticker="VALE3", quantity=1, average_price=1))
    banco.session.commit()

    reset_demo_account("visitante", today=date(2026, 10, 25))

    assert Strategy.query.filter_by(user_id=1).count() == 0
    assert Portfolio.query.filter_by(user_id=1, ticker="VALE3").count() == 0


def test_nao_toca_em_outra_conta(banco):
    banco.session.add(Portfolio(user_id=2, ticker="VALE3", quantity=5, average_price=9))
    banco.session.commit()

    reset_demo_account("visitante")

    assert Portfolio.query.filter_by(user_id=2).count() == 1


def test_ativo_sem_preco_fica_de_fora(banco):
    reset_demo_account("visitante")

    tickers = {p.ticker for p in Portfolio.query.filter_by(user_id=1)}
    assert tickers == {t for t, *_ in DEMO_STOCKS} - {"BBSE3"}
    assert PortfolioFii.query.filter_by(user_id=1).count() == len(DEMO_FIIS)


def test_compras_do_extrato_batem_com_o_preco_medio(banco):
    reset_demo_account("visitante")

    for position in Portfolio.query.filter_by(user_id=1):
        compras = Transaction.query.filter_by(
            user_id=1, ticker=position.ticker, type="COMPRA"
        ).all()
        quantidade = sum(c.quantity for c in compras)
        custo = sum(c.quantity * c.price for c in compras)
        assert quantidade == position.quantity
        assert custo / quantidade == pytest.approx(position.average_price, abs=0.02)


def test_rodar_duas_vezes_nao_duplica(banco):
    primeira = reset_demo_account("visitante")
    segunda = reset_demo_account("visitante")

    assert primeira == segunda
    assert Favorite.query.filter_by(user_id=1).count() == 4


def test_conta_inexistente_nao_faz_nada(banco):
    assert reset_demo_account("ninguem") == 0
