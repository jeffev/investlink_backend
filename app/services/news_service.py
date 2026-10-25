import json
import logging
import os
from datetime import datetime

import requests
from flask import jsonify

from models.stock import Stock

_cache = {}
_CACHE_TTL_HOURS = 1
_NEWSAPI_URL = "https://newsapi.org/v2/everything"
_TIMEOUT = 10
_DEFAULT_QUERY = "bolsa OR ibovespa OR investimento OR B3"
# A chave do cache é a lista de tickers que o cliente manda, então sem teto
# cada combinação inventada guardava 100 artigos na memória do worker.
_MAX_CACHE_ENTRIES = 200
_SAFE_URL_PREFIXES = ("https://", "http://")


def _safe_url(url):
    # O link vira `href` no frontend: um `javascript:` vindo da fonte de
    # notícias executaria no domínio da aplicação, onde fica o token.
    if isinstance(url, str) and url.lower().startswith(_SAFE_URL_PREFIXES):
        return url
    return None


def _is_cache_valid(entry):
    if not entry or not entry.get("fetched_at"):
        return False
    age = datetime.utcnow() - entry["fetched_at"]
    return age.total_seconds() < _CACHE_TTL_HOURS * 3600


def _build_query(tickers):
    if not tickers:
        return _DEFAULT_QUERY
    parts = []
    for ticker in tickers[:5]:
        stock = Stock.query.filter_by(ticker=ticker).first()
        if stock and stock.companyname:
            parts.append(f'"{ticker}" OR "{stock.companyname}"')
        else:
            parts.append(f'"{ticker}"')
    return " OR ".join(parts)


def get_news(tickers, page, per_page):
    try:
        api_key = os.environ.get("NEWS_API_KEY", "")
        if not api_key:
            return (
                jsonify(
                    {
                        "articles": [],
                        "total_results": 0,
                        "message": "NEWS_API_KEY not configured",
                    }
                ),
                200,
            )

        cache_key = json.dumps(sorted(tickers))
        cache_entry = _cache.get(cache_key)

        if _is_cache_valid(cache_entry):
            articles = cache_entry["articles"]
        else:
            query = _build_query(tickers)
            params = {
                "q": query,
                "language": "pt",
                "sortBy": "publishedAt",
                "pageSize": 100,
                "apiKey": api_key,
            }
            resp = requests.get(_NEWSAPI_URL, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            if len(_cache) >= _MAX_CACHE_ENTRIES:
                _cache.clear()
            _cache[cache_key] = {"articles": articles, "fetched_at": datetime.utcnow()}

        offset = (page - 1) * per_page
        page_articles = articles[offset : offset + per_page]

        return (
            jsonify(
                {
                    "articles": [
                        {
                            "title": a.get("title"),
                            "description": a.get("description"),
                            "url": _safe_url(a.get("url")),
                            "urlToImage": _safe_url(a.get("urlToImage")),
                            "publishedAt": a.get("publishedAt"),
                            "source": a.get("source", {}).get("name"),
                        }
                        for a in page_articles
                    ],
                    "total_results": len(articles),
                    "page": page,
                    "per_page": per_page,
                }
            ),
            200,
        )

    except requests.exceptions.Timeout:
        logging.warning("NewsAPI timeout")
        return (
            jsonify(
                {
                    "articles": [],
                    "total_results": 0,
                    "message": "Service temporarily unavailable",
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"News service error: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
