from flask import jsonify

from jobs.daily_refresh import last_run


def last_refresh_json():
    """
    Quando o dado foi atualizado pela última vez.

    A vitrine precisa dizer de quando é o preço que está mostrando. Lista de
    oportunidade sem data é lista em que não dá para confiar: ninguém sabe se
    é o fechamento de ontem ou o de três semanas atrás.
    """
    execucao = last_run()
    if execucao is None:
        return jsonify({"status": "NUNCA", "started_at": None}), 200
    return jsonify(execucao.to_json()), 200
