FROM python:3.14-alpine AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY ./miamap/restapi /app

# Disable development dependencies
ENV UV_NO_DEV=1

ENV UV_LINK_MODE=copy

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app
RUN uv sync --frozen --no-cache --no-dev

FROM python:3.14-alpine
COPY --from=builder /app /app
COPY --from=builder /bin/uv /bin/uv
WORKDIR /app

CMD ["uv", "run", "fastapi", "run"]
# CMD ["uv", "run", "fastapi", "dev"]
