# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV REDIS_URL=redis://redis:6379/0 \
    MONGO_URL=mongodb://mongo:27017 \
    MONGO_DB=crawler \
    CONCURRENCY=100 \
    DOMAIN_COOLDOWN_SECONDS=1.0 \
    REQUEST_TIMEOUT_SECONDS=15 \
    MAX_CONTENT_SIZE_BYTES=3145728 \
    USER_AGENT=DistributedCrawler/1.0

ENTRYPOINT ["python","-m","crawler.main"]
CMD ["run","--concurrency","100","--max-pages","1000"]
