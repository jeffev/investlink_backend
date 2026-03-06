import logging
import json
import requests
from flask import jsonify

from models.fii import Fii
from models.favorite_fiis import FavoriteFii
from config import db

FII_ALLOWED_COLS = {
    "ticker",
    "companyname",
    "sectorname",
    "subsectorname",
    "segment",
    "price",
    "dy",
    "p_vp",
    "valorpatrimonialcota",
    "liquidezmediadiaria",
    "percentualcaixa",
    "dividend_cagr",
    "cota_cagr",
    "numerocotistas",
    "numerocotas",
    "patrimonio",
    "lastdividend",
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
        query = query.order_by(col.desc() if sort_dir == "desc" else col.asc())
    return query


def list_fiis(user_id, page=1, per_page=50, sort_by=None, sort_dir="asc", filters=None):
    try:
        per_page = min(per_page, 500)
        favorites = {
            fav.fii_ticker for fav in FavoriteFii.query.filter_by(user_id=user_id).all()
        }
        query = Fii.query
        query = _apply_filters_and_sort(
            query, Fii, FII_ALLOWED_COLS, sort_by, sort_dir, filters
        )
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        fiis_json = [
            {**fii.to_json(), "favorita": fii.ticker in favorites}
            for fii in paginated.items
        ]
        return (
            jsonify(
                {
                    "data": fiis_json,
                    "pagination": {
                        "total": paginated.total,
                        "pages": paginated.pages,
                        "current_page": paginated.page,
                        "per_page": per_page,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def view_fii(ticker):
    try:
        fii = db.session.get(Fii, ticker)
        if fii is None:
            return jsonify({"message": "FII not found"}), 404
        return jsonify(fii.to_json()), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def new_fii(fii_data):
    try:
        if Fii.query.filter_by(ticker=fii_data["ticker"]).first():
            return jsonify({"message": "FII already exists"}), 400

        new_fii = Fii(**fii_data)

        db.session.add(new_fii)
        db.session.commit()
        return jsonify({"message": "FII added successfully"}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def edit_fii(ticker, fii_data):
    try:
        fii = db.session.get(Fii, ticker)
        if fii is None:
            return jsonify({"message": "FII not found"}), 404

        for key, value in fii_data.items():
            setattr(fii, key, value)

        db.session.commit()
        return jsonify({"message": "FII edited successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def delete_fii(ticker):
    try:
        fii = db.session.get(Fii, ticker)
        if fii is None:
            return jsonify({"message": "FII not found"}), 404

        db.session.delete(fii)
        db.session.commit()
        return jsonify({"message": "FII deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def get_all_fiis_from_statusinvest():
    try:
        url = "https://statusinvest.com.br/category/advancedsearchresultpaginated"
        search_params = {
            "Segment": "",
            "Gestao": "",
            "my_range": "0;20",
            "dy": {"Item1": None, "Item2": None},
            "p_vp": {"Item1": None, "Item2": None},
            "percentualcaixa": {"Item1": None, "Item2": None},
            "numerocotistas": {"Item1": None, "Item2": None},
            "dividend_cagr": {"Item1": None, "Item2": None},
            "cota_cagr": {"Item1": None, "Item2": None},
            "liquidezmediadiaria": {"Item1": None, "Item2": None},
            "patrimonio": {"Item1": None, "Item2": None},
            "valorpatrimonialcota": {"Item1": None, "Item2": None},
            "numerocotas": {"Item1": None, "Item2": None},
            "lastdividend": {"Item1": None, "Item2": None},
        }
        params = {
            "search": json.dumps(search_params),
            "orderColumn": "",
            "isAsc": "",
            "page": 0,
            "take": 1000,
            "CategoryType": 2,
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(url, params=params, headers=headers)

        if response.status_code != 200:
            logging.error(f"HTTP error occurred: {response.status_code}")
            return None

        return response.json()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None


def update_all_fiis():
    try:
        fiis_data = get_all_fiis_from_statusinvest()
        if not fiis_data or "list" not in fiis_data:
            return jsonify({"error": "Error fetching FII data from StatusInvest."}), 500

        cached_fiis = fiis_data["list"]
        tickers = {fii["ticker"] for fii in cached_fiis}

        existing_fiis = Fii.query.filter(Fii.ticker.in_(tickers)).all()
        existing_tickers = {fii.ticker for fii in existing_fiis}

        numeric_fields = [
            "price",
            "sectorid",
            "subsectorid",
            "segmentid",
            "gestao",
            "dy",
            "p_vp",
            "valorpatrimonialcota",
            "liquidezmediadiaria",
            "percentualcaixa",
            "dividend_cagr",
            "cota_cagr",
            "numerocotistas",
            "numerocotas",
            "patrimonio",
            "lastdividend",
        ]

        for fii_data in cached_fiis:
            for field in numeric_fields:
                fii_data[field] = fii_data.get(field, 0.0)

        cached_map = {item["ticker"]: item for item in cached_fiis}
        for fii in existing_fiis:
            for key, value in cached_map[fii.ticker].items():
                setattr(fii, key, value)

        new_fiis = [
            Fii(**fii_data)
            for fii_data in cached_fiis
            if fii_data["ticker"] not in existing_tickers
        ]

        db.session.add_all(new_fiis)
        db.session.commit()
        return jsonify({"message": "FIIs updated successfully."}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
