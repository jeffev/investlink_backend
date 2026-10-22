import logging
import json
import re
import cloudscraper
import requests
from flask import jsonify
from sqlalchemy import nulls_last
from sqlalchemy.exc import SQLAlchemyError

from models.fii import Fii
from models.favorite_fiis import FavoriteFii
from config import db
from models.fii_indicator_history import FiiIndicatorHistory
from models.fii_score import FiiScore
from services.fii_scoring_service import (
    DEFAULT_FII_PROFILE,
    FII_PROFILES,
    attach_score_fields,
    get_score_map,
    refresh_fii_scores,
)

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
    "ffo_yield",
    "qtd_imoveis",
    "cap_rate",
    "vacancia_media",
}

SCORE_COLUMN = "score_total"


def _resolve_profile(profile):
    normalized = (profile or "").strip().upper()
    return normalized if normalized in FII_PROFILES else DEFAULT_FII_PROFILE


def _join_score(query, profile):
    """Left join: fundo sem score continua aparecendo na tabela."""
    return query.outerjoin(
        FiiScore,
        db.and_(
            FiiScore.ticker == Fii.ticker,
            FiiScore.profile == profile,
        ),
    )


def _sort_by_score(query, sort_dir):
    direction = (
        FiiScore.score_total.desc()
        if sort_dir == "desc"
        else FiiScore.score_total.asc()
    )
    return query.order_by(nulls_last(direction))


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
        # An indicator that does not apply to a fund is NULL. Postgres puts
        # NULLs first on a descending sort, which would open the ranking on a
        # page of blanks instead of on the best-ranked assets.
        query = query.order_by(nulls_last(direction))
    return query


def list_fiis(
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
        favorites = {
            fav.fii_ticker for fav in FavoriteFii.query.filter_by(user_id=user_id).all()
        }
        resolved_profile = _resolve_profile(profile)
        query = _join_score(Fii.query, resolved_profile)
        if sort_by == SCORE_COLUMN:
            query = _apply_filters_and_sort(
                query, Fii, FII_ALLOWED_COLS, None, sort_dir, filters
            )
            query = _sort_by_score(query, sort_dir)
        else:
            query = _apply_filters_and_sort(
                query, Fii, FII_ALLOWED_COLS, sort_by, sort_dir, filters
            )
        if search:
            term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Fii.ticker.ilike(term),
                    Fii.companyname.ilike(term),
                )
            )
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        page_tickers = [fii.ticker for fii in paginated.items]
        score_map = get_score_map(page_tickers, resolved_profile)
        fiis_json = [
            attach_score_fields(
                {**fii.to_json(), "favorita": fii.ticker in favorites},
                score_map.get(fii.ticker),
            )
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


# Ruído que todo nome de fundo carrega e que não distingue um do outro.
_NAME_BOILERPLATE = re.compile(
    r"\b(fundos?\s+de\s+investimento\s+imobili[aá]ri[oa]s?"
    r"|fdo\.?\s+de\s+inv\.?\s+imob\.?"
    r"|fundo\s+de\s+inv\.?\s+imob\.?"
    r"|fii|responsabilidade\s+limitada|resp\.?\s+ltda\.?|rl)\b",
    re.IGNORECASE,
)
_VOWELS = set("AEIOU")
# Partícula do português fica minúscula no meio do nome. A primeira palavra
# nunca é partícula.
_PARTICLES = {"de", "da", "do", "das", "dos", "e"}
# Siglas com vogal, que a regra geral não pega. Levantadas contando os tokens
# de três e quatro letras nos 1.106 nomes que a CVM publica — o resto do que
# aparece nesse tamanho é palavra mesmo (RIO, REAL, LOG, NOVA).
_KNOWN_ACRONYMS = {"VBI", "HSI", "CDI", "CRI", "FOF", "CIX", "REC"}


def _humanize_token(token, first=False):
    """
    Sigla continua em caixa alta; partícula vira minúscula; o resto é
    capitalizado.

    `.title()` sozinho transforma CSHG em Cshg, VBI em Vbi e "de" em "De".
    Token sem vogal é sigla — CSHG, BTG, HGLG, RBR. Cortar por tamanho não
    funciona: entre os nomes publicados, "RIO" aparece 373 vezes e "LOG" 26,
    contra 9 de "VBI". As poucas siglas com vogal viraram lista explícita.
    """
    if not first and token.lower() in _PARTICLES:
        return token.lower()
    if token.isupper() and (
        len(token) <= 2 or token in _KNOWN_ACRONYMS or not (set(token) & _VOWELS)
    ):
        return token
    return token.capitalize()


def humanize_fund_name(raw):
    """
    'KINEA RENDA IMOBILIARIA FII RESPONSABILIDADE LIMITADA' -> 'Kinea Renda Imobiliaria'

    A CVM publica o nome em caixa alta e cercado de jargão jurídico. O que
    sobra depois de tirar o jargão é o que distingue um fundo do outro, que é
    o que o card precisa mostrar.
    """
    if not raw:
        return None

    limpo = _NAME_BOILERPLATE.sub(" ", raw)
    limpo = re.sub(r"[\s\-–,\.]+", " ", limpo).strip()

    # "BB PREMIUM MALLS FII DE RESPONSABILIDADE LIMITADA" perde o miolo e
    # sobra com um "de" pendurado no fim.
    tokens = _strip_particles(limpo.split())
    if not tokens:
        return None

    return " ".join(
        _humanize_token(token, first=indice == 0) for indice, token in enumerate(tokens)
    )


def _strip_particles(tokens):
    """Tira partícula solta nas pontas, que o jargão removido deixou para trás."""
    while tokens and tokens[0].lower() in _PARTICLES:
        tokens = tokens[1:]
    while tokens and tokens[-1].lower() in _PARTICLES:
        tokens = tokens[:-1]
    return tokens


def enrich_fii_names(fiis_data):
    """
    Preenche o nome do fundo a partir do Informe Mensal da CVM.

    O Fundamentus é a fonte primária e não publica nome: a coleta repetia o
    ticker no lugar, e o card mostrava "HGLG11" embaixo de "HGLG11". O informe
    mensal publica, e o pipeline já o guarda em `fii_indicators_history`.

    Falha de leitura não derruba a atualização: nome é enfeite, cotação não.
    """
    pendentes = [
        item["ticker"]
        for item in fiis_data
        if not item.get("companyname") or item["companyname"] == item["ticker"]
    ]
    if not pendentes:
        return

    try:
        linhas = (
            db.session.query(FiiIndicatorHistory.ticker, FiiIndicatorHistory.fund_name)
            .filter(
                FiiIndicatorHistory.ticker.in_(pendentes),
                FiiIndicatorHistory.fund_name.isnot(None),
            )
            .order_by(FiiIndicatorHistory.reference_date)
            .all()
        )
    except SQLAlchemyError as error:
        db.session.rollback()
        logging.error(f"Nome dos fundos indisponível: {error}")
        return

    # A ordenação é crescente, então o informe mais recente sobrescreve.
    nomes = {ticker: nome for ticker, nome in linhas}
    for item in fiis_data:
        nome = humanize_fund_name(nomes.get(item["ticker"]))
        if nome:
            item["companyname"] = nome


def _parse_br_float(value):
    if not value or value in ("-", ""):
        return 0.0
    value = value.strip().replace("%", "").replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return 0.0


def get_all_fiis_from_fundamentus():
    try:
        url = "https://www.fundamentus.com.br/fii_resultado.php"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            logging.error(f"Fundamentus HTTP error: {response.status_code}")
            return None

        html = response.text
        tbody_start = html.find("<tbody>")
        tbody_end = html.find("</tbody>")
        if tbody_start == -1:
            logging.error("Fundamentus: tbody não encontrado")
            return None

        tbody = html[tbody_start:tbody_end]
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL)

        fiis = []
        segmento_map = {}
        seg_counter = 1

        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            if len(cells) < 6:
                continue

            ticker = cells[0].strip()
            if not ticker or not re.match(r"^[A-Z]{4}[0-9]{2}$", ticker):
                continue

            segmento = cells[1].strip() or "Outros"
            if segmento not in segmento_map:
                segmento_map[segmento] = seg_counter
                seg_counter += 1

            price = _parse_br_float(cells[2])
            ffo_yield = _parse_br_float(cells[3])
            dy = _parse_br_float(cells[4])
            p_vp = _parse_br_float(cells[5])
            # A coluna 6 é "Valor de Mercado", não patrimônio — estava sendo
            # gravada como `patrimonio` e a tela mostrava capitalização no
            # lugar do patrimônio do fundo. O patrimônio sai do próprio P/VP,
            # que é justamente preço sobre valor patrimonial.
            valor_mercado = _parse_br_float(cells[6]) if len(cells) > 6 else 0.0
            liquidez = _parse_br_float(cells[7]) if len(cells) > 7 else 0.0
            qtd_imoveis = int(_parse_br_float(cells[8])) if len(cells) > 8 else 0
            cap_rate = _parse_br_float(cells[11]) if len(cells) > 11 else 0.0
            vacancia = _parse_br_float(cells[12]) if len(cells) > 12 else 0.0

            patrimonio = round(valor_mercado / p_vp, 2) if p_vp else 0.0
            vpa = round(price / p_vp, 2) if p_vp and p_vp != 0 else 0.0

            fiis.append(
                {
                    "ticker": ticker,
                    "companyname": ticker,
                    "price": price,
                    "dy": dy,
                    "p_vp": p_vp,
                    "sectorname": segmento,
                    "subsectorname": segmento,
                    "segment": segmento,
                    "sectorid": segmento_map[segmento],
                    "subsectorid": segmento_map[segmento],
                    "segmentid": segmento_map[segmento],
                    "patrimonio": patrimonio,
                    "liquidezmediadiaria": liquidez,
                    "valorpatrimonialcota": vpa,
                    "gestao": 0,
                    "gestao_f": "",
                    "percentualcaixa": 0.0,
                    "dividend_cagr": 0.0,
                    "cota_cagr": 0.0,
                    "numerocotistas": 0.0,
                    "numerocotas": 0.0,
                    "lastdividend": 0.0,
                    "ffo_yield": ffo_yield,
                    "qtd_imoveis": qtd_imoveis,
                    "cap_rate": cap_rate,
                    "vacancia_media": vacancia,
                }
            )

        logging.info(f"Fundamentus: {len(fiis)} FIIs coletados")
        return {"list": fiis}
    except Exception as e:
        logging.error(f"Erro ao buscar FIIs do Fundamentus: {e}")
        return None


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
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, params=params)

        if response.status_code != 200:
            logging.error(f"HTTP error occurred: {response.status_code}")
            return None

        return response.json()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None


def update_all_fiis():
    try:
        fiis_data = get_all_fiis_from_fundamentus()
        if not fiis_data or "list" not in fiis_data:
            logging.error("Fundamentus falhou, tentando StatusInvest...")
            fiis_data = get_all_fiis_from_statusinvest()
        if not fiis_data or "list" not in fiis_data:
            logging.error("Ambas as fontes falharam ao buscar FIIs")
            return jsonify({"error": "Error fetching FII data."}), 500

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
            "ffo_yield",
            "qtd_imoveis",
            "cap_rate",
            "vacancia_media",
        ]

        for fii_data in cached_fiis:
            for field in numeric_fields:
                fii_data[field] = fii_data.get(field, 0.0)

        enrich_fii_names(cached_fiis)

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

        # O score entra aqui, e não num pipeline à parte, pelo mesmo motivo do
        # score de ação: pipeline separado é o que deixou a vitrine vazia.
        refresh_fii_scores()

        return jsonify({"message": "FIIs updated successfully."}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
