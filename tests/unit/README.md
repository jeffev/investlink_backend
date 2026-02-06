# Backend Unit Tests - InvestLink

Este diretório contém testes unitários para os serviços backend do InvestLink.

## Estrutura de Testes

### Arquivos de Teste

- **test_user.py** - Testes para modelo User
- **test_user_services.py** - Testes para serviço User (validação, CRUD)
- **test_stock.py** - Testes para modelo Stock (Graham formula, discount)
- **test_stock_services.py** - Testes para serviço Stock (CRUD, favoritas)
- **test_favorite.py** - Testes para modelo Favorite
- **test_favorite_services.py** - Testes para serviço Favorite (CRUD)
- **test_fii_services.py** - Testes para serviço FII (CRUD)
- **test_favorite_fii_services.py** - Testes para serviço Favorite_FII (CRUD)
- **test_user_layout_services.py** - Testes para serviço UserLayout (CRUD)

### Fixtures Compartilhadas (conftest.py)

O arquivo `conftest.py` fornece fixtures reutilizáveis para todos os testes:

- **mock_db_session** - Sessão de banco de dados mockada
- **sample_user** - Usuário de teste padrão
- **sample_stock** - Ação de teste padrão
- **sample_fii** - FII de teste padrão
- **sample_favorite** - Favorita de ação de teste
- **sample_favorite_fii** - Favorita de FII de teste
- **sample_layout** - Layout de usuário de teste
- **auth_token** - Token JWT de teste
- **valid_user_data** - Dados válidos para criação de usuário
- **invalid_user_data** - Dados inválidos para testes de validação

## Rodando os Testes

### Todos os testes
```bash
cd backend
pip install -r requirements.txt
pytest tests/unit/
```

### Testes específicos
```bash
# Apenas testes de usuário
pytest tests/unit/test_user_services.py

# Apenas testes com cobertura
pytest tests/unit/ --cov=app --cov-report=html

# Com saída verbose
pytest tests/unit/ -v
```

## Padrões de Teste

### 1. Estructura Padrão

```python
import sys
import os
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.user import User  # noqa: E402
from services.user_services import validate_email  # noqa: E402
```

### 2. Testes de Validação

```python
def test_validate_email_valid():
    """Test email validation with valid format"""
    assert validate_email("user@example.com") is True

def test_validate_email_invalid():
    """Test email validation with invalid format"""
    assert validate_email("invalid.email") is False
```

### 3. Testes de Serviço com Mocks

```python
@patch('services.user_services.User.query')
@patch('services.user_services.db.session')
def test_list_users(mock_session, mock_query):
    """Test list_users returns all users"""
    from services.user_services import list_users
    
    user1 = User(id=1, user_name="john", name="John", email="j@example.com")
    mock_query.all.return_value = [user1]
    
    response = list_users()
    data = response.get_json()
    
    assert len(data) == 1
    assert data[0]["user_name"] == "john"
```

### 4. Usando Fixtures

```python
def test_with_fixture(sample_user, valid_user_data):
    """Test usando fixtures compartilhadas"""
    assert sample_user.id == 1
    assert sample_user.email == "test@example.com"
    assert valid_user_data["user_name"] == "newuser"
```

## Cobertura de Testes

### Atual
- Models: ✓ 100% (test_user.py, test_stock.py, test_favorite.py)
- Services: ⚠️ ~60% (test_user_services.py, test_stock_services.py, test_favorite_services.py)
- Routes: ✗ 0% (integração tests apenas)

### Meta
- Models: ✓ 100%
- Services: ✓ 80%+
- Routes: ✓ Teste de integração

## Melhores Práticas

1. **Iso late Database Calls**
   - Use `@patch` para mockar `db.session` e queries
   - Nunca use banco de dados real em testes unitários

2. **Test One Thing**
   - Cada teste deve validar um comportamento específico
   - Use nomes descritivos: `test_<function>_<scenario>`

3. **Arrange-Act-Assert**
   ```python
   # Arrange - Setup
   user_data = {...}
   
   # Act - Execute
   response = new_user(user_data)
   
   # Assert - Verify
   assert response[1] == 201
   ```

4. **Use Fixtures para DRY**
   - Dados compartilhados em `conftest.py`
   - Evita repetição entre testes

5. **Mock External Dependencies**
   - API calls
   - Database
   - JWT operations
   - Requests HTTP

## Adicionando Novos Testes

1. Crie arquivo `test_<service>_services.py`
2. Importe com o padrão sys.path
3. Use `@patch` para dependências externas
4. Siga padrão Arrange-Act-Assert
5. Use fixtures do `conftest.py`

## Execução em CI/CD

Os testes rodam automaticamente na pipeline GitHub Actions:
- Verificação de lint (Flake8)
- Execução de testes
- Cobertura de testes

Verifique `.github/workflows/` para mais detalhes.
