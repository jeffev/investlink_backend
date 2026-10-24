"""
A memória do score, dia a dia.

`refresh_scores` apaga e reescreve a tabela de nota a cada execução. Isso é
correto para o retrato atual e destrói o histórico — e sem histórico a vitrine
só sabe dizer "estes são os melhores agora", nunca "este entrou hoje" ou "este
subiu doze pontos na semana".

O retrato continua em `stock_scores`/`fii_scores`; aqui fica a lembrança: uma
linha por ativo, perfil e dia, com a nota e a elegibilidade. É o suficiente
para o delta e barato o bastante para guardar meses.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from config import db
from models.fii_score import FiiScore
from models.score_snapshot import ScoreSnapshot
from models.stock_score import StockScore

ACAO = "ACAO"
FII = "FII"

SOURCES = {ACAO: StockScore, FII: FiiScore}

# Três meses cobrem a janela que a tela usa (ontem, semana, mês) com folga
# para feriado e rotina que falhou.
RETENTION_DAYS = 120


def record_snapshots(reference=None):
    """
    Grava o retrato de hoje. Idempotente: rodar duas vezes no mesmo dia
    atualiza a linha em vez de duplicar.
    """
    reference = reference or date.today()
    total = 0

    for asset_type, model in SOURCES.items():
        rows = [
            {
                "asset_type": asset_type,
                "ticker": score.ticker,
                "profile": score.profile,
                "snapshot_date": reference,
                "score_total": score.score_total,
                "eligible": bool(score.eligible),
            }
            for score in model.query.all()
        ]
        if not rows:
            continue

        statement = insert(ScoreSnapshot).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=["asset_type", "ticker", "profile", "snapshot_date"],
            set_={
                "score_total": statement.excluded.score_total,
                "eligible": statement.excluded.eligible,
            },
        )
        db.session.execute(statement)
        total += len(rows)

    db.session.commit()
    logging.info(f"Snapshots do score gravados: {total} linhas em {reference}")
    return total


def prune_snapshots(keep_days=RETENTION_DAYS, reference=None):
    """Descarta o que é velho demais para qualquer comparação da tela."""
    limite = (reference or date.today()) - timedelta(days=keep_days)
    removidos = ScoreSnapshot.query.filter(ScoreSnapshot.snapshot_date < limite).delete(
        synchronize_session=False
    )
    db.session.commit()
    return removidos


def _previous_date(asset_type, profile, before):
    """A data gravada mais recente antes de `before`, se houver."""
    return (
        db.session.query(func.max(ScoreSnapshot.snapshot_date))
        .filter(
            ScoreSnapshot.asset_type == asset_type,
            ScoreSnapshot.profile == profile,
            ScoreSnapshot.snapshot_date < before,
        )
        .scalar()
    )


def get_score_deltas(asset_type, profile, tickers, reference=None):
    """
    {ticker: {"previous", "delta", "is_new", "since"}} comparando a nota de
    hoje com a do retrato anterior.

    `is_new` quer dizer "não estava elegível no retrato anterior" — que é o
    que o investidor lê como "entrou na lista". Ativo sem retrato anterior
    nenhum **não** é novo: é desconhecido, e anunciar estreia para a base
    inteira no primeiro dia de uso seria ruído.

    Falha de leitura devolve vazio em vez de derrubar a vitrine: o delta é um
    enfeite informativo, a lista é o produto.
    """
    if not tickers:
        return {}

    reference = reference or date.today()
    try:
        anterior = _previous_date(asset_type, profile, reference)
        if anterior is None:
            return {}

        linhas = ScoreSnapshot.query.filter(
            ScoreSnapshot.asset_type == asset_type,
            ScoreSnapshot.profile == profile,
            ScoreSnapshot.snapshot_date == anterior,
            ScoreSnapshot.ticker.in_(tickers),
        ).all()
    except SQLAlchemyError as error:
        db.session.rollback()
        logging.error(f"Histórico de score indisponível: {error}")
        return {}

    por_ticker = {linha.ticker: linha for linha in linhas}
    deltas = {}
    for ticker in tickers:
        linha = por_ticker.get(ticker)
        if linha is None:
            continue
        deltas[ticker] = {
            "previous": linha.score_total,
            "is_new": not linha.eligible,
            "since": anterior.isoformat(),
        }
    return deltas


def attach_delta(payload, delta, score_total):
    """Anexa o movimento da nota à linha que vai para a tela."""
    if not delta:
        payload["score_delta"] = None
        payload["score_is_new"] = False
        payload["score_delta_since"] = None
        return payload

    anterior = delta.get("previous")
    payload["score_delta"] = (
        round(score_total - anterior, 1)
        if score_total is not None and anterior is not None
        else None
    )
    payload["score_is_new"] = bool(delta.get("is_new"))
    payload["score_delta_since"] = delta.get("since")
    return payload
