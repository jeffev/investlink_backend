"""
Sonda de disponibilidade usada pelo orquestrador e pelo deploy.

Um contêiner que subiu não é uma aplicação que responde: o caso comum de deploy
quebrado é o processo de pé com o banco fora de alcance. A sonda consulta o
banco para que essa diferença apareça antes de o primeiro usuário abrir a tela.
"""

import logging

from flask import jsonify
from sqlalchemy import text

from config import db

logger = logging.getLogger(__name__)


def health_json():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as error:
        logger.error("Health check falhou ao consultar o banco: %s", error)
        return jsonify({"status": "degraded", "database": "unreachable"}), 503

    return jsonify({"status": "ok", "database": "ok"}), 200
