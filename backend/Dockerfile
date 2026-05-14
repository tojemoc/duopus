# Dev / smoke-test API image (Python 3.12 + locked deps via uv).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --shell /usr/sbin/nologin --no-create-home app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
