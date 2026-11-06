# syntax=docker/dockerfile:1

# ---- Stage 1: compile the React UI to static files (Node exists only here) ----
FROM node:24-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime that serves API + built UI ----------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    # Trust X-Forwarded-For/-Proto only from these addresses (uvicorn accepts
    # IPs and CIDR ranges). Default: localhost and private networks, i.e. a
    # reverse proxy or cloudflared on the same host / Docker network. Narrow it
    # to your proxy's exact address in production, e.g. FORWARDED_ALLOW_IPS=172.18.0.2.
    # Never use "*" on a port the internet can reach: clients could spoof their IP
    # and dodge per-IP rate limits and lockout.
    FORWARDED_ALLOW_IPS="127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

WORKDIR /app

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini main.py ./
COPY app ./app
COPY migrations ./migrations
COPY --from=ui /ui/dist ./frontend/dist

RUN mkdir -p /app/data && chown app:app /app/data
VOLUME ["/app/data"]

# Never run as root.
USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health/ready', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-server-header", "--no-access-log"]
