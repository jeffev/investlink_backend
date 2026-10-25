"""
Configuração que não pode cair em default público em produção.
"""

import pytest

from config import resolve_jwt_secret


def test_sem_jwt_secret_em_producao_o_boot_falha(monkeypatch):
    # O default está no repositório: com ele, qualquer um assina token de admin.
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        resolve_jwt_secret()


def test_jwt_secret_definido_e_usado(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-do-servidor")
    assert resolve_jwt_secret() == "segredo-do-servidor"


def test_fora_de_producao_o_default_local_continua(monkeypatch):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    assert resolve_jwt_secret() == "fallback_secret_key"
