FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# collectstatic needs a SECRET_KEY at build time only.
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && useradd --create-home devhire \
    && mkdir -p /app/media \
    && chown -R devhire /app/media

USER devhire

EXPOSE 8000

ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
