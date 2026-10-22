"""
Compares a stock's current multiples against its own history.

A P/L of 8 says nothing on its own. A P/L of 8 for a company that traded at a
median of 12.6 over the last five years says the market is pricing it below its
own norm — which is the question an investor actually asks.

This is deliberately about the company against itself. Sector comparison already
happens in the data science pipeline (feature_engineer.add_sector_zscores).
"""

import logging
from datetime import date
from statistics import median

from flask import jsonify

from models.stock import Stock
from models.stock_indicator_history import StockIndicatorHistory

# Multiples worth comparing against the company's own past. Deliberately short:
# these are the ones whose historical band an investor can actually read.
TRACKED_INDICATORS = [
    {"key": "p_l", "label": "P/L", "lower_is_better": True},
    {"key": "p_vp", "label": "P/VP", "lower_is_better": True},
    {"key": "ev_ebit", "label": "EV/EBIT", "lower_is_better": True},
    {"key": "dy", "label": "Dividend Yield", "lower_is_better": False},
]

DEFAULT_YEARS = 5

# Below this many completed years the median is noise, not a reference.
MIN_YEARS = 3

# How far from the median the current value must sit before we call it
# cheap or expensive instead of in line.
DEVIATION_BAND_PERCENT = 10.0


def _percentile_of(values, current):
    """Share of historical values strictly below `current`, as 0-100."""
    if not values:
        return None
    below = sum(1 for value in values if value < current)
    return round((below / len(values)) * 100, 1)


def _verdict(deviation_percent, lower_is_better):
    if abs(deviation_percent) < DEVIATION_BAND_PERCENT:
        return "EM_LINHA"
    is_below = deviation_percent < 0
    if is_below:
        return "BARATO" if lower_is_better else "CARO"
    return "CARO" if lower_is_better else "BARATO"


def _build_indicator_context(indicator, current, history_rows):
    """
    Returns the context dict for one indicator, or None when the company does
    not have enough completed years to compare against.
    """
    key = indicator["key"]
    if current is None:
        return None

    samples = [
        (row.year, getattr(row, key))
        for row in history_rows
        if getattr(row, key) is not None
    ]
    if len(samples) < MIN_YEARS:
        return None

    values = [value for _, value in samples]
    historical_median = median(values)
    if not historical_median:
        return None

    deviation_percent = ((current - historical_median) / abs(historical_median)) * 100

    return {
        "key": key,
        "label": indicator["label"],
        "lower_is_better": indicator["lower_is_better"],
        "current": round(current, 2),
        "median": round(historical_median, 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "deviation_percent": round(deviation_percent, 2),
        "percentile": _percentile_of(values, current),
        "verdict": _verdict(deviation_percent, indicator["lower_is_better"]),
        "years": sorted(year for year, _ in samples),
    }


def get_historical_context(ticker, years=DEFAULT_YEARS):
    """
    Builds, for each tracked multiple, where the company trades today relative
    to its own median over the last `years` completed fiscal years.
    """
    try:
        stock = Stock.query.get(ticker)
        if stock is None:
            return jsonify({"message": "Stock not found"}), 404

        # The running year is still open — its indicators would be a partial
        # snapshot competing with closed years in the same median.
        last_closed_year = date.today().year - 1
        first_year = last_closed_year - years + 1

        history_rows = (
            StockIndicatorHistory.query.filter(
                StockIndicatorHistory.ticker == ticker,
                StockIndicatorHistory.year >= first_year,
                StockIndicatorHistory.year <= last_closed_year,
            )
            .order_by(StockIndicatorHistory.year.asc())
            .all()
        )

        indicators = []
        for indicator in TRACKED_INDICATORS:
            context = _build_indicator_context(
                indicator, getattr(stock, indicator["key"], None), history_rows
            )
            if context is not None:
                indicators.append(context)

        return (
            jsonify(
                {
                    "ticker": ticker,
                    "years_requested": years,
                    "years_available": len(history_rows),
                    "indicators": indicators,
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
