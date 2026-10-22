import logging
import json
from datetime import date

import cloudscraper
from flask import jsonify
from sqlalchemy import func, nulls_last
from models.stock import Stock
from models.stock_price_history import StockPriceHistory
from models.favorite import Favorite
from config import db
from services.prediction_service import get_latest_predictions_map, attach_ml_fields
from services.cvm_fundamentals_service import enrich_with_cvm
from models.stock_score import StockScore
from services.scoring_service import (
    DEFAULT_PROFILE,
    PROFILES,
    attach_score_fields,
    get_score_map,
    refresh_scores,
)

STOCK_ALLOWED_COLS = {
    "ticker",
    "companyname",
    "sectorname",
    "subsectorname",
    "segmentname",
    "price",
    "p_l",
    "dy",
    "p_vp",
    "p_ebit",
    "p_ativo",
    "ev_ebit",
    "margembruta",
    "margemebit",
    "margemliquida",
    "p_capitalgiro",
    "p_ativocirculante",
    "giroativos",
    "roe",
    "roa",
    "roic",
    "dividaliquidapatrimonioliquido",
    "dividaliquidaebit",
    "pl_ativo",
    "passivo_ativo",
    "liquidezcorrente",
    "peg_ratio",
    "receitas_cagr5",
    "lucros_cagr5",
    "liquidezmediadiaria",
    "vpa",
    "lpa",
    "valormercado",
    "graham_formula",
    "discount_to_graham",
    "roic_rank",
    "ey_rank",
    "magic_formula_rank",
    # Lets the screener isolate the companies already running on audited
    # figures. fundamentals_date stays out: the range filter below coerces
    # values with float(), which a date cannot survive.
    "fundamentals_source",
}


def _apply_filters_and_sort(query, model, allowed_cols, sort_by, sort_dir, filters):
    if filters:
        for f in filters:
            col_id = f.get("id")
            value = f.get("value")
            if col_id not in allowed_cols or value is None:
                continue
            col = getattr(model, col_id)
            if isinstance(value, list):
                min_val, max_val = value[0], value[1]
                if min_val not in (None, ""):
                    query = query.filter(col >= float(min_val))
                if max_val not in (None, ""):
                    query = query.filter(col <= float(max_val))
            elif value != "":
                query = query.filter(col.ilike(f"%{value}%"))
    if sort_by and sort_by in allowed_cols:
        col = getattr(model, sort_by)
        direction = col.desc() if sort_dir == "desc" else col.asc()
        # An indicator that does not apply to a company is NULL. Postgres puts
        # NULLs first on a descending sort, which would open the ranking on a
        # page of blanks instead of on the best-ranked assets.
        query = query.order_by(nulls_last(direction))
    return query


def _get_peak_map(tickers):
    if not tickers:
        return {}
    rows = (
        db.session.query(
            StockPriceHistory.ticker,
            func.max(StockPriceHistory.high).label("peak_high"),
        )
        .filter(StockPriceHistory.ticker.in_(tickers))
        .group_by(StockPriceHistory.ticker)
        .all()
    )
    return {row.ticker: row.peak_high for row in rows}


def _compute_queda_do_topo(price, peak):
    if not peak or not price:
        return None
    return round(((price - peak) / peak) * 100, 2)


# The fundamental score lives in its own table, one row per ticker per
# profile, so the table has to join to sort or filter by it. Sorting on a
# column the user can see but the server cannot order by is worse than not
# offering the column at all.
SCORE_COLUMN = "score_total"


def _resolve_profile(profile):
    normalized = (profile or "").strip().upper()
    return normalized if normalized in PROFILES else DEFAULT_PROFILE


def _join_score(query, profile):
    """Left join so a company without a score still shows up in the table."""
    return query.outerjoin(
        StockScore,
        db.and_(
            StockScore.ticker == Stock.ticker,
            StockScore.profile == profile,
        ),
    )


def _sort_by_score(query, sort_dir):
    direction = (
        StockScore.score_total.desc()
        if sort_dir == "desc"
        else StockScore.score_total.asc()
    )
    return query.order_by(nulls_last(direction))


def list_stocks(
    user_id,
    page=1,
    per_page=50,
    sort_by=None,
    sort_dir="asc",
    filters=None,
    search=None,
    profile=None,
):
    try:
        per_page = min(per_page, 500)
        resolved_profile = _resolve_profile(profile)
        favorites = {
            fav.stock_ticker for fav in Favorite.query.filter_by(user_id=user_id).all()
        }
        # The screener shows what can still be bought. view_stock and
        # bulk_view_stocks keep serving delisted tickers so a portfolio holding
        # one does not lose it.
        query = _join_score(
            Stock.query.filter(Stock.active.is_(True)), resolved_profile
        )
        if sort_by == SCORE_COLUMN:
            query = _apply_filters_and_sort(
                query, Stock, STOCK_ALLOWED_COLS, None, sort_dir, filters
            )
            query = _sort_by_score(query, sort_dir)
        else:
            query = _apply_filters_and_sort(
                query, Stock, STOCK_ALLOWED_COLS, sort_by, sort_dir, filters
            )
        if search:
            term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Stock.ticker.ilike(term),
                    Stock.companyname.ilike(term),
                )
            )
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        pred_map = get_latest_predictions_map()
        page_tickers = [s.ticker for s in paginated.items]
        peak_map = _get_peak_map(page_tickers)
        score_map = get_score_map(page_tickers, resolved_profile)
        stocks_json = [
            attach_score_fields(
                attach_ml_fields(
                    {
                        **stock.to_json(),
                        "favorita": stock.ticker in favorites,
                        "queda_do_topo": _compute_queda_do_topo(
                            stock.price, peak_map.get(stock.ticker)
                        ),
                    },
                    pred_map.get(stock.ticker),
                ),
                score_map.get(stock.ticker),
            )
            for stock in paginated.items
        ]
        return (
            jsonify(
                {
                    "data": stocks_json,
                    "pagination": {
                        "total": paginated.total,
                        "pages": paginated.pages,
                        "current_page": paginated.page,
                        "per_page": per_page,
                    },
                    "profile": resolved_profile,
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def view_stock(ticker):
    try:
        stock = db.session.get(Stock, ticker)
        if not stock:
            return jsonify({"message": "Stock not found"}), 404
        pred = get_latest_predictions_map().get(ticker)
        score = get_score_map([ticker], DEFAULT_PROFILE).get(ticker)
        payload = attach_score_fields(attach_ml_fields(stock.to_json(), pred), score)
        return jsonify(payload), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def bulk_view_stocks(tickers):
    try:
        if not tickers:
            return jsonify([]), 200
        stocks = Stock.query.filter(Stock.ticker.in_(tickers)).all()
        pred_map = get_latest_predictions_map()
        result = [attach_ml_fields(s.to_json(), pred_map.get(s.ticker)) for s in stocks]
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def new_stock(stock_data):
    try:
        if Stock.query.filter_by(ticker=stock_data["ticker"]).first():
            return jsonify({"message": "Stock already exists"}), 400

        new_stock = Stock(**stock_data)
        new_stock.graham_formula = new_stock.get_graham_formula()
        new_stock.discount_to_graham = new_stock.get_discount_to_graham()

        db.session.add(new_stock)
        db.session.commit()
        return jsonify({"message": "Stock added successfully"}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def edit_stock(ticker, stock_data):
    try:
        stock = db.session.get(Stock, ticker)
        if not stock:
            return jsonify({"message": "Stock not found"}), 404

        for key, value in stock_data.items():
            setattr(stock, key, value)

        stock.graham_formula = stock.get_graham_formula()
        stock.discount_to_graham = stock.get_discount_to_graham()

        db.session.commit()
        return jsonify({"message": "Stock edited successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def delete_stock(ticker):
    try:
        stock = db.session.get(Stock, ticker)
        if not stock:
            return jsonify({"message": "Stock not found"}), 404

        db.session.delete(stock)
        db.session.commit()
        return jsonify({"message": "Stock deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def get_all_stocks_from_statusinvest():
    try:
        url = "https://statusinvest.com.br/category/advancedsearchresultpaginated"
        search_params = {
            "Sector": "",
            "SubSector": "",
            "Segment": "",
            "my_range": "-20;100",
            "forecast": {
                "upsidedownside": {"Item1": None, "Item2": None},
                "estimatesnumber": {"Item1": None, "Item2": None},
                "revisedup": True,
                "reviseddown": True,
                "consensus": [],
            },
            "dy": {"Item1": None, "Item2": None},
            "p_l": {"Item1": None, "Item2": None},
            "peg_ratio": {"Item1": None, "Item2": None},
            "p_vp": {"Item1": None, "Item2": None},
            "p_ativo": {"Item1": None, "Item2": None},
            "margembruta": {"Item1": None, "Item2": None},
            "margemebit": {"Item1": None, "Item2": None},
            "margemliquida": {"Item1": None, "Item2": None},
            "p_ebit": {"Item1": None, "Item2": None},
            "ev_ebit": {"Item1": None, "Item2": None},
            "dividaliquidaebit": {"Item1": None, "Item2": None},
            "dividaliquidapatrimonioliquido": {"Item1": None, "Item2": None},
            "p_sr": {"Item1": None, "Item2": None},
            "p_capitalgiro": {"Item1": None, "Item2": None},
            "p_ativocirculante": {"Item1": None, "Item2": None},
            "roe": {"Item1": None, "Item2": None},
            "roic": {"Item1": None, "Item2": None},
            "roa": {"Item1": None, "Item2": None},
            "liquidezcorrente": {"Item1": None, "Item2": None},
            "pl_ativo": {"Item1": None, "Item2": None},
            "passivo_ativo": {"Item1": None, "Item2": None},
            "giroativos": {"Item1": None, "Item2": None},
            "receitas_cagr5": {"Item1": None, "Item2": None},
            "lucros_cagr5": {"Item1": None, "Item2": None},
            "liquidezmediadiaria": {"Item1": None, "Item2": None},
            "vpa": {"Item1": None, "Item2": None},
            "lpa": {"Item1": None, "Item2": None},
            "valormercado": {"Item1": None, "Item2": None},
        }
        params = {
            "search": json.dumps(search_params),
            "orderColumn": "",
            "isAsc": "",
            "page": 0,
            "take": 1000,
            "CategoryType": 1,
        }
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, params=params)

        if response.status_code != 200:
            logging.error(f"HTTP error occurred: {response.status_code}")
            return None

        return response.json()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None


def mark_delisted(returned_tickers):
    """
    Flags every stock the source stopped returning.

    Marked, never deleted: a user can hold a delisted ticker in their portfolio,
    and removing the row would take their position with it. Reappearing is
    handled too — a ticker that comes back is reactivated rather than left
    contradicting the fresh price beside it.
    """
    if not returned_tickers:
        # An empty payload is a failed fetch, not a market that closed.
        return 0

    today = date.today()
    delisted = Stock.query.filter(Stock.ticker.notin_(returned_tickers)).all()
    for stock in delisted:
        if stock.active:
            stock.active = False
            stock.delisted_at = today

    revived = Stock.query.filter(
        Stock.ticker.in_(returned_tickers), Stock.active.is_(False)
    ).all()
    for stock in revived:
        stock.active = True
        stock.delisted_at = None

    if delisted or revived:
        logging.info(
            f"Delisting: {len(delisted)} inactive, {len(revived)} back on the exchange"
        )
    return len(delisted)


def calculate_ey(stock_data):
    earnings = stock_data.get("lpa", 0)
    price = stock_data.get("price", 0)
    ey = earnings / price if price != 0 else 0
    return ey


def update_all_stocks():
    try:
        stocks_data = get_all_stocks_from_statusinvest()
        if not stocks_data or "list" not in stocks_data:
            return (
                jsonify({"error": "Error fetching stock data from StatusInvest."}),
                500,
            )

        cached_stocks = stocks_data["list"]
        tickers = {stock["ticker"] for stock in cached_stocks}

        existing_stocks = Stock.query.filter(Stock.ticker.in_(tickers)).all()
        existing_map = {stock.ticker: stock for stock in existing_stocks}
        existing_tickers = set(existing_map.keys())

        numeric_fields = [
            "price",
            "p_l",
            "dy",
            "p_vp",
            "p_ebit",
            "p_ativo",
            "ev_ebit",
            "margembruta",
            "margemebit",
            "margemliquida",
            "p_sr",
            "p_capitalgiro",
            "p_ativocirculante",
            "giroativos",
            "roe",
            "roa",
            "roic",
            "dividaliquidapatrimonioliquido",
            "dividaliquidaebit",
            "pl_ativo",
            "passivo_ativo",
            "liquidezcorrente",
            "peg_ratio",
            "receitas_cagr5",
            "vpa",
            "lpa",
            "valormercado",
        ]

        # Audited figures first: the earnings yield and the magic formula
        # ranks below have to be computed on the numbers that will actually be
        # stored, not on the scraped ones they replace.
        enrich_with_cvm(cached_stocks)

        for stock_data in cached_stocks:
            stock_data["ey"] = calculate_ey(stock_data)
            for field in numeric_fields:
                stock_data.setdefault(field, 0.0)

        ey_ranks = {
            stock["ticker"]: rank + 1
            for rank, stock in enumerate(
                sorted(cached_stocks, key=lambda x: x["ey"], reverse=True)
            )
        }

        roic_ranks = {
            stock["ticker"]: rank + 1
            for rank, stock in enumerate(
                sorted(cached_stocks, key=lambda x: x["roic"], reverse=True)
            )
        }

        new_stocks = []
        for stock_data in cached_stocks:
            stock_data["roic_rank"] = roic_ranks[stock_data["ticker"]]
            stock_data["ey_rank"] = ey_ranks[stock_data["ticker"]]
            stock_data["magic_formula_rank"] = (
                stock_data["roic_rank"] + stock_data["ey_rank"]
            )

            if stock_data["ticker"] in existing_tickers:
                stock = existing_map[stock_data["ticker"]]
                for key, value in stock_data.items():
                    setattr(stock, key, value)
                stock.graham_formula = stock.get_graham_formula()
                stock.discount_to_graham = stock.get_discount_to_graham()
                stock.roic_rank = stock_data["roic_rank"]
                stock.ey_rank = stock_data["ey_rank"]
                stock.magic_formula_rank = stock_data["magic_formula_rank"]
            else:
                new_stocks.append(Stock(**{**stock_data}))

        db.session.add_all(new_stocks)
        mark_delisted(tickers)
        db.session.commit()

        # The score describes this snapshot, so it is rebuilt with it. Keeping
        # it in a separate pipeline is what left the opportunities page empty.
        refresh_scores()

        return jsonify({"message": "Stocks updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
