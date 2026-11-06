---
name: observability
description: Running and monitoring this app in production - health and readiness checks, request ids, access logs, JSON log shipping, what to alert on, and how to investigate an incident. Load before changing health checks, middleware, logging setup or deployment config, when adding a dependency the app relies on (database, email, payment API), or when debugging a production problem.
---

# Observability and Monitoring

Use what the template already emits (health checks, structured logs, access logs, request ids, audit events) before adding new tooling. Code-level rules for errors and log statements are in `error-handling-logging`.

## 1. Signals the app emits

| Signal | Where | Use |
|---|---|---|
| Liveness | `GET /api/health/live` → `{"status":"ok"}` | "is the process up" (container HEALTHCHECK, restarts) |
| Readiness | `GET /api/health/ready` → 200, or 503 if the database is unreachable | load balancer / uptime monitor; deploy gates |
| Request id | `X-Request-ID` on every response; in every log line | follow one request end to end |
| Access log | logger `app.access`: method, path, status, `duration_ms`, client IP | traffic, latency, error rates |
| Error log | logger `app.errors` (unhandled exceptions with traceback) + feature loggers | debugging |
| Audit trail | `aud_event` table (+ log line) | security investigations, who-did-what |
| Startup checks | `UnsafeConfiguration` stops the app on unsafe production settings | config mistakes caught before serving |

Health endpoints are public, unauthenticated and exempt from host validation so the container and the proxy can reach them. They return no versions, hostnames or dependency details: keep it that way.

## 2. Logs in production

- `LOG_FORMAT=json` (the production default) writes one JSON object per line to stdout. Docker captures it; ship it with your log stack (Loki/Grafana, ELK, Datadog, CloudWatch, or simply `docker compose logs`).
- Configure the Docker log driver with rotation so disks don't fill:
  ```yaml
  logging:
    driver: json-file
    options: { max-size: "20m", max-file: "5" }
  ```
- Useful queries: everything for one request (`request_id = "…"`); slow requests (`logger = "app.access" and duration_ms > 1000`); error rate (`logger = "app.access" and status >= 500`); failed sign-ins (`message ~ "auth.login" and outcome=failure`, or the `aud_event` table).
- Health probes and static files are logged at DEBUG, so they don't drown API and page traffic.

## 3. What to monitor and alert on

Start with these; tune thresholds to your traffic.

| Alert | Source | Suggested trigger |
|---|---|---|
| App down | external uptime check on `/api/health/ready` | 2 consecutive failures (1-minute interval) |
| Elevated server errors | access log `status >= 500` | > 1% of requests over 5 min, or any burst of 10+ |
| Slow responses | access log `duration_ms` p95 | p95 > 1 s for 10 min |
| Sign-in attack | `auth.login` failures / `auth.lockout` events | spike vs baseline, or 20+ lockouts/hour |
| Permission probing | access log `status = 403` | spike vs baseline |
| Rate limiting | `status = 429` | sustained spike |
| Email failing | `Failed to send email` (logger `app.integrations.mail`) | any in 15 min (users can't reset passwords or get codes) |
| Turnstile/Cloudflare failing | 503 "Verification service unavailable" | any sustained |
| Container restarts / OOM | Docker / host monitoring | any unexpected restart |
| Disk / DB size | host metrics | > 80% |
| TLS certificate expiry | uptime monitor | < 14 days |

Send alerts to a channel people actually watch, with a link to the log query.

## 4. Adding instrumentation

- **New dependency the app needs to serve traffic** (database, cache, required API): add it to the readiness check in `app/features/system/router.py` with a short timeout, returning only a generic 503. Optional dependencies (email) are not readiness checks; alert on their failures instead.
- **Timing a slow operation**: log once with `duration_ms` in `extra`, at INFO for business operations, WARNING when over a threshold.
- **Metrics**: if you need dashboards beyond log queries, add Prometheus metrics (`prometheus-client`): request count/latency by route template and status, plus business counters. Expose `/api/metrics` only on the internal network or behind auth, never publicly, and use route templates (`/api/orders/{order_id}`), never raw paths, as labels.
- **Tracing**: if several services are involved, add OpenTelemetry and propagate the same request id (`X-Request-ID`) to downstream calls.
- Don't add tooling the project doesn't need yet; each signal must have a consumer (a dashboard, an alert or a runbook).

## 5. Investigating an incident

1. Get the **reference** (request id) from the user's error message, or the time and action.
2. Search logs for that `request_id`: you get the access line (status, duration) and any error/traceback from the same request.
3. For security questions (who changed a role, who signed in), query `aud_event` by actor, target or time; it survives log rotation.
4. Check readiness and recent deploys (`docker compose ps`, `docker compose logs --since 30m app`).
5. After the fix, add the missing test, and the missing alert if the problem was found by a user rather than by monitoring.

## 6. Deployment hygiene

- The container HEALTHCHECK calls `/api/health/ready`; compose should use `restart: unless-stopped`.
- Keep `LOG_LEVEL=INFO` in production; use DEBUG only temporarily.
- Clocks in UTC everywhere (logs, database, audit) so events line up.
- Time-box log retention to what you need (e.g. 14–30 days); keep audit data per your compliance needs.

## 7. Checklist

- [ ] New required dependency is in the readiness check (generic 503, short timeout).
- [ ] New failure modes produce a WARNING/ERROR log with useful `extra` fields and the request id.
- [ ] No sensitive values in logs or health responses.
- [ ] An alert exists (or is proposed) for any new failure that users would notice.
- [ ] Metrics endpoints, if any, are not public.
