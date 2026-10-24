"""
Ranks companies on five pillars, inside their own sector.

Why not one formula with a weight on the Graham number:
    The Graham number contains earnings and book value per share, so adding it
    to P/L and to ROE counts the same information three times, and it is
    meaningless for banks, for cyclicals at the top of their cycle and for
    asset-light companies. It belongs on a card as a badge, not in the weights.

Why inside the sector:
    A P/L of 12 is cheap for a utility and expensive for a software company.
    Ranking across the whole market produces a list of utilities and banks and
    calls it a discovery.

Why guard rails run before the score, not inside it:
    A company can be excellent on four pillars and still be untradeable, or be
    losing money three years running. Those are disqualifications, not
    penalties, and mixing them into a weighted average lets a high dividend
    yield buy its way past a broken balance sheet.
"""

import json
import logging
from datetime import datetime

from sqlalchemy import extract
from sqlalchemy.exc import SQLAlchemyError

from config import db
from models.cvm_fundamentals_ltm import CvmFinancials, TickerCvmMap
from models.stock import Stock
from models.stock_score import StockScore
from services.cvm_fundamentals_service import SOURCE_CVM, ticker_root
from services.cycle_service import (
    DETERIORACAO,
    OPORTUNIDADE,
    TOPO,
    attach_cycle_signals,
)

# Each metric is (stock attribute, lower_is_better).
PILLAR_METRICS = {
    "valuation": [("p_l", True), ("p_vp", True), ("ev_ebit", True)],
    "qualidade": [("roic", False), ("margemliquida", False), ("margembruta", False)],
    "saude": [("dividaliquidaebit", True), ("liquidezcorrente", False)],
    "crescimento": [("receitas_cagr5", False), ("lucros_cagr5", False)],
    "dividendos": [("dy", False)],
    # Onde o papel está no próprio ciclo. `queda_pontuavel` é a queda do topo
    # de 12 meses — e só chega aqui preenchida quando o fundamento resistiu à
    # queda; sem esse filtro, o pilar premiaria exatamente quem está
    # afundando. `valuation_vs_historico` é o múltiplo de hoje contra a
    # mediana da própria empresa.
    "ciclo": [("preco_sobre_topo", True), ("valuation_vs_historico", True)],
}

# Profiles are weight sets, not different formulas. The investor picks a
# profile; nobody should be asked to pick weights.
PROFILES = {
    "EQUILIBRADO": {
        "valuation": 0.25,
        "qualidade": 0.20,
        "saude": 0.15,
        "crescimento": 0.10,
        "dividendos": 0.10,
        "ciclo": 0.20,
    },
    "VALOR": {
        "valuation": 0.35,
        "qualidade": 0.15,
        "saude": 0.15,
        "crescimento": 0.05,
        "dividendos": 0.05,
        "ciclo": 0.25,
    },
    "DIVIDENDOS": {
        "valuation": 0.15,
        "qualidade": 0.15,
        "saude": 0.20,
        "crescimento": 0.05,
        "dividendos": 0.30,
        "ciclo": 0.15,
    },
    "QUALIDADE": {
        "valuation": 0.15,
        "qualidade": 0.35,
        "saude": 0.20,
        "crescimento": 0.10,
        "dividendos": 0.05,
        "ciclo": 0.15,
    },
    "CRESCIMENTO": {
        "valuation": 0.15,
        "qualidade": 0.20,
        "saude": 0.10,
        "crescimento": 0.30,
        "dividendos": 0.05,
        "ciclo": 0.20,
    },
}

DEFAULT_PROFILE = "EQUILIBRADO"

# Below this many peers the sector median is noise, so the company is ranked
# against the whole market instead.
MIN_SECTOR_SIZE = 5

# Guard rails. Named because they are judgement calls, not universal truths.
MIN_DAILY_LIQUIDITY = 1_000_000.0
MAX_NET_DEBT_TO_EBIT = 3.5
MIN_PROFITABLE_YEARS = 3
PROFIT_HISTORY_YEARS = 5

# Red flag thresholds.
LOW_CURRENT_RATIO = 1.0
IMPLAUSIBLE_DIVIDEND_YIELD = 15.0
HEALTHY_DIVIDEND_YIELD = 6.0
STRONG_ROIC = 15.0
WEAK_NET_MARGIN = 0.0
# Below the guard rail, but high enough that the investor should see it.
NOTABLE_LEVERAGE = 2.0
# A pillar only earns a spot among the reasons when it is genuinely ahead
# of the sector, not merely average.
STRONG_PILLAR = 60.0

MAX_REASONS = 3
MAX_RED_FLAGS = 3


def _entry(code, message):
    """
    Every reason and every flag carries a stable code beside its wording.

    The message embeds the company's own numbers, which is what makes it worth
    reading — and also what makes it unique per company. Without a code, the
    same rule fires under seventy different strings and nothing downstream can
    count, filter or translate it.
    """
    return {"code": code, "message": message}


# Múltiplo de preço: preço sobre alguma medida de resultado ou patrimônio.
# Quando a medida é negativa, o múltiplo não fica "barato" — ele deixa de
# significar o que o nome diz.
PRICE_MULTIPLES = {
    "p_l",
    "p_vp",
    "ev_ebit",
    "p_ebit",
    "p_ativo",
    "p_sr",
    "p_capitalgiro",
    "p_ativocirculante",
    "peg_ratio",
}


def scoring_value(stock, attribute):
    """
    O valor que a métrica leva para o pilar, que nem sempre é o publicado.

    Um DY de 34% é sinalizado como não recorrente três linhas abaixo e mesmo
    assim era premiado como se fosse quatro vezes melhor que um sólido 8%.
    Acima do limiar de plausibilidade o yield é aparado.

    **Múltiplo negativo não é múltiplo barato.** P/L de −4,50 quer dizer
    prejuízo; EV/EBIT negativo quer dizer resultado operacional negativo; P/VP
    negativo quer dizer patrimônio líquido negativo. O percentil ordena do
    menor para o maior, então o negativo era classificado como o mais barato
    do setor — a AZTE3 chegou a **segundo lugar geral** com P/L −4,50 e
    EV/EBIT −6,97, tirando 86 no pilar de valuation.

    Fora do ranking daquela métrica, a empresa é ranqueada pelo que de fato se
    aplica a ela, e o alerta de prejuízo continua no card contando o resto.
    """
    value = getattr(stock, attribute, None)
    if attribute == "dy" and _is_usable(value):
        return min(value, IMPLAUSIBLE_DIVIDEND_YIELD)
    if attribute in PRICE_MULTIPLES and value is not None and value <= 0:
        return None
    if attribute == "dividaliquidaebit":
        return _leverage_value(stock, value)
    return value


def _leverage_value(stock, value):
    """
    Dívida líquida sobre EBIT, quando o número quer dizer alguma coisa.

    Negativo tem duas leituras opostas: caixa líquido com EBIT positivo (ótimo)
    ou EBIT negativo com dívida (péssimo). A razão não distingue as duas, e
    como menor é melhor, as duas eram premiadas igualmente — 25 das 126 ações
    elegíveis caem nesse caso.

    A margem EBIT dá o sinal do denominador. Com EBIT não positivo, a razão
    sai do ranking e a empresa é avaliada pelo resto.
    """
    if value is None or value >= 0:
        return value
    margem_ebit = getattr(stock, "margemebit", None)
    return value if (margem_ebit or 0) > 0 else None


def _is_usable(value):
    """
    StatusInvest reports a missing indicator as 0.0, so a bare `is not None`
    check would rank a company with no data as the worst in its sector rather
    than as unknown.
    """
    return value is not None and value != 0


# ── Guard rails ──────────────────────────────────────────────────────────────


def get_profitable_years(tickers):
    """
    Returns {ticker root: count of profitable fiscal years} from CVM filings.

    Consistency, not magnitude: one spectacular year does not make a company
    that lost money in three of the last five a safe holding.
    """
    roots = {root for root in map(ticker_root, tickers) if root}
    if not roots:
        return {}

    first_year = datetime.utcnow().year - PROFIT_HISTORY_YEARS
    try:
        rows = _profit_rows(roots, first_year)
    except SQLAlchemyError as error:
        # As tabelas da CVM pertencem ao pipeline de dados e o `flask db
        # upgrade` do backend não as cria. Num servidor onde a migração do
        # pipeline ainda não rodou, deixar o erro subir zerava o score de
        # TODAS as ações por causa de um guard rail entre cinco. Sem
        # histórico, nenhuma empresa é excluída — que é a regra que já valia
        # para quem simplesmente não tem histórico.
        db.session.rollback()
        logging.error(
            f"Histórico de lucro indisponível; a consistência de lucro não "
            f"será verificada nesta execução: {error}"
        )
        return {}

    profitable = {}
    seen = set()
    for root, year, profit in rows:
        if (root, year) in seen:
            continue
        seen.add((root, year))
        if profit is not None and profit > 0:
            profitable[root] = profitable.get(root, 0) + 1
    return profitable


def _profit_rows(roots, first_year):
    return (
        db.session.query(
            TickerCvmMap.ticker_root,
            extract("year", CvmFinancials.period_end).label("year"),
            CvmFinancials.lucro_liquido,
        )
        .join(CvmFinancials, CvmFinancials.cd_cvm == TickerCvmMap.cd_cvm)
        .filter(
            TickerCvmMap.ticker_root.in_(roots),
            CvmFinancials.period_months == 12,
            extract("year", CvmFinancials.period_end) >= first_year,
        )
        .all()
    )


def check_eligibility(stock, profitable_years):
    """
    Returns the list of reasons this company should not be ranked at all.

    An empty list means it passes.
    """
    reasons = []

    if stock.active is False:
        reasons.append(
            _entry(
                "DESLISTADA",
                "Deixou de ser negociada — o ativo saiu da fonte de dados",
            )
        )

    liquidity = stock.liquidezmediadiaria
    if liquidity is None or liquidity < MIN_DAILY_LIQUIDITY:
        reasons.append(
            _entry(
                "LIQUIDEZ_BAIXA",
                "Liquidez diária abaixo de R$ 1 milhão — difícil entrar e sair "
                "da posição",
            )
        )

    if stock.vpa is not None and stock.vpa < 0:
        reasons.append(_entry("PATRIMONIO_NEGATIVO", "Patrimônio líquido negativo"))

    years = profitable_years.get(ticker_root(stock.ticker))
    if years is not None and years < MIN_PROFITABLE_YEARS:
        reasons.append(
            _entry(
                "LUCRO_INCONSISTENTE",
                f"Lucro positivo em apenas {years} dos últimos "
                f"{PROFIT_HISTORY_YEARS} exercícios",
            )
        )

    # Dívida com resultado operacional negativo produz razão negativa, que o
    # limite de alavancagem lia como caixa líquido e deixava passar livre.
    margem_ebit = getattr(stock, "margemebit", None)
    if (
        _is_usable(getattr(stock, "dividaliquidaebit", None))
        and stock.dividaliquidaebit < 0
        and _is_usable(margem_ebit)
        and margem_ebit < 0
    ):
        reasons.append(
            _entry(
                "ALAVANCAGEM_SEM_EBIT",
                "Dívida líquida com resultado operacional negativo — a relação "
                "com o EBIT não mede endividamento aqui",
            )
        )

    leverage = _leverage_value(stock, stock.dividaliquidaebit)
    if _is_usable(leverage) and leverage > MAX_NET_DEBT_TO_EBIT:
        reasons.append(
            _entry(
                "ALAVANCAGEM_ALTA",
                f"Dívida líquida em {leverage:.1f}× o EBIT, acima do limite de "
                f"{MAX_NET_DEBT_TO_EBIT}×",
            )
        )

    return reasons


# ── Percentis ────────────────────────────────────────────────────────────────


def percentile_ranks(values_by_ticker, lower_is_better):
    """
    Maps {ticker: value} to {ticker: percentile 0-100}, best = 100.

    Ties share the same percentile; a single-company group scores 50 rather
    than 100, because being alone is not the same as being the best.
    """
    if not values_by_ticker:
        return {}
    if len(values_by_ticker) == 1:
        return {ticker: 50.0 for ticker in values_by_ticker}

    ordered = sorted(values_by_ticker.items(), key=lambda item: item[1])
    total = len(ordered)
    ranks = {}
    for index, (ticker, value) in enumerate(ordered):
        share = index / (total - 1)
        ranks[ticker] = round((1 - share if lower_is_better else share) * 100, 1)
    return ranks


def _group_by_sector(stocks):
    """Sector buckets, with the small ones folded into a single market bucket."""
    by_sector = {}
    for stock in stocks:
        by_sector.setdefault(stock.sectorname or "SEM SETOR", []).append(stock)

    groups = []
    market = []
    for sector, members in by_sector.items():
        if len(members) >= MIN_SECTOR_SIZE:
            groups.append((sector, members))
        else:
            market.extend(members)
    if market:
        groups.append(("MERCADO", market))
    return groups


def compute_metric_percentiles(stocks):
    """
    Returns {ticker: {metric: percentile}} ranked inside each sector.

    Companies missing a metric are left out of that metric's ranking entirely,
    so a blank never competes as if it were a value.
    """
    percentiles = {stock.ticker: {} for stock in stocks}

    for _, members in _group_by_sector(stocks):
        for metrics in PILLAR_METRICS.values():
            for attribute, lower_is_better in metrics:
                # Filtra pelo valor de pontuação, não pelo bruto: múltiplo
                # negativo e alavancagem sem EBIT viram None, e comparar None
                # com float na ordenação derruba o refresh inteiro. É o mesmo
                # acerto que o score de FII já tinha recebido.
                values = {}
                for stock in members:
                    value = scoring_value(stock, attribute)
                    if _is_usable(value):
                        values[stock.ticker] = value
                for ticker, rank in percentile_ranks(values, lower_is_better).items():
                    percentiles[ticker][attribute] = rank
    return percentiles


def compute_pillars(metric_percentiles, pillar_metrics=None):
    """
    Averages each pillar's available metrics. A pillar with nothing to average
    is None, not zero — unknown must not read as bad.

    `pillar_metrics` is overridable because the backtest scores past years from
    a narrower set of columns — the yearly history has no growth figure — and
    duplicating this loop to say so would be worse than parameterising it.
    """
    pillars = {}
    for pillar, metrics in (pillar_metrics or PILLAR_METRICS).items():
        available = [
            metric_percentiles[attribute]
            for attribute, _ in metrics
            if attribute in metric_percentiles
        ]
        pillars[pillar] = (
            round(sum(available) / len(available), 1) if available else None
        )
    return pillars


def weighted_score(pillars, profile, profiles=None, default_profile=None):
    """
    Weighted average over the pillars that exist.

    The weights are renormalized rather than counting a missing pillar as
    zero: a bank has no EBIT-based leverage, and scoring it zero on financial
    health would push every bank off the list for a fact about accounting.

    `profiles` is overridable so the FII score can reuse this renormalization
    with its own pillars and weights — the rule about missing pillars is the
    same for both assets, and a second copy of it would drift.
    """
    profiles = profiles or PROFILES
    weights = profiles.get(profile) or profiles[default_profile or DEFAULT_PROFILE]
    usable = {
        pillar: weight
        for pillar, weight in weights.items()
        if pillars.get(pillar) is not None
    }
    if not usable:
        return None

    total_weight = sum(usable.values())
    total = sum(pillars[pillar] * weight for pillar, weight in usable.items())
    return round(total / total_weight, 1)


# ── Motivos e alertas ────────────────────────────────────────────────────────


def build_reasons(stock, pillars):
    """Why this company earns its place, strongest pillar first."""
    labels = {
        "valuation": "Múltiplos baratos frente ao próprio setor",
        "qualidade": "Rentabilidade acima da média do setor",
        "saude": "Balanço mais sólido que o do setor",
        "crescimento": "Crescimento acima da média do setor",
        "dividendos": "Dividendos acima da média do setor",
        "ciclo": "Momento de entrada melhor que o do setor",
    }
    ranked = sorted(
        ((pillar, value) for pillar, value in pillars.items() if value is not None),
        key=lambda item: item[1],
        reverse=True,
    )

    reasons = []
    if getattr(stock, "cycle_state", None) == OPORTUNIDADE and stock.cycle_message:
        reasons.append(_entry("CICLO_OPORTUNIDADE", stock.cycle_message))

    reasons += [
        _entry(f"PILAR_{pillar.upper()}", f"{labels[pillar]} ({value:.0f}/100)")
        for pillar, value in ranked
        if value >= STRONG_PILLAR
    ]

    if _is_usable(stock.roic) and stock.roic >= STRONG_ROIC:
        reasons.append(
            _entry(
                "ROIC_ALTO",
                f"ROIC de {stock.roic:.1f}% — o capital investido rende bem",
            )
        )
    if (
        _is_usable(stock.dy)
        and HEALTHY_DIVIDEND_YIELD <= stock.dy < IMPLAUSIBLE_DIVIDEND_YIELD
    ):
        reasons.append(_entry("DY_SAUDAVEL", f"Dividend Yield de {stock.dy:.1f}%"))

    return reasons[:MAX_REASONS]


def build_red_flags(stock):
    """
    What could go wrong. Shown beside the reasons on purpose: a screener that
    only argues for the asset is an advertisement, not an analysis.
    """
    flags = []

    # Comprar no topo do próprio ciclo e cair junto com o lucro são os dois
    # jeitos de errar que nenhum múltiplo isolado denuncia.
    estado = getattr(stock, "cycle_state", None)
    if estado in (TOPO, DETERIORACAO) and stock.cycle_message:
        codigo = "CICLO_TOPO" if estado == TOPO else "CICLO_DETERIORACAO"
        flags.append(_entry(codigo, stock.cycle_message))

    if stock.lpa is not None and stock.lpa < 0:
        flags.append(
            _entry("PREJUIZO", "Empresa com prejuízo — lucro por ação negativo")
        )
    if _is_usable(stock.margemliquida) and stock.margemliquida < WEAK_NET_MARGIN:
        flags.append(_entry("MARGEM_NEGATIVA", "Margem líquida negativa"))
    margem_ebit = getattr(stock, "margemebit", None)
    if _is_usable(margem_ebit) and margem_ebit < 0:
        # Mostrado, não escondido: pode ser um ciclo ruim de uma boa empresa,
        # e é o investidor que decide. O que não pode é o múltiplo negativo
        # entrar no ranking como se fosse desconto.
        flags.append(
            _entry(
                "EBIT_NEGATIVO",
                f"Resultado operacional negativo (margem EBIT de "
                f"{margem_ebit:.1f}%)",
            )
        )
    if (
        _is_usable(stock.dividaliquidaebit)
        and stock.dividaliquidaebit > NOTABLE_LEVERAGE
    ):
        flags.append(
            _entry(
                "ALAVANCAGEM",
                f"Dívida líquida em {stock.dividaliquidaebit:.1f}× o EBIT",
            )
        )
    if (
        _is_usable(stock.liquidezcorrente)
        and stock.liquidezcorrente < LOW_CURRENT_RATIO
    ):
        flags.append(
            _entry(
                "CAIXA_CURTO",
                f"Liquidez corrente de {stock.liquidezcorrente:.2f} — "
                "caixa de curto prazo apertado",
            )
        )
    if _is_usable(stock.dy) and stock.dy >= IMPLAUSIBLE_DIVIDEND_YIELD:
        flags.append(
            _entry(
                "DY_IMPLAUSIVEL",
                f"DY de {stock.dy:.1f}% dificilmente se repete — "
                "confira se veio de provento extraordinário",
            )
        )
    if stock.fundamentals_source != SOURCE_CVM:
        flags.append(
            _entry(
                "FUNDAMENTO_DEFASADO",
                "Fundamento de fonte pública, do último exercício fechado — "
                "não auditado nem dos últimos 12 meses",
            )
        )

    return flags[:MAX_RED_FLAGS]


# ── Orquestração ─────────────────────────────────────────────────────────────


def leading_pillars(profile):
    """Os pilares que mais pesam no perfil — o que o perfil quer dizer."""
    weights = PROFILES.get(profile) or PROFILES[DEFAULT_PROFILE]
    maior = max(weights.values())
    return {pillar for pillar, peso in weights.items() if peso == maior}


def _ranks_in_profile(pillars, profile):
    """
    Sem o pilar que define o perfil, a ação não entra naquela vitrine.

    `weighted_score` renormaliza os pesos quando um pilar falta — regra que
    nasceu para o banco que não tem EBIT, onde o pilar ausente é fato
    contábil. Aqui ela se volta contra o usuário: uma empresa sem dividendo
    declarado teria os 30% do pilar de dividendos redistribuídos para os
    outros e poderia liderar justamente o perfil DIVIDENDOS, ranqueada por
    aquilo que o perfil não pediu.

    É a mesma regra que o score de FII já aplicava; faltava valer para ação.
    """
    return all(pillars.get(pillar) is not None for pillar in leading_pillars(profile))


def _score_row(stock, pillars, profile, exclusion_reasons, run_date):
    """Builds the persisted row for one ticker under one profile."""
    eligible = not exclusion_reasons
    ranked = eligible and _ranks_in_profile(pillars, profile)
    return {
        "ticker": stock.ticker,
        "profile": profile,
        "run_date": run_date,
        "score_total": weighted_score(pillars, profile) if ranked else None,
        "score_valuation": pillars.get("valuation"),
        "score_qualidade": pillars.get("qualidade"),
        "score_saude": pillars.get("saude"),
        "score_crescimento": pillars.get("crescimento"),
        "score_dividendos": pillars.get("dividendos"),
        "score_ciclo": pillars.get("ciclo"),
        "eligible": eligible,
        "exclusion_reasons": json.dumps(exclusion_reasons, ensure_ascii=False),
        "reasons": json.dumps(build_reasons(stock, pillars), ensure_ascii=False),
        "red_flags": json.dumps(build_red_flags(stock), ensure_ascii=False),
    }


def build_scores(stocks, profiles=None):
    """
    Scores the whole universe for each profile.

    The percentiles are computed once and reused: a profile changes the weights,
    never the ranking of a company against its peers.
    """
    profiles = profiles or list(PROFILES)
    attach_cycle_signals(stocks)
    percentiles = compute_metric_percentiles(stocks)
    profitable_years = get_profitable_years([stock.ticker for stock in stocks])
    run_date = datetime.utcnow()

    rows = []
    for stock in stocks:
        pillars = compute_pillars(percentiles.get(stock.ticker, {}))
        exclusion_reasons = check_eligibility(stock, profitable_years)
        for profile in profiles:
            rows.append(
                _score_row(stock, pillars, profile, exclusion_reasons, run_date)
            )
    return rows


def refresh_scores():
    """
    Recomputes and stores the score for every ticker and profile.

    Called at the end of the stock refresh so the score can never describe a
    snapshot that no longer exists. Deliberately not a separate pipeline: the
    opportunities page is empty today precisely because it depends on one that
    never runs.
    """
    try:
        stocks = Stock.query.all()
        if not stocks:
            return 0

        rows = build_scores(stocks)
        StockScore.query.delete()
        db.session.bulk_insert_mappings(StockScore, rows)
        db.session.commit()

        eligible = sum(1 for row in rows if row["eligible"]) // len(PROFILES)
        logging.info(
            f"Scores refreshed: {len(stocks)} tickers, {eligible} eligible, "
            f"{len(PROFILES)} profiles"
        )
        return len(rows)
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return 0


# ── Leitura para a tabela ────────────────────────────────────────────────────


def get_score_map(tickers, profile):
    """{ticker: StockScore} for one profile, for the rows on screen."""
    if not tickers:
        return {}

    scores = StockScore.query.filter(
        StockScore.ticker.in_(tickers),
        StockScore.profile == profile,
    ).all()
    return {score.ticker: score for score in scores}


def attach_score_fields(stock_json, score):
    """
    Adds the fundamental score to a stock row, mirroring attach_ml_fields.

    Flat keys rather than a nested object: the table sorts and renders on
    column accessors, and a nested score would need every consumer to know its
    shape. The pillars stay nested because they are only read by the popover.
    """
    if score is None:
        stock_json["score_total"] = None
        stock_json["score_profile"] = None
        stock_json["score_eligible"] = None
        stock_json["score_pillars"] = []
        return stock_json

    payload = score.to_json()
    stock_json["score_total"] = payload["score_total"]
    stock_json["score_profile"] = payload["profile"]
    stock_json["score_eligible"] = payload["eligible"]
    stock_json["score_pillars"] = payload["pillars"]
    return stock_json
