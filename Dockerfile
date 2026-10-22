# Usa a imagem oficial do Python
FROM python:3.9

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Log direto no stdout do contêiner, sem buffer — senão o `docker logs` só
# mostra o que a aplicação escreveu depois que o buffer encheu.
ENV PYTHONUNBUFFERED=1

# Copia o arquivo requirements.txt e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código do backend para o contêiner
COPY . .

RUN chmod +x /app/docker-entrypoint.sh

# Expõe a porta que a aplicação vai rodar
EXPOSE 5000

# O entrypoint aplica as migrações e sobe o gunicorn. O servidor embutido do
# Flask (`python app/app.py`) continua valendo para desenvolvimento local, mas
# não atende produção: é single-thread e o debugger é execução remota de código.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
