FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src/ src/
RUN uv sync --frozen

EXPOSE 8000

ENTRYPOINT ["uv", "run", "gmail"]
