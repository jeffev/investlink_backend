import logging
from datetime import date, datetime, timedelta

import requests
from flask import jsonify

_cache = {"data": None, "fetched_at": None}
_CACHE_TTL_HOURS = 24
_BCB_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
_TIMEOUT = 10


def _fetch_serie(serie, start_date, end_date):
    url = (
        _BCB_BASE.format(serie=serie) + f"?formato=json"
        f"&dataInicial={start_date.strftime('%d/%m/%Y')}"
        f"&dataFinal={end_date.strftime('%d/%m/%Y')}"
    )
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _compound(records):
    """Accumulates (1 + rate/100) for each record and returns the accumulated % - 1."""
    acc = 1.0
    for r in records:
        try:
            acc *= 1 + float(r["valor"].replace(",", ".")) / 100
        except (ValueError, KeyError):
            continue
    return round((acc - 1) * 100, 2)


def _is_cache_valid():
    if not _cache["data"] or not _cache["fetched_at"]:
        return False
    age = datetime.utcnow() - _cache["fetched_at"]
    return age.total_seconds() < _CACHE_TTL_HOURS * 3600


def _fetch_benchmarks():
    end = date.today()
    start_12m = end - timedelta(days=366)

    cdi_records = _fetch_serie(12, start_12m, end)
    ipca_records = _fetch_serie(433, start_12m, end)

    return {
        "cdi_12m": _compound(cdi_records),
        "ipca_12m": _compound(ipca_records),
        "fetched_at": date.today().isoformat(),
    }


def get_benchmarks():
    try:
        if _is_cache_valid():
            return jsonify(_cache["data"]), 200

        data = _fetch_benchmarks()
        _cache["data"] = data
        _cache["fetched_at"] = datetime.utcnow()
        return jsonify(data), 200
    except requests.exceptions.Timeout:
        logging.warning("BCB API timeout — returning cached or empty benchmarks")
        if _cache["data"]:
            return jsonify({**_cache["data"], "stale": True}), 200
        return jsonify({"cdi_12m": None, "ipca_12m": None, "fetched_at": None}), 200
    except Exception as e:
        logging.error(f"Benchmark fetch error: {e}")
        if _cache["data"]:
            return jsonify({**_cache["data"], "stale": True}), 200
        return jsonify({"cdi_12m": None, "ipca_12m": None, "fetched_at": None}), 200
