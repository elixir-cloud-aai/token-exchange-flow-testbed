# Image of the testbed's services, session and end-to-end run. It holds no
# secrets, and takes no build arguments: client secrets only come in at
# runtime (`lslogin.env`, see `compose.lslogin.yaml`). Images are pinned by
# digest, so that rebuilds use the same ones.

# uv, for installing the versions of `uv.lock`; not part of the image
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

FROM python:3.13-slim@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1 AS build
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src src
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python

FROM python:3.13-slim@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1
LABEL org.opencontainers.image.title="Token exchange testbed"
LABEL org.opencontainers.image.licenses="Apache-2.0"
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 TESTBED_DOCS=/app/docs
WORKDIR /app
COPY --from=build /app/.venv .venv
# The end-to-end run also runs every session command of the docs
COPY docs docs
USER 1000:1000
