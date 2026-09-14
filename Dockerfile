FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml ./
RUN uv pip install --system aiogram aiohttp aiosqlite beautifulsoup4 apscheduler pydantic certifi playwright pypdf
RUN python -m playwright install --with-deps chromium

COPY . .

EXPOSE 8080

CMD ["python", "-m", "src.main"]
