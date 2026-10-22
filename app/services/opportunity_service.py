"""
Serves the ranked opportunities and the score behind each one.

The reasons and the red flags travel with every row on purpose. A score with
no explanation is a number nobody trusts, and a list that only argues for the
assets on it is an advertisement.
"""

import logging

from flask import jsonify

from models.fii import Fii
from models.fii_score import FiiScore
from models.stock import Stock
from models.stock_score import StockScore
from services.cvm_fundamentals_service import ticker_root
from services.fii_scoring_service import DEFAULT_FII_PROFILE, FII_PROFILES
from services.scoring_service import DEFAULT_PROFILE, PROFILES

DEFAULT_LIMIT = 12
MAX_LIMIT = 100

# Fields the card needs. Deliberately short — the full indicator set is one
# click away on the detail page.
CARD_FIELDS = (
    "ticker",
    "companyname",
    "sectorname",
    "price",
    "p_l",
    "p_vp",
    "dy",
    "roe",
    "roic",
    "graham_formula",
    "discount_to_graham",
    "fundamentals_source",
    "fundamentals_date",
)

# O card do FII mostra outra coisa: não há lucro por ação nem Graham, e o que
# decide a compra é desconto sobre o patrimônio, renda e quanto do imóvel está
# alugado.
FII_CARD_FIELDS = (
    "ticker",
    "companyname",
    "segment",
    "price",
    "p_vp",
    "dy",
    "ffo_yield",
    "cap_rate",
    "vacancia_media",
    "qtd_imoveis",
    "liquidezmediadiaria",
    "patrimonio",
    "valorpatrimonialcota",
)

PROFILE_LABELS = {
    "EQUILIBRADO": "Equilibrado",
    "VALOR": "Valor",
    "DIVIDENDOS": "Dividendos",
    "QUALIDADE": "Qualidade a preço justo",
    "CRESCIMENTO": "Crescimento",
    "RENDA": "Renda",
}

# Um descritor por tipo de ativo em vez de duas cópias da mesma função: a
# consulta, o recorte e o formato da resposta são idênticos — o que muda é a
# tabela, os pesos e os campos do card.
ASSET_TYPES = {
    "ACAO": {
        "model": Stock,
        "score_model": StockScore,
        "profiles": PROFILES,
        "default_profile": DEFAULT_PROFILE,
        "card_fields": CARD_FIELDS,
        # ON e PN da mesma empresa pontuam quase igual.
        "dedupe_share_classes": True,
    },
    "FII": {
        "model": Fii,
        "score_model": FiiScore,
        "profiles": FII_PROFILES,
        "default_profile": DEFAULT_FII_PROFILE,
        "card_fields": FII_CARD_FIELDS,
        # Fundo não tem classe de cota: cada ticker é um ativo distinto.
        "dedupe_share_classes": False,
    },
}

DEFAULT_ASSET_TYPE = "ACAO"


def _resolve_asset_type(asset_type):
    if not asset_type:
        return ASSET_TYPES[DEFAULT_ASSET_TYPE]
    return ASSET_TYPES.get(asset_type.strip().upper())


# ON and PN shares of the same company score almost identically, and a
# twelve-card shortlist that spends two slots on POMO3 and POMO4 is showing
# eleven ideas. Fetching a few extra rows leaves room to drop the duplicates.
SHARE_CLASS_HEADROOM = 3


def _one_class_per_company(scores):
    """Keeps the best-scoring share class of each company, order preserved."""
    seen = set()
    kept = []
    for score in scores:
        root = ticker_root(score.ticker) or score.ticker
        if root in seen:
            continue
        seen.add(root)
        kept.append(score)
    return kept


def _card(asset, score, card_fields):
    payload = {field: getattr(asset, field, None) for field in card_fields}
    if payload.get("fundamentals_date"):
        payload["fundamentals_date"] = payload["fundamentals_date"].isoformat()
    payload["score"] = score.to_json()
    return payload


def _resolve_profile(profile, asset):
    if not profile:
        return asset["default_profile"]
    normalized = profile.strip().upper()
    return normalized if normalized in asset["profiles"] else None


def list_opportunities(profile=None, limit=DEFAULT_LIMIT, asset_type=None):
    """Best-ranked eligible assets for a profile, highest score first."""
    try:
        asset = _resolve_asset_type(asset_type)
        if asset is None:
            return (
                jsonify(
                    {
                        "message": "Unknown asset type",
                        "asset_types": sorted(ASSET_TYPES),
                    }
                ),
                400,
            )

        resolved = _resolve_profile(profile, asset)
        if resolved is None:
            return (
                jsonify(
                    {
                        "message": "Unknown profile",
                        "profiles": sorted(asset["profiles"]),
                    }
                ),
                400,
            )

        score_model = asset["score_model"]
        limit = max(1, min(limit, MAX_LIMIT))
        headroom = SHARE_CLASS_HEADROOM if asset["dedupe_share_classes"] else 1
        ranked = (
            score_model.query.filter(
                score_model.profile == resolved,
                score_model.eligible.is_(True),
                score_model.score_total.isnot(None),
            )
            .order_by(score_model.score_total.desc())
            .limit(limit * headroom)
            .all()
        )
        if asset["dedupe_share_classes"]:
            ranked = _one_class_per_company(ranked)
        scores = ranked[:limit]
        if not scores:
            return jsonify({"profile": resolved, "data": []}), 200

        tickers = [score.ticker for score in scores]
        model = asset["model"]
        assets = {
            item.ticker: item
            for item in model.query.filter(model.ticker.in_(tickers)).all()
        }
        data = [
            _card(assets[score.ticker], score, asset["card_fields"])
            for score in scores
            if score.ticker in assets
        ]
        return jsonify({"profile": resolved, "data": data}), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def get_stock_score(ticker, profile=None, asset_type=None):
    """
    The score for one ticker, including the ineligible case.

    An excluded company still answers "why isn't this on the list?", which is
    the question a screener that simply hides it cannot.
    """
    try:
        asset = _resolve_asset_type(asset_type)
        if asset is None:
            return jsonify({"message": "Unknown asset type"}), 400

        resolved = _resolve_profile(profile, asset)
        if resolved is None:
            return jsonify({"message": "Unknown profile"}), 400

        score = (
            asset["score_model"]
            .query.filter_by(ticker=ticker, profile=resolved)
            .first()
        )
        if score is None:
            return jsonify({"message": "Score not found"}), 404

        return jsonify(score.to_json()), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def list_profiles(asset_type=None):
    """The weight sets the user can choose between, for one asset type."""
    try:
        asset = _resolve_asset_type(asset_type)
        if asset is None:
            return jsonify({"message": "Unknown asset type"}), 400

        data = [
            {
                "key": key,
                "label": PROFILE_LABELS.get(key, key.title()),
                "weights": weights,
                "default": key == asset["default_profile"],
            }
            for key, weights in asset["profiles"].items()
        ]
        return jsonify({"data": data}), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
