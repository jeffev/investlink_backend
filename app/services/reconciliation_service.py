"""
Compara o fundamento vindo da CVM com o que o StatusInvest publica.

Por que isto existe:
    O `update_all_stocks` passou a preferir o número auditado da CVM, e o
    scraper de indicadores foi aposentado por causa disso. Aposentar uma fonte
    sem nada olhando a substituta é trocar um risco conhecido por um silencioso:
    se a ingestão da CVM quebrar num setor, o screener continua entregando
    número — só que errado.

Sobre que base a comparação é feita:
    Contra o **exercício fechado**, não contra os últimos doze meses. O
    StatusInvest reporta o último exercício encerrado; comparar isso com o LTM
    acusaria divergência em toda empresa que simplesmente teve um trimestre
    diferente do ano passado — ruído, não erro.

O que uma divergência significa:
    Não que a CVM esteja errada. As duas fontes discordam legitimamente quando
    a empresa refez a demonstração, quando o StatusInvest usa o individual e a
    CVM o consolidado, ou quando há participação de minoritários. O relatório
    serve para alguém olhar, não para decidir sozinho.
"""

import logging
from datetime import date

from flask import jsonify
from sqlalchemy import extract

from config import db
from models.cvm_fundamentals_ltm import CvmFinancials, TickerCvmMap
from services.cvm_fundamentals_service import ticker_root
from services.stock_services import get_all_stocks_from_statusinvest

# Acima disso a divergência deixa de ser diferença de critério e vira suspeita.
DIVERGENCE_THRESHOLD_PERCENT = 10.0

# Abaixo disso o percentual explode por divisão: uma empresa com LPA de R$0,01
# acusaria 200% de divergência por um centavo de diferença de arredondamento.
MIN_COMPARABLE_VALUE = 0.10

COMPARED_FIELDS = ("lpa", "vpa", "roe")


def _divergence_percent(cvm_value, source_value):
    """
    Diferença relativa entre as duas fontes, ou None quando não dá para comparar.

    A base é o valor da CVM por ser o auditado — a pergunta é "quanto o
    StatusInvest se afasta do que foi entregue à reguladora".
    """
    if cvm_value is None or source_value is None:
        return None
    if abs(cvm_value) < MIN_COMPARABLE_VALUE:
        return None
    return round(((source_value - cvm_value) / abs(cvm_value)) * 100, 2)


def _annual_fundamentals(year):
    """
    {ticker_root: {lpa, vpa, roe}} do exercício fechado, a partir da CVM.

    Derivado aqui em vez de lido pronto porque `cvm_financials` guarda os
    valores absolutos do balanço; por ação é uma conta, não um campo.
    """
    rows = (
        db.session.query(TickerCvmMap.ticker_root, CvmFinancials)
        .join(CvmFinancials, CvmFinancials.cd_cvm == TickerCvmMap.cd_cvm)
        .filter(
            CvmFinancials.period_months == 12,
            extract("year", CvmFinancials.period_end) == year,
        )
        .all()
    )

    fundamentals = {}
    for root, row in rows:
        shares = row.acoes_circulacao
        equity = row.patrimonio_liquido
        profit = row.lucro_controladores or row.lucro_liquido
        if not shares or shares <= 0:
            continue
        fundamentals[root] = {
            "lpa": profit / shares if profit is not None else None,
            "vpa": equity / shares if equity is not None else None,
            "roe": (
                (profit / equity) * 100
                if profit is not None and equity and equity > 0
                else None
            ),
        }
    return fundamentals


def _compare_ticker(ticker, source_row, cvm_row):
    """Divergências de um ticker, ou None quando nenhuma passa do limite."""
    divergences = {}
    for field in COMPARED_FIELDS:
        percent = _divergence_percent(cvm_row.get(field), source_row.get(field))
        if percent is not None and abs(percent) > DIVERGENCE_THRESHOLD_PERCENT:
            divergences[field] = {
                "cvm": round(cvm_row[field], 4),
                "statusinvest": round(source_row[field], 4),
                "divergence_percent": percent,
            }

    if not divergences:
        return None
    return {"ticker": ticker, "fields": divergences}


def reconcile_fundamentals(year=None):
    """
    Confronta as duas fontes e devolve o relatório das divergências.

    Busca o StatusInvest na hora de propósito: a tabela `stocks` já foi
    sobrescrita pelo valor da CVM, então ela não serve mais de testemunha.
    """
    try:
        reference_year = year or (date.today().year - 1)
        payload = get_all_stocks_from_statusinvest()
        if not payload or "list" not in payload:
            return (
                jsonify({"message": "Não foi possível consultar o StatusInvest"}),
                502,
            )

        cvm_by_root = _annual_fundamentals(reference_year)
        if not cvm_by_root:
            return (
                jsonify(
                    {
                        "message": (
                            f"Sem demonstrações da CVM para {reference_year} — "
                            "rode a ingestão antes de reconciliar"
                        )
                    }
                ),
                409,
            )

        report = _build_report(payload["list"], cvm_by_root, reference_year)
        logging.info(
            f"Reconciliação {reference_year}: {report['diverging']} divergências "
            f"em {report['compared']} tickers comparados"
        )
        return jsonify(report), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def _build_report(source_rows, cvm_by_root, reference_year):
    """Monta o relatório a partir das duas fontes já carregadas."""
    divergences = []
    compared = 0
    without_cvm = []

    for row in source_rows:
        ticker = row.get("ticker")
        root = ticker_root(ticker) if ticker else None
        cvm_row = cvm_by_root.get(root) if root else None
        if cvm_row is None:
            if ticker:
                without_cvm.append(ticker)
            continue

        compared += 1
        divergence = _compare_ticker(ticker, row, cvm_row)
        if divergence:
            divergences.append(divergence)

    divergences.sort(
        key=lambda item: max(
            abs(field["divergence_percent"]) for field in item["fields"].values()
        ),
        reverse=True,
    )
    return {
        "reference_year": reference_year,
        "threshold_percent": DIVERGENCE_THRESHOLD_PERCENT,
        "compared": compared,
        "diverging": len(divergences),
        "without_cvm_data": len(without_cvm),
        "divergences": divergences,
    }
