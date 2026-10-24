"""
A atualização diária.

Até aqui o dado só mudava quando um administrador abria a tela e clicava em
"Atualizar Ações". Uma vitrine de oportunidades que depende de alguém lembrar
de apertar um botão mostra o preço da semana passada sem avisar — e preço
velho não é informação incompleta, é informação errada.

A ordem importa: fundamento e cotação primeiro, score depois (ele sai de
dentro do próprio update), e o retrato do dia por último, quando a nota já é a
nova. Invertida, a memória guardaria a nota de ontem com a data de hoje.
"""

import logging
from datetime import datetime

from config import db
from models.job_run import JobRun
from services.fii_services import update_all_fiis
from services.price_snapshot_service import record_closing_prices
from services.snapshot_service import prune_snapshots, record_snapshots
from services.stock_services import update_all_stocks

DAILY_JOB_NAME = "atualizacao_diaria"

STATUS_OK = "OK"
STATUS_PARCIAL = "PARCIAL"
STATUS_ERRO = "ERRO"


def _executar_etapa(nome, funcao):
    """
    Roda uma etapa e devolve (ok, descrição), sem deixar exceção escapar.

    Uma etapa que falha não pode levar as outras junto: se o FII caiu e a ação
    passou, o usuário tem preço novo de ação — esconder isso por causa do FII
    seria trocar um dado velho por dois.
    """
    try:
        resposta = funcao()
        status = resposta[1] if isinstance(resposta, tuple) else 200
        ok = status < 400
        return ok, f"{nome}: HTTP {status}"
    except Exception as error:  # noqa: BLE001 - a rotina não pode morrer aqui
        db.session.rollback()
        logging.error(f"Etapa '{nome}' falhou: {error}")
        return False, f"{nome}: {type(error).__name__} {error}"


def run_daily_refresh():
    """
    Executa o ciclo e registra a execução. Devolve a linha de `job_runs`.

    O registro é gravado mesmo quando tudo falha — é justamente aí que ele
    serve, porque o sintoma visível de uma rotina parada é "os dados
    congelaram", sem nada a que recorrer.
    """
    inicio = datetime.utcnow()
    resultados = [
        _executar_etapa("acoes", update_all_stocks),
        _executar_etapa("fiis", update_all_fiis),
    ]

    sucessos = sum(1 for ok, _ in resultados if ok)
    if sucessos:
        # A cotação de hoje entra na série antes do retrato: é ela que mantém
        # viva a janela de 12 meses do sinal de ciclo.
        resultados.append(_executar_etapa("cotacao", record_closing_prices))
        # Só vale guardar o retrato se alguma nota foi recalculada.
        resultados.append(_executar_etapa("snapshot", record_snapshots))
        resultados.append(_executar_etapa("limpeza", prune_snapshots))

    if sucessos == 0:
        status = STATUS_ERRO
    elif all(ok for ok, _ in resultados):
        status = STATUS_OK
    else:
        status = STATUS_PARCIAL

    execucao = JobRun(
        job_name=DAILY_JOB_NAME,
        started_at=inicio,
        finished_at=datetime.utcnow(),
        status=status,
        detail=" | ".join(descricao for _, descricao in resultados),
    )
    db.session.add(execucao)
    db.session.commit()

    logging.info(f"Atualização diária: {status} — {execucao.detail}")
    return execucao


def last_run(job_name=DAILY_JOB_NAME):
    """A execução mais recente, para a tela dizer de quando é o dado."""
    return (
        JobRun.query.filter_by(job_name=job_name)
        .order_by(JobRun.started_at.desc())
        .first()
    )
