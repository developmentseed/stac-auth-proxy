# https://github.com/astral-sh/uv-docker-example/blob/c16a61fb3e6ab568ac58d94b73a7d79594a5d570/Dockerfile

# Build stage
FROM python:3.13-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/usr/local

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY uv.lock pyproject.toml ./

RUN uv sync --frozen --no-install-project --no-dev

ADD . /app
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy only the source code directory needed at runtime
COPY --from=builder /app/src/stac_auth_proxy /app/src/stac_auth_proxy

RUN useradd -m -u 1001 -s /bin/bash user && \
    chown -R user:user /app

USER user

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "stac_auth_proxy"]