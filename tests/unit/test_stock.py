import sys
import os

# Ensure the app folder is on sys.path so imports match runtime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.stock import Stock  # noqa: E402


def test_graham_formula_positive_values():
    s = Stock(lpa=4.0, vpa=16.0, price=100.0)
    # Graham formula = sqrt(22.5 * lpa * vpa)
    expected = round((22.5 * 4.0 * 16.0) ** 0.5, 2)
    assert s.get_graham_formula() == expected


def test_discount_to_graham_calculation():
    s = Stock(lpa=1.0, vpa=4.0, price=50.0)
    graham = s.get_graham_formula()
    expected = round(((s.price - graham) / s.price) * 100, 2)
    assert s.get_discount_to_graham() == expected


def test_discount_to_graham_is_negative_when_price_below_graham():
    # Graham = sqrt(22.5 * 2 * 8) = 18.97, price 10 -> trading at a discount
    s = Stock(lpa=2.0, vpa=8.0, price=10.0)
    assert s.get_discount_to_graham() < 0


def test_graham_formula_is_none_for_loss_making_company():
    s = Stock(lpa=-3.0, vpa=16.0, price=100.0)
    assert s.get_graham_formula() is None


def test_graham_formula_is_none_for_negative_equity():
    s = Stock(lpa=4.0, vpa=-16.0, price=100.0)
    assert s.get_graham_formula() is None


def test_graham_formula_is_none_when_data_is_missing():
    assert Stock(lpa=None, vpa=16.0, price=100.0).get_graham_formula() is None
    assert Stock(lpa=4.0, vpa=None, price=100.0).get_graham_formula() is None


def test_discount_to_graham_is_none_when_graham_does_not_apply():
    # A loss-making company must not report 0.0, which would be
    # indistinguishable from a company priced exactly at fair value.
    s = Stock(lpa=-3.0, vpa=16.0, price=100.0)
    assert s.get_discount_to_graham() is None


def test_discount_to_graham_is_none_without_price():
    s = Stock(lpa=4.0, vpa=16.0, price=None)
    assert s.get_discount_to_graham() is None


def test_constructor_persists_none_for_loss_making_company():
    s = Stock(ticker="XPTO3", lpa=-1.0, vpa=5.0, price=20.0)
    assert s.graham_formula is None
    assert s.discount_to_graham is None
