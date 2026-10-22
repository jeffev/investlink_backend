#!/bin/sh
set -e

# As migrações rodam aqui, com a aplicação ainda parada: um processo só aplica
# o schema antes de qualquer worker aceitar requisição. Se falhar, o contêiner
# morre e o deploy reverte — melhor que servir tráfego com schema pela metade.
python -c "import wsgi; wsgi.prepare_database()"

exec gunicorn \
  --bind "0.0.0.0:${PORT:-5000}" \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile - \
  wsgi:application
