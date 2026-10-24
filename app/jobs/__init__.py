"""
Rotinas que rodam sozinhas.

Vivem fora do processo web de propósito. O gunicorn sobe três workers; um
agendador dentro deles dispararia a mesma atualização três vezes, concorrendo
pela mesma tabela. O contêiner `scheduler` roda este módulo sozinho, com um
processo só.
"""

from jobs.daily_refresh import DAILY_JOB_NAME, run_daily_refresh

__all__ = ["DAILY_JOB_NAME", "run_daily_refresh"]
