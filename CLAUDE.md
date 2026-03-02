# Backend InvestLink

Flask 3.0.3 · SQLAlchemy 2.0.30 · PostgreSQL 13 · Python 3.14 (local) / 3.9 (CI/Docker)

## Comandos essenciais

```bash
# Testes (sempre com PYTHONPATH)
cd /d/Investlink/backend
PYTHONPATH=app python -m pytest tests/unit/ -v

# Testes de um arquivo específico
PYTHONPATH=app python -m pytest tests/unit/test_stock_services.py -v

# Lint
python -m black --check .
python -m flake8 .
```

## Estrutura
```
app/
  models/    → Stock, Fii, User, Favorite, FavoriteFii, UserLayout
  services/  → lógica de negócio (camada principal)
  routes/    → blueprints Flask (só parse de request + chamada ao service)
  config.py  → db = SQLAlchemy()  |  jwt = JWTManager()
  app.py     → cria app, registra blueprints, db.create_all()
tests/
  unit/
    conftest.py  → fixtures: app, mock_db_session, sample_user, sample_stock, sample_fii, sample_layout
```

## Padrão obrigatório — Serviços

```python
def minha_funcao(param):
    try:
        # lógica usando db.session, Model.query
        db.session.commit()
        return jsonify({"message": "ok"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro: {e}")
        return jsonify({"message": "An error occurred"}), 500
```

## Padrão obrigatório — Rotas

```python
@bp.route("/recurso", methods=["GET"])
@jwt_required()
def listar():
    user_id = get_jwt_identity()
    return service_function(user_id)
```

## Padrão obrigatório — Testes

```python
# Sempre dentro de app.app_context()
# Mockar db via patch do módulo do serviço
with patch('services.stock_services.db') as mock_db, \
     patch('services.stock_services.Stock.query') as mock_query:
    mock_db.session = mock_db_session   # fixture do conftest
    mock_query.filter_by.return_value.first.return_value = ...
```

## Gotchas
- `PYTHONPATH=app` é obrigatório — sem isso os imports `from models.x import X` falham
- `user_layout_service.py` usa decorator `@handle_db_operations` que faz commit automaticamente — mockar `db` no patch do serviço
- `validate_email` rejeita `..` consecutivos (lookahead no regex)
- Sem type hints (padrão do projeto)
- Sem migrations — usa `db.create_all()` no startup
