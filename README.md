# InvestLink Backend

API REST do InvestLink — serviço responsável por autenticação, gestão de usuários, dados de ações, FIIs e favoritos.

## Stack

- Python 3.9
- Flask 3.0.3
- SQLAlchemy 2.0.30 + Flask-Migrate (Alembic)
- PostgreSQL 13
- Flask-JWT-Extended 4.6.0
- bcrypt 4.1.3

## Execução local (sem Docker)

```bash
cd backend
pip install -r requirements.txt
```

Configure as variáveis de ambiente:

```env
DATABASE_URL=postgresql://postgres:senha@localhost:5432/investlink
JWT_SECRET_KEY=sua_chave_secreta
FLASK_ENV=development
```

```bash
python app/app.py
```

O servidor sobe em `http://localhost:5000`. Na primeira execução as migrations são aplicadas e o usuário `admin/admin` é criado automaticamente.

## Execução com Docker

Na raiz do monorepo:

```bash
docker compose up --build backend
```

## Usuário padrão

| Campo  | Valor                  |
|--------|------------------------|
| Login  | admin                  |
| Senha  | admin                  |
| Perfil | ADMIN                  |
| E-mail | admin@investlink.local |

## Documentação da API

Swagger disponível em `http://localhost:5000/swagger` após iniciar o servidor.

## Endpoints

Todos os endpoints (exceto login e registro) exigem `Authorization: Bearer <token>`.

### Autenticação

| Método | Rota             | Descrição              | Auth     |
|--------|------------------|------------------------|----------|
| POST   | `/v1/user/login` | Login (retorna JWT)    | Não      |
| POST   | `/v1/users`      | Registro de novo usuário | Não    |

### Usuários

| Método | Rota                  | Descrição               | Perfil   |
|--------|-----------------------|-------------------------|----------|
| GET    | `/v1/users`           | Listar usuários         | Qualquer |
| GET    | `/v1/user/<id>`       | Detalhar usuário        | Qualquer |
| PUT    | `/v1/user/<id>`       | Editar usuário          | Qualquer |
| DELETE | `/v1/user/<id>`       | Excluir usuário         | Qualquer |

### Ações

| Método | Rota                         | Descrição               | Perfil   |
|--------|------------------------------|-------------------------|----------|
| GET    | `/v1/stocks`                 | Listar ações            | Qualquer |
| GET    | `/v1/stock/<ticker>`         | Detalhar ação           | Qualquer |
| POST   | `/v1/stocks`                 | Criar ação              | Qualquer |
| PUT    | `/v1/stock/<ticker>`         | Editar ação             | Qualquer |
| DELETE | `/v1/stock/<ticker>`         | Excluir ação            | Qualquer |
| PUT    | `/v1/stocks/update-stocks`   | Atualizar cotações      | ADMIN    |

### FIIs

| Método | Rota                       | Descrição               | Perfil   |
|--------|----------------------------|-------------------------|----------|
| GET    | `/v1/fiis`                 | Listar FIIs             | Qualquer |
| GET    | `/v1/fii/<ticker>`         | Detalhar FII            | Qualquer |
| POST   | `/v1/fiis`                 | Criar FII               | Qualquer |
| PUT    | `/v1/fii/<ticker>`         | Editar FII              | Qualquer |
| DELETE | `/v1/fii/<ticker>`         | Excluir FII             | Qualquer |
| PUT    | `/v1/fiis/update-fiis`     | Atualizar cotações      | ADMIN    |

### Favoritos — Ações

| Método | Rota                         | Descrição                  | Perfil   |
|--------|------------------------------|----------------------------|----------|
| GET    | `/v1/favorites`              | Listar favoritos           | Qualquer |
| GET    | `/v1/favorite/<id>`          | Detalhar favorito          | Qualquer |
| POST   | `/v1/favorites`              | Criar favorito (com dados) | Qualquer |
| PUT    | `/v1/favorite/<id>`          | Editar favorito            | Qualquer |
| DELETE | `/v1/favorite/<id>`          | Remover favorito           | Qualquer |
| POST   | `/v1/favorites/<ticker>`     | Adicionar ação aos favoritos | Qualquer |
| DELETE | `/v1/favorites/<ticker>`     | Remover ação dos favoritos | Qualquer |

### Favoritos — FIIs

| Método | Rota                             | Descrição                   | Perfil   |
|--------|----------------------------------|-----------------------------|----------|
| GET    | `/v1/favorites/fii`              | Listar FIIs favoritos       | Qualquer |
| GET    | `/v1/favorite/fii/<id>`          | Detalhar FII favorito       | Qualquer |
| POST   | `/v1/favorites/fii`              | Criar favorito (com dados)  | Qualquer |
| PUT    | `/v1/favorite/fii/<id>`          | Editar FII favorito         | Qualquer |
| DELETE | `/v1/favorite/fii/<id>`          | Remover FII favorito        | Qualquer |
| POST   | `/v1/favorites/fii/<ticker>`     | Adicionar FII aos favoritos | Qualquer |
| DELETE | `/v1/favorites/fii/<ticker>`     | Remover FII dos favoritos   | Qualquer |

### Layout de Usuário

| Método | Rota                        | Descrição                        | Perfil   |
|--------|-----------------------------|----------------------------------|----------|
| GET    | `/v1/user_layout/<layout>`  | Buscar layout salvo da página    | Qualquer |
| POST   | `/v1/user_layout`           | Salvar layout de página          | Qualquer |

## Estrutura

```
backend/
├── app/
│   ├── app.py           → entrypoint, migrations, seed
│   ├── config.py        → criação do app Flask e DB
│   ├── utils.py         → registro de rotas e middleware JWT
│   ├── models/          → User, Stock, Fii, Favorite, UserLayout
│   ├── services/        → lógica de negócio
│   └── routes/          → handlers HTTP
├── migrations/          → Alembic migrations
├── tests/unit/          → testes unitários (pytest)
└── requirements.txt
```

## Testes

```bash
cd backend
pytest tests/ -v
```
