# Imagem slim de um Python com suporte: a `python:3.9` completa trazia o Debian
# inteiro (imagemagick, headers de desenvolvimento...) e dezenas de CVEs de
# sistema que a aplicação nunca usa, num Python que já saiu de suporte.
FROM python:3.12-slim

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Log direto no stdout do contêiner, sem buffer — senão o `docker logs` só
# mostra o que a aplicação escreveu depois que o buffer encheu.
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Nenhuma dependência compila nada: psycopg2-binary, bcrypt e greenlet vêm em
# wheel. O único pacote de sistema é o curl, que o healthcheck do compose do
# servidor usa (`curl -fsS http://localhost:5000/health`) e a slim não traz.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo requirements.txt e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código do backend para o contêiner
COPY . .

# Sem root: o processo só lê o código e fala com o banco pela rede.
RUN chmod +x /app/docker-entrypoint.sh \
    && useradd --system --no-create-home --uid 10001 app
USER app

# Expõe a porta que a aplicação vai rodar
EXPOSE 5000

# O entrypoint aplica as migrações e sobe o gunicorn. O servidor embutido do
# Flask (`python app/app.py`) continua valendo para desenvolvimento local, mas
# não atende produção: é single-thread e o debugger é execução remota de código.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
