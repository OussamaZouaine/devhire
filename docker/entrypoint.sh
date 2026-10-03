#!/bin/sh
set -e

# Only the web container applies migrations; workers start straight away.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
