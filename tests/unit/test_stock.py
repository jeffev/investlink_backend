import sys
import os

# Ensure the app folder is on sys.path so imports match runtime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.stock import Stock


def test_graham_formula_positive_values():
    s = Stock(lpa=4.0, vpa=16.0, price=100.0)
    # Graham formula = sqrt(22.5 * lpa * vpa)
    expected = round((22.5 * 4.0 * 16.0) ** 0.5, 2)
    assert s.get_graham_formula() == expected


def test_discount_to_graham_calculation():
    s = Stock(lpa=1.0, vpa=4.0, price=50.0)
    graham = s.get_graham_formula()
    expected = round(((s.price - graham) / s.price) * 100, 2) if s.price and graham else 0.0
    assert s.get_discount_to_graham() == expected
 
