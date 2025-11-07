# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Минимальные системные зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Установка зависимостей
COPY requirements2.txt .
RUN python -m pip install --no-cache-dir -r requirements2.txt

# Копируем приложение
COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "main2.py"]
