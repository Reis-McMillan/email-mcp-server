FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY src/ src/
RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "email-mcp-server", "--host", "0.0.0.0"]
