"""
Ponto de entrada WSGI do contêiner.

O código vive em `app/` com imports planos (`from config import db`), então o
diretório precisa entrar no sys.path.

O módulo é carregado por caminho, e não com `import app`, porque existe um
`app/__init__.py` vazio: dependendo de qual entrada do sys.path vem primeiro —
e `PYTHONPATH=app`, que é como os testes rodam, muda isso —, o nome `app`
resolve ora para o pacote vazio, ora para o `app/app.py`. Carregar pelo arquivo
tira a ambiguidade: o gunicorn e a linha de comando passam a ver sempre o mesmo
módulo.
"""

import importlib.util
import os
import sys

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

_spec = importlib.util.spec_from_file_location(
    "investlink_app", os.path.join(APP_DIR, "app.py")
)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

application = _module.app
prepare_database = _module.prepare_database

__all__ = ["application", "prepare_database"]
