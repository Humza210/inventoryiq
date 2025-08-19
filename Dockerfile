FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==22.0.0

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD exec gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-8080} wsgi:app
