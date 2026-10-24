"""
Reads the audited CVM fundamentals the data science pipeline writes and lets
the stock snapshot prefer them over the scraped ones.

Why prefer the CVM:
    StatusInvest reports the last closed fiscal year. In September that is nine
    months stale — it misses two quarterly results and any turnaround in
    between. The pipeline builds a trailing twelve month figure from the
    quarterly filings, so the screener stops pricing companies on last year.

What is NOT taken from the CVM:
    Price, market value, sector, dividend yield and traded liquidity. Those are
    market data, not accounting data, and StatusInvest remains the source.
"""

import logging
import re

from models.cvm_fundamentals_ltm import CvmFundamentalsLtm, TickerCvmMap

# stocks column -> CvmFundamentalsLtm attribute.
#
# Only accounting figures. A null on the CVM side means the indicator does not
# apply to that company — a bank has no EBIT-based leverage and no current
# ratio — and a null must never overwrite a value that is already there.
CVM_FIELD_MAP = {
    "lpa": "lpa_ltm",
    "vpa": "vpa",
    "roe": "roe_ltm",
    "roic": "roic_ltm",
    "margembruta": "m_bruta_ltm",
    "margemebit": "m_ebit_ltm",
    "margemliquida": "m_liquida_ltm",
    "dividaliquidaebit": "div_liq_ebit",
    "dividaliquidapatrimonioliquido": "div_liq_pl",
    "liquidezcorrente": "liq_corrente",
}

SOURCE_CVM = "CVM"
# O rótulo da fonte pública. Era "STATUSINVEST" e passou a mentir quando a
# coleta trocou para o Fundamentus: o card anunciava uma procedência que o
# dado não tinha. "PUBLICA" descreve o que importa — número de fonte aberta,
# do último exercício fechado, não auditado nesta base.
SOURCE_STATUSINVEST = "PUBLICA"

# The ticker root is four alphanumeric characters, not four letters: B3SA3 is
# the exchange itself. This mirrors data_sources/ticker_cvm_map.py in the
# pipeline repository — the two services cannot share code, so the rule is
# repeated rather than approximated.
_TICKER_ROOT = re.compile(r"^([A-Za-z0-9]{4})\d")


def ticker_root(ticker):
    """PETR4 -> PETR. None for anything that is not a B3 symbol."""
    if not ticker:
        return None
    match = _TICKER_ROOT.match(ticker.strip().upper())
    return match.group(1) if match else None


def get_fundamentals_by_ticker(tickers):
    """
    Returns {ticker: CvmFundamentalsLtm} for the tickers that resolve.

    Two hops: ticker root -> CD_CVM -> fundamentals. Both are loaded in a
    single query each; this runs over the whole universe on every refresh.
    """
    roots = {root for root in map(ticker_root, tickers) if root}
    if not roots:
        return {}

    bridge = TickerCvmMap.query.filter(TickerCvmMap.ticker_root.in_(roots)).all()
    cd_cvm_by_root = {row.ticker_root: row.cd_cvm for row in bridge}
    if not cd_cvm_by_root:
        return {}

    fundamentals = CvmFundamentalsLtm.query.filter(
        CvmFundamentalsLtm.cd_cvm.in_(set(cd_cvm_by_root.values()))
    ).all()
    by_cd_cvm = {row.cd_cvm: row for row in fundamentals}

    resolved = {}
    for ticker in tickers:
        cd_cvm = cd_cvm_by_root.get(ticker_root(ticker))
        if cd_cvm and cd_cvm in by_cd_cvm:
            resolved[ticker] = by_cd_cvm[cd_cvm]
    return resolved


def _recalculated_multiples(stock_data, fundamentals):
    """
    Price multiples implied by the CVM figures.

    They have to move together with the earnings they divide: leaving P/L from
    StatusInvest next to an LTM earnings per share would show a P/L of 4.9 for
    a company whose own price and LPA on the same row give 3.9.
    """
    price = stock_data.get("price")
    if not price or price <= 0:
        return {}

    multiples = {}
    if fundamentals.lpa_ltm and fundamentals.lpa_ltm > 0:
        multiples["p_l"] = round(price / fundamentals.lpa_ltm, 4)
    if fundamentals.vpa and fundamentals.vpa > 0:
        multiples["p_vp"] = round(price / fundamentals.vpa, 4)
    return multiples


# Divergência a partir da qual o número auditado deixa de ser "discordância"
# e passa a ser erro. A diferença legítima entre o LTM da CVM e o exercício
# fechado da fonte pública raramente passa do dobro; mil vezes é escala
# trocada.
MAX_MULTIPLE_DIVERGENCE = 5.0


def _implausible(recalculated, published):
    """
    O múltiplo recalculado é incompatível com o publicado?

    Existe porque a quantidade de ações em circulação vem errada da CVM para
    algumas empresas — o Santander aparece com 7,4 **milhões** de ações em vez
    de 7,4 bilhões. O LPA sai mil vezes maior, o P/L mil vezes menor, e a
    empresa vira "a mais barata do setor": SANB3, SANB4, SANB11, SYNE3 e POSI3
    estavam entre as ações com P/VP abaixo de 0,05, que é impossível para
    companhia listada.

    A verificação compara o número auditado com o que a fonte pública
    publicou. Não é desempate — é detector de ordem de grandeza. Discordar por
    30% é normal; discordar por mil vezes é defeito.
    """
    if not recalculated or not published or published <= 0:
        return False
    razao = recalculated / published
    return razao > MAX_MULTIPLE_DIVERGENCE or razao < 1 / MAX_MULTIPLE_DIVERGENCE


def _multiples_are_sane(stock_data, recalculated):
    """Todos os múltiplos recalculados batem com a ordem de grandeza publicada."""
    for column, value in recalculated.items():
        if _implausible(value, stock_data.get(column)):
            logging.warning(
                f"{stock_data.get('ticker')}: múltiplo {column} da CVM "
                f"({value}) incompatível com o publicado "
                f"({stock_data.get(column)}) — fundamento auditado descartado"
            )
            return False
    return True


def apply_cvm_fundamentals(stock_data, fundamentals):
    """
    Substitui o fundamento da fonte pública pelo auditado, no lugar.

    Devolve quantos campos foram trocados, para o chamador poder relatar que
    parte do universo roda de fato com dado da CVM.

    Quando o múltiplo recalculado é incompatível em ordem de grandeza com o
    publicado, **nada é trocado**: um dado auditado com escala errada é pior
    que um dado público correto, porque ele chega com o selo de auditado e vai
    para o topo da vitrine.
    """
    if fundamentals is None:
        stock_data["fundamentals_source"] = SOURCE_STATUSINVEST
        return 0

    recalculated = _recalculated_multiples(stock_data, fundamentals)
    if not _multiples_are_sane(stock_data, recalculated):
        stock_data["fundamentals_source"] = SOURCE_STATUSINVEST
        return 0

    replaced = 0
    for column, attribute in CVM_FIELD_MAP.items():
        value = getattr(fundamentals, attribute, None)
        # Zero não é valor, é componente que faltou no cálculo do LTM — a
        # convenção vale no projeto inteiro (`_is_usable` no score). Gravar o
        # zero por cima destruía dado bom: o ALLD3 tinha ROE de 23,06% na
        # fonte pública e ficou com 0, e 21 das ações elegíveis perderam pelo
        # menos um indicador assim.
        if value is None or value == 0:
            continue
        stock_data[column] = value
        replaced += 1

    for column, value in recalculated.items():
        stock_data[column] = value
        replaced += 1

    if replaced == 0:
        stock_data["fundamentals_source"] = SOURCE_STATUSINVEST
        return 0

    stock_data["fundamentals_source"] = SOURCE_CVM
    stock_data["fundamentals_date"] = fundamentals.ltm_end
    return replaced


def enrich_with_cvm(cached_stocks):
    """
    Applies the CVM figures to a whole StatusInvest payload.

    Logs the share of the universe that ended up on audited data — a silent
    drop in that number is the first sign the pipeline stopped running.
    """
    try:
        tickers = [stock["ticker"] for stock in cached_stocks if stock.get("ticker")]
        fundamentals_by_ticker = get_fundamentals_by_ticker(tickers)
        if not fundamentals_by_ticker:
            logging.warning(
                "CVM fundamentals unavailable — keeping StatusInvest figures"
            )
            for stock_data in cached_stocks:
                stock_data["fundamentals_source"] = SOURCE_STATUSINVEST
            return 0

        enriched = 0
        for stock_data in cached_stocks:
            fundamentals = fundamentals_by_ticker.get(stock_data.get("ticker"))
            if apply_cvm_fundamentals(stock_data, fundamentals) > 0:
                enriched += 1

        logging.info(
            f"CVM fundamentals applied to {enriched}/{len(cached_stocks)} tickers"
        )
        return enriched
    except Exception as e:
        # The refresh must still deliver the StatusInvest snapshot; audited
        # figures are an improvement on it, not a precondition for it.
        logging.error(f"An error occurred while applying CVM fundamentals: {e}")
        return 0
