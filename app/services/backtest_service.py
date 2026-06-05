import json
import logging
from datetime import date, datetime, timedelta

import requests
from flask import jsonify

from config import db
from models.stock import Stock
from models.stock_price_history import StockPriceHistory
from models.strategy import Strategy
from services.stock_services import STOCK_ALLOWED_COLS, _apply_filters_and_sort

_BCB_CDI_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
_TIMEOUT = 10
_MAX_TICKERS = 50


def _fetch_cdi_rates(start_date, end_date):
    url = (
        _BCB_CDI_URL
        + "?formato=json"
        + f"&dataInicial={start_date.strftime('%d/%m/%Y')}"
        + f"&dataFinal={end_date.strftime('%d/%m/%Y')}"
    )
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    result = {}
    for r in resp.json():
        try:
            d = datetime.strptime(r["data"], "%d/%m/%Y").date()
            result[d] = float(r["valor"].replace(",", ".")) / 100
        except (ValueError, KeyError):
            continue
    return result


def _calc_max_drawdown(series):
    peak = series[0]
    max_dd = 0.0
    for v in series:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)


def run_backtest(strategy_id, user_id, start_date_str):
    try:
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                return (
                    jsonify({"message": "Invalid start_date format. Use YYYY-MM-DD"}),
                    400,
                )
        else:
            start_date = date.today() - timedelta(days=365)

        strategy = db.session.get(Strategy, strategy_id)
        if strategy is None:
            return jsonify({"message": "Strategy not found"}), 404
        if strategy.user_id != user_id:
            return jsonify({"message": "Unauthorized"}), 403
        if strategy.asset_type != "STOCK":
            return (
                jsonify({"message": "Backtest available only for STOCK strategies"}),
                400,
            )

        filters = json.loads(strategy.filters or "[]")
        sorting_raw = json.loads(strategy.sorting) if strategy.sorting else []

        if sorting_raw:
            sort_by = sorting_raw[0]["id"]
            sort_dir = "desc" if sorting_raw[0].get("desc", False) else "asc"
        else:
            sort_by = None
            sort_dir = "asc"

        query = Stock.query
        query = _apply_filters_and_sort(
            query, Stock, STOCK_ALLOWED_COLS, sort_by, sort_dir, filters
        )
        stocks = query.limit(_MAX_TICKERS).all()

        if not stocks:
            return jsonify({"message": "No stocks match this strategy's filters"}), 400

        tickers = [s.ticker for s in stocks]

        ticker_prices = {}
        for ticker in tickers:
            records = (
                StockPriceHistory.query.filter(
                    StockPriceHistory.ticker == ticker,
                    StockPriceHistory.date >= start_date,
                    StockPriceHistory.close_price.isnot(None),
                )
                .order_by(StockPriceHistory.date.asc())
                .all()
            )
            if len(records) >= 2:
                ticker_prices[ticker] = {r.date: r.close_price for r in records}

        if not ticker_prices:
            return (
                jsonify(
                    {"message": "No historical price data available for these stocks"}
                ),
                400,
            )

        date_sets = [set(prices.keys()) for prices in ticker_prices.values()]
        common_dates = sorted(date_sets[0].intersection(*date_sets[1:]))

        if len(common_dates) < 2:
            return (
                jsonify({"message": "Not enough common price data to run backtest"}),
                400,
            )

        first_date = common_dates[0]
        last_date = common_dates[-1]

        ticker_normalized = {}
        for ticker, prices in ticker_prices.items():
            base = prices.get(first_date)
            if base and base > 0:
                ticker_normalized[ticker] = {
                    d: (prices[d] / base) * 100 for d in common_dates
                }

        if not ticker_normalized:
            return jsonify({"message": "Could not normalize price data"}), 400

        portfolio_series = []
        for d in common_dates:
            values = [ticker_normalized[t][d] for t in ticker_normalized]
            portfolio_series.append(
                {"date": d.isoformat(), "value": round(sum(values) / len(values), 2)}
            )

        cdi_series = []
        try:
            cdi_rates = _fetch_cdi_rates(first_date, last_date)
            cdi_value = 100.0
            cdi_by_date = {}
            for d in common_dates:
                rate = cdi_rates.get(d, 0.0)
                cdi_value *= 1 + rate
                cdi_by_date[d] = round(cdi_value, 2)
            cdi_series = [
                {"date": d.isoformat(), "value": cdi_by_date[d]} for d in common_dates
            ]
        except Exception as e:
            logging.warning(f"CDI fetch failed during backtest: {e}")
            cdi_series = [{"date": d.isoformat(), "value": None} for d in common_dates]

        final_value = portfolio_series[-1]["value"]
        total_return = round(final_value - 100, 2)

        n_years = (last_date - first_date).days / 365.25
        cagr = (
            round(((final_value / 100) ** (1 / n_years) - 1) * 100, 2)
            if n_years > 0
            else 0.0
        )

        pv = [p["value"] for p in portfolio_series]
        max_drawdown = _calc_max_drawdown(pv)

        cdi_final = (
            cdi_series[-1]["value"]
            if cdi_series and cdi_series[-1]["value"] is not None
            else None
        )
        cdi_total_return = round(cdi_final - 100, 2) if cdi_final else None

        ticker_returns = []
        for ticker, norm in ticker_normalized.items():
            ticker_returns.append(
                {"ticker": ticker, "return": round(norm[last_date] - 100, 2)}
            )
        ticker_returns.sort(key=lambda x: x["return"], reverse=True)

        best = ticker_returns[0] if ticker_returns else None
        worst = ticker_returns[-1] if ticker_returns else None

        return (
            jsonify(
                {
                    "tickers": list(ticker_normalized.keys()),
                    "start_date": first_date.isoformat(),
                    "end_date": last_date.isoformat(),
                    "portfolio_series": portfolio_series,
                    "cdi_series": cdi_series,
                    "metrics": {
                        "total_return": total_return,
                        "cagr": cagr,
                        "max_drawdown": max_drawdown,
                        "ticker_count": len(ticker_normalized),
                        "cdi_total_return": cdi_total_return,
                        "best_ticker": best,
                        "worst_ticker": worst,
                    },
                    "ticker_returns": ticker_returns,
                }
            ),
            200,
        )

    except Exception as e:
        logging.error(f"Backtest error: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
