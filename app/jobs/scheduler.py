"""
O processo que dispara a rotina todo dia.

Uso:
    python app/jobs/scheduler.py          # fica rodando e dispara no horário
    python app/jobs/scheduler.py --now    # roda uma vez agora e sai

O horário é 21h de Brasília, de segunda a sexta. A B3 fecha às 18h e o
after-market às 18h30; as fontes de fundamento publicam o fechamento ao longo
da noite. Rodar antes disso traz o preço do meio do pregão com cara de preço
de fechamento.

Fim de semana fica de fora porque não há pregão: a rotina só gastaria
requisição na fonte para reescrever os mesmos números — e ainda gravaria dois
retratos idênticos no histórico, inventando "nenhuma mudança" onde na verdade
não houve dia útil.
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.blocking import BlockingScheduler  # noqa: E402
from apscheduler.triggers.cron import CronTrigger  # noqa: E402

from jobs.daily_refresh import run_daily_refresh  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

TIMEZONE = os.environ.get("SCHEDULER_TIMEZONE", "America/Sao_Paulo")
HOUR = int(os.environ.get("DAILY_REFRESH_HOUR", "21"))
MINUTE = int(os.environ.get("DAILY_REFRESH_MINUTE", "0"))


def _build_app():
    """
    A aplicação Flask, só pelo contexto.

    O agendador não serve HTTP; ele precisa do contexto porque os serviços
    falam com o banco pela sessão do Flask-SQLAlchemy.
    """
    from config import create_app
    from utils import setup_routes

    app = create_app()
    # As rotas trazem os imports que registram os mappers do SQLAlchemy; sem
    # elas, o relacionamento `Favorite -> User` falha ao resolver.
    setup_routes(app)
    return app


def executar_uma_vez(app):
    with app.app_context():
        execucao = run_daily_refresh()
        return execucao.status


def main():
    parser = argparse.ArgumentParser(description="Rotinas automáticas do InvestLink")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Executa a atualização imediatamente e encerra",
    )
    args = parser.parse_args()

    app = _build_app()

    if args.now:
        status = executar_uma_vez(app)
        logger.info(f"Execução avulsa concluída: {status}")
        return

    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        lambda: executar_uma_vez(app),
        trigger=CronTrigger(day_of_week="mon-fri", hour=HOUR, minute=MINUTE),
        id="atualizacao_diaria",
        # Se o contêiner ficou fora do ar na hora marcada, roda ao voltar em
        # vez de pular o dia — mas uma vez só, não uma por disparo perdido.
        misfire_grace_time=6 * 60 * 60,
        coalesce=True,
        max_instances=1,
    )
    logger.info(
        f"Agendador no ar: seg-sex às {HOUR:02d}:{MINUTE:02d} ({TIMEZONE}). "
        "Ctrl+C para sair."
    )
    scheduler.start()


if __name__ == "__main__":
    main()
