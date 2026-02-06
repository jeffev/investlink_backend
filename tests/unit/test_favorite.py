import sys
import os

# Ensure the app folder is on sys.path so imports match runtime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.favorite import Favorite  # noqa: E402
from models.stock import Stock  # noqa: E402


def test_favorite_to_json_includes_stock():
    s = Stock(ticker="TST", companyname="Test Co", price=10.0, lpa=1.0, vpa=4.0)
    f = Favorite(id=1, user_id=2, ceiling_price=12.0, target_price=8.0)
    f.stock = s

    result = f.to_json()
    assert result["id"] == 1
    assert result["user_id"] == 2
    assert isinstance(result["stock"], dict)
    assert result["stock"]["ticker"] == "TST"
    assert result["ceiling_price"] == 12.0
    assert result["target_price"] == 8.0
