"""
Testa o score contra o passado — com as ressalvas que fazem o número valer algo.

**Look-ahead**: pontuar 2021 com o score de hoje é trapaça, e produz um
resultado espetacular e mentiroso. Cada ano é pontuado com os múltiplos
daquele ano (`stock_indicators_history`), que são derivados do balanço
entregue e do preço praticado à época. O score de 2021 não sabe nada de 2022.

**Viés de sobrevivência**: a tabela `stocks` só conhece quem existe hoje. Toda
empresa que quebrou e saiu da bolsa está ausente dos dois lados da conta —
tanto do decil de topo quanto da média do universo. O retorno absoluto sai
otimista, e isso vai declarado na resposta, não numa nota de rodapé.

**O comparador não é o Ibovespa**: é a média igualmente ponderada do próprio
universo pontuado naquele ano. Para um score que escolhe ações, "bateu a ação
média?" é a pergunta mais direta do que "bateu um índice ponderado por valor de
mercado" — e não exige chamar uma fonte externa dentro de um endpoint.
"""

import logging
from datetime import date, timedelta

from flask import jsonify
from config import db
from models.stock import Stock
from models.stock_indicator_history import StockIndicatorHistory
from models.stock_price_history import StockPriceHistory
from services.scoring_service import (
    DEFAULT_PROFILE,
    MIN_SECTOR_SIZE,
    PROFILES,
    _is_usable,
    compute_pillars,
    percentile_ranks,
    weighted_score,
)

# O histórico anual não tem CAGR, então o pilar de crescimento não existe aqui.
# `weighted_score` renormaliza os pesos em cima do que sobrou.
HISTORICAL_PILLAR_METRICS = {
    "valuation": [("p_l", True), ("p_vp", True), ("ev_ebit", True)],
    "qualidade": [("roe", False), ("m_liquida", False)],
    "saude": [("div_liq_ebit", True)],
    "dividendos": [("dy", False)],
}

TOP_DECILE = 0.10

# Abaixo disso o "decil de topo" vira duas ou três ações e o resultado é sorte.
MIN_UNIVERSE = 30

# Janela para achar o último pregão do ano — dezembro tem feriado e o papel
# pode simplesmente não ter negociado nos últimos dias.
YEAR_END_LOOKBACK_DAYS = 45


def _year_end_prices(years, tickers):
    """{(ticker, year): último fechamento do ano}, dentro da janela de busca."""
    if not years or not tickers:
        return {}

    windows = [
        (
            date(year, 12, 31) - timedelta(days=YEAR_END_LOOKBACK_DAYS),
            date(year, 12, 31),
        )
        for year in years
    ]
    earliest = min(start for start, _ in windows)
    latest = max(end for _, end in windows)

    rows = (
        StockPriceHistory.query.filter(
            StockPriceHistory.ticker.in_(tickers),
            StockPriceHistory.date >= earliest,
            StockPriceHistory.date <= latest,
        )
        .order_by(StockPriceHistory.date.asc())
        .all()
    )

    prices = {}
    for row in rows:
        if row.close_price is None:
            continue
        for window_start, window_end in windows:
            if window_start <= row.date <= window_end:
                # Ordenado por data: a última gravação do ano fica valendo.
                prices[(row.ticker, window_end.year)] = row.close_price
                break
    return prices


def _score_year(rows, sector_by_ticker, profile):
    """{ticker: score} de um ano, ranqueado dentro do setor daquele ano."""
    by_sector = {}
    for row in rows:
        by_sector.setdefault(
            sector_by_ticker.get(row.ticker) or "SEM SETOR", []
        ).append(row)

    groups = []
    market = []
    for members in by_sector.values():
        (groups if len(members) >= MIN_SECTOR_SIZE else market).append(members)
    if market:
        groups.append([row for members in market for row in members])

    percentiles = {row.ticker: {} for row in rows}
    for members in groups:
        for metrics in HISTORICAL_PILLAR_METRICS.values():
            for attribute, lower_is_better in metrics:
                values = {
                    row.ticker: getattr(row, attribute)
                    for row in members
                    if _is_usable(getattr(row, attribute, None))
                }
                for ticker, rank in percentile_ranks(values, lower_is_better).items():
                    percentiles[ticker][attribute] = rank

    scores = {}
    for ticker, metric_percentiles in percentiles.items():
        pillars = compute_pillars(metric_percentiles, HISTORICAL_PILLAR_METRICS)
        score = weighted_score(pillars, profile)
        if score is not None:
            scores[ticker] = score
    return scores


def _annual_return(ticker, year, prices):
    """Retorno do fim do ano `year` ao fim do ano seguinte."""
    start = prices.get((ticker, year))
    end = prices.get((ticker, year + 1))
    if not start or not end or start <= 0:
        return None
    return (end - start) / start * 100


def _evaluate_year(year, scores, prices):
    """Compara o decil de topo com a média do universo naquele ano."""
    returns = {}
    for ticker in scores:
        value = _annual_return(ticker, year, prices)
        if value is not None:
            returns[ticker] = value
    if len(returns) < MIN_UNIVERSE:
        return None

    ranked = sorted(returns, key=lambda ticker: scores[ticker], reverse=True)
    size = max(1, int(len(ranked) * TOP_DECILE))
    selected = ranked[:size]

    top = sum(returns[ticker] for ticker in selected) / len(selected)
    universe = sum(returns.values()) / len(returns)
    return {
        "year": year,
        "holding_period": f"{year}-12-31 → {year + 1}-12-31",
        "universe_size": len(returns),
        "selected": len(selected),
        "top_decile_return": round(top, 2),
        "universe_return": round(universe, 2),
        "excess_return": round(top - universe, 2),
        "tickers": selected,
    }


def _compound(returns):
    """Retorno acumulado de uma sequência de retornos anuais, em percentual."""
    total = 1.0
    for value in returns:
        total *= 1 + value / 100
    return round((total - 1) * 100, 2)


def _summarise(results):
    if not results:
        return None
    years = len(results)
    top = _compound([r["top_decile_return"] for r in results])
    universe = _compound([r["universe_return"] for r in results])

    def annualised(total):
        return round(((1 + total / 100) ** (1 / years) - 1) * 100, 2)

    return {
        "years": years,
        "top_decile_total": top,
        "universe_total": universe,
        "top_decile_annualised": annualised(top),
        "universe_annualised": annualised(universe),
        "beat_universe_in": sum(1 for r in results if r["excess_return"] > 0),
    }


def _caveats():
    """
    Ressalvas que viajam com o número, não abaixo dele.

    Um backtest sem as suas limitações ao lado é propaganda.
    """
    return [
        {
            "code": "VIES_SOBREVIVENCIA",
            "message": (
                "O universo só contém empresas que existem hoje. Quem quebrou e saiu "
                "da bolsa está fora dos dois lados da conta, então o retorno absoluto "
                "sai otimista."
            ),
        },
        {
            "code": "COMPARADOR_NAO_E_IBOV",
            "message": (
                "O comparador é a média igualmente ponderada do próprio universo "
                "pontuado, não o Ibovespa."
            ),
        },
        {
            "code": "SEM_CUSTOS",
            "message": (
                "Não há corretagem, imposto nem custo de rebalanceamento anual."
            ),
        },
        {
            "code": "AMOSTRA_CURTA",
            "message": (
                "A série de múltiplos anuais começa em 2020 — são poucos anos para "
                "concluir qualquer coisa sobre a estratégia."
            ),
        },
    ]


def backtest_score(profile=None):
    """Roda o score contra cada ano disponível do histórico."""
    try:
        resolved = (profile or "").strip().upper()
        if resolved and resolved not in PROFILES:
            return jsonify({"message": "Unknown profile"}), 400
        resolved = resolved or DEFAULT_PROFILE

        rows = StockIndicatorHistory.query.all()
        if not rows:
            return (
                jsonify(
                    {
                        "message": (
                            "Sem histórico de múltiplos — rode "
                            "run_price_history.py --indicators antes"
                        )
                    }
                ),
                409,
            )

        results = _run_years(rows, resolved)
        return (
            jsonify(
                {
                    "profile": resolved,
                    "summary": _summarise(results),
                    "years": results,
                    "caveats": _caveats(),
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def _run_years(rows, profile):
    """Pontua e avalia cada ano que tem o ano seguinte para medir o retorno."""
    sector_by_ticker = {
        ticker: sector
        for ticker, sector in db.session.query(Stock.ticker, Stock.sectorname).all()
    }
    by_year = {}
    for row in rows:
        by_year.setdefault(row.year, []).append(row)

    years = sorted(by_year)
    tickers = {row.ticker for row in rows}
    prices = _year_end_prices(years + [max(years) + 1], tickers)

    results = []
    for year in years:
        scores = _score_year(by_year[year], sector_by_ticker, profile)
        evaluation = _evaluate_year(year, scores, prices)
        if evaluation:
            results.append(evaluation)

    logging.info(f"Backtest do score ({profile}): {len(results)} anos avaliados")
    return results
