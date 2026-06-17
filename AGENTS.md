# AGENTS.md — Hermes Grafana Observability Stack

> **Purpose:** This file exists so any AI agent (Hermes, Claude, Copilot, etc.) can quickly understand this repo, make safe changes, and avoid breaking the stack.
> **Audience:** AI agents working on this codebase.
> **Last updated:** 2026-06-17

---

## 1. What This Project Is

A Docker Compose-based observability stack for the [Hermes Agent](https://github.com/NousResearch/Hermes-Trainer) runtime. It exposes Hermes SQLite databases and log files as metrics and logs viewable in Grafana.

**Key insight:** Hermes stores all operational data in SQLite (not a traditional TSDB or log aggregator). This project bridges that gap by:
- Running SQL queries against Hermes DBs and exposing results as Prometheus metrics (via a custom Python exporter)
- Shipping all Hermes log files to Loki (via Promtail)
- Visualizing everything in Grafana dashboards

---

## 2. Stack Architecture (One Sentence Per Service)

| Service | Role | Why It Exists |
|---------|------|---------------|
| **Grafana** (3000) | Dashboard UI | User-facing. Pre-provisioned with Prometheus + Loki datasources. |
| **Prometheus** (9090) | Metrics TSDB | Scrapes numeric data from Node Exporter and SQLite Exporter every 15s. |
| **Loki** (3100) | Log indexer | Receives log streams from Promtail. Grafana queries it natively. |
| **Promtail** | Log shipper | Reads `~/.hermes/**/*.log` and pushes to Loki. Tracks offsets in `positions.yaml`. |
| **Node Exporter** (9100) | Host telemetry | Exposes Linux CPU, memory, disk, network metrics. |
| **SQLite Exporter** (9200) | Custom bridge | Python FastAPI app. Executes SQL against Hermes DBs, returns Prometheus-format metrics. |

**Network:** All services share a Docker bridge network `hermes-observability`.

---

## 3. File Map — What Lives Where

### Root config
- `docker-compose.yml` — The orchestration. **Never** edit service names or network name without updating dependent configs.
- `.env` — Only sets `HERMES_HOME=/home/urbano/.hermes`. Used by compose for volume binding.

### Metrics pipeline
- `prometheus/prometheus.yml` — Scrape targets. `sqlite-exporter:9200` and `node-exporter:9100`.
- `prometheus/rules/` — Prometheus alerting rules (empty placeholder; add `.yml` files here).

### Logs pipeline
- `loki/loki-config.yml` — Loki server config. Uses filesystem-backed storage (`/loki/chunks`). Retention: 168h (7 days).
- `promtail/promtail-config.yml` — Defines log sources with Loki labels. Uses glob patterns for rotated logs (`agent.log*`).

### Grafana
- `grafana/provisioning/datasources/datasources.yml` — Auto-provisions Prometheus and Loki on first startup.
- `dashboards/*.json` — Pre-built dashboards. Imported automatically via Grafana provisioning (read `README.md` section on dashboards).

### Custom exporter
- `sqlite-exporter/main.py` — FastAPI app. Serves `/metrics` (Prometheus format), `/health`, `/reload`.
- `sqlite-exporter/queries.yml` — **The main place to add new metrics.** Each block = one SQL query → one metric.
- `sqlite-exporter/Dockerfile` — `python:3.13-slim`. Installs deps, copies `main.py` + `queries.yml`.
- `sqlite-exporter/requirements.txt` — `fastapi`, `uvicorn`, `prometheus-client`, `pyyaml`.

---

## 4. How to Add a New Metric (Agent Cheat Sheet)

**Scenario:** Hermes added a new table `alerts` in `state.db` and you want to expose `alert_count`.

1. **Edit** `sqlite-exporter/queries.yml`:
   ```yaml
   - metric: alert_count
     type: gauge
     db: state.db
     description: Number of active alerts
     sql: SELECT COUNT(*) AS value FROM alerts WHERE resolved = 0
     labels: []
     value: value
   ```

2. **Hot-reload** the exporter (no container restart needed):
   ```bash
   curl http://localhost:9200/reload
   ```

3. **Verify** the metric appears:
   ```bash
   curl -s http://localhost:9200/metrics | grep hermes_alert_count
   ```

4. **Add to a dashboard** via Grafana UI (or edit the JSON in `dashboards/` and restart Grafana).

**Important:**
- `db` path is relative to `HERMES_DB_ROOT` (mounted at `/hermes` in the container).
- Always use `mode=ro` SQLite URIs. The exporter does this automatically.
- Labels must match SQL column names. Label values are coerced to strings.
- If a DB file doesn't exist, the query is silently skipped (no crash).

---

## 5. How to Add a New Log Source

**Scenario:** A new Hermes component writes to `~/.hermes/new_service/output.log`.

1. **Edit** `promtail/promtail-config.yml`:
   ```yaml
   - job_name: hermes-new-service
     static_configs:
       - targets:
           - localhost
         labels:
           job: hermes-new-service
           app: hermes
           component: new_service
           __path__: /hermes/new_service/*.log
   ```

2. **Restart** Promtail:
   ```bash
   docker compose restart promtail
   ```

3. **Verify** in Grafana Explore → Loki datasource: `{app="hermes", component="new_service"}`

---

## 6. Common Operations

### Start the full stack
```bash
cd ~/MyCode/hermes-grafana
docker compose up -d --build
```

### View logs
```bash
docker compose logs -f grafana
docker compose logs -f sqlite-exporter
docker compose logs -f promtail
```

### Restart a single service
```bash
docker compose restart sqlite-exporter
```

### Full teardown (preserves volumes → data is kept)
```bash
docker compose down
```

### Full teardown + destroy data
```bash
docker compose down -v
```

### Rebuild just the custom exporter
```bash
docker compose up -d --build sqlite-exporter
```

### Check Prometheus targets
```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].labels.job'
```

### Check SQLite exporter health
```bash
curl http://localhost:9200/health
curl http://localhost:9200/metrics | head -20
```

---

## 7. Gotchas & Safety Rules

| Gotcha | Why It Happens | Safe Fix |
|--------|---------------|----------|
| **SQLite "database is locked"** | Hermes has a write transaction open. | Exporter already uses `?mode=ro` + 5s timeout. If still failing, wait 10s and retry. |
| **Promtail not picking up new logs** | Promtail tracks file offsets in `positions.yaml`. | Restart Promtail container. |
| **Grafana dashboards disappear** | Dashboards are provisioned from JSON files on startup only. | Place JSON in `dashboards/` **before** first start. To update live, use Grafana UI → Export → overwrite file. |
| **SQLite Exporter crashes on bad SQL** | `queries.yml` has a syntax error or references a missing column. | Check exporter logs: `docker compose logs sqlite-exporter`. Fix query, hit `/reload`. |
| **Metrics look stale** | Prometheus scrape interval is 15s; SQL queries may cache. | The exporter re-runs SQL on every `/metrics` hit. If stale, check Prometheus target health. |
| **Loki disk grows** | Log volume is high. | Loki retention is 168h. To extend, edit `loki/loki-config.yml` `limits_config.reject_old_samples_max_age` and `table_manager.retention_period`. |
| **"permission denied" on Docker socket** | User not in `docker` group. | See `SETUP.md` — run `sudo usermod -aG docker $USER`, logout/login. |

---

## 8. Data Flow Diagram (For Agents)

```
Hermes Runtime
    │
    ├─→ SQLite DBs (state.db, metrics.db, ollama_usage.db, kanban.db, cron_logs.db, inbox_captures.db)
    │       │
    │       └─→ SQLite Exporter (port 9200) ──SQL──┐
    │                                              │
    ├─→ Log files (*.log, rotated .log.1 .log.2)  │
    │       │                                      │
    │       └─→ Promtail ──push──→ Loki (3100)     │
    │                                              │
    └─→ Host resources (CPU, RAM, disk, net)       │
            │                                      │
            └─→ Node Exporter (9100) ──────────────┤
                                                   │
                              ┌────────────────────┘
                              │
                        Prometheus (9090)
                              │
                              └─→ Grafana (3000) ←── Loki datasource
```

---

## 9. Hermes DB Schema Quick Reference

When writing new queries in `queries.yml`, these are the key tables/columns:

### `state.db` (sessions, messages)
- `sessions`: `id`, `source`, `model`, `started_at` (unix epoch), `ended_at`, `end_reason`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `message_count`, `tool_call_count`
- `messages`: `session_id`, `role`, `timestamp` (unix epoch), `token_count`, `tool_name`

### `metrics.db` (executions, tool_calls, daily_stats)
- `executions`: `timestamp` (ISO), `session_id`, `model`, `execution_time_s`, `total_tokens`, `cost_usd`, `success`
- `tool_calls`: `execution_id`, `tool_name`, `timestamp`
- `daily_stats`: `date`, `total_executions`, `total_tokens`, `total_cost_usd`, `error_count`

### `ollama_usage.db`
- `usage_calls`: `timestamp_utc` (ISO), `model`, `duration_ms`, `estimated_cost`, `session_id`
- `usage_status`: `timestamp_utc`, `tier`, `session_remaining`, `weekly_remaining`

### `db/cron_logs.db`
- `cron_runs`: `job_name`, `run_at` (ISO), `status`, `exit_code`

### `logs/inbox_captures.db`
- `inbox_captures`: `created_at`, `status`, `duration_seconds`, `category`, `url`

### `kanban.db`
- `tasks`: `id`, `title`, `status`, `priority`, `created_at` (unix epoch), `completed_at`, `workspace_kind`

**Always** check actual schema with `.schema <table>` if unsure:
```bash
sqlite3 ~/.hermes/state.db ".schema sessions"
```

---

## 10. Testing Changes

Before declaring a change "done", verify:

1. **Config syntax:**
   ```bash
   docker compose config   # validates docker-compose.yml
   ```

2. **SQLite exporter queries:**
   ```bash
   # Test against live DB
   sqlite3 "file:/home/urbano/.hermes/state.db?mode=ro" "SELECT COUNT(*) FROM sessions;"
   ```

3. **Promtail config:**
   ```bash
   docker compose run --rm promtail -config.file=/etc/promtail/promtail-config.yml -dry-run
   ```

4. **Dashboard JSON validity:**
   ```bash
   python3 -c "import json; json.load(open('dashboards/hermes-overview.json'))"
   ```

---

## 11. Related Files in This Repo

| File | What It Contains |
|------|-----------------|
| `ARCHITECTURE.md` | Full design rationale, extensibility roadmap, security notes |
| `SETUP.md` | Human-facing step-by-step deployment guide |
| `CHANGELOG.md` | Session history, blocker status, what was built when |
| `README.md` | Quick-start for humans |

---

*End of AGENTS.md — When editing this file, keep it concise. Agents need speed, not prose.*
