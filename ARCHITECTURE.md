# Hermes Observability Stack — Architecture Document

> **Version:** 1.0
> **Date:** 2026-06-17
> **Author:** Hermes Agent (auto-generated)
> **Scope:** Provide full observability over the Hermes Agent runtime using Grafana.

---

## 1. Objective

Transform the Hermes Agent from a black-box into an observable system. We want:
- **Metrics**: Token usage, cost, execution latency, cron reliability, task velocity, model performance.
- **Logs**: Real-time tailing and historical search across all Hermes log files (including rotated).
- **System correlation**: Link metrics with host resources (CPU, RAM, disk) to answer “Why did it slow down?”.
- **Alerting capability**: Proactively catch anomalies (cron errors, cost spikes, queue backlogs).

---

## 2. Stack Components

| Component | Technology | Port | Role |
|-----------|-----------|------|------|
| Dashboard | **Grafana** | 3000 | Unified visualization layer. Plugs natively into Prometheus (metrics) and Loki (logs). |
| Metrics TSDB | **Prometheus** | 9090 | Scrapes and stores time-series numeric data from exporters. |
| Log Aggregator | **Loki** | 3100 | Indexes log streams. Lightweight alternative to Elasticsearch. |
| Log Shipper | **Promtail** | — (no incoming port) | Reads Hermes log files on disk and pushes them to Loki. |
| Host Telemetry | **Node Exporter** | 9100 | Exposes Linux host metrics (CPU, memory, disk, network, load). |
| SQLite Bridge | **SQLite Exporter** (custom) | 9200 | Executes SQL queries against Hermes SQLite databases and exposes results as Prometheus metrics. |

---

## 3. Data Sources & Mappings

### 3.1 SQLite Databases (via SQLite Exporter)

| Database | Table(s) | Metrics Exposed |
|----------|----------|-----------------|
| `~/.hermes/state.db` | `sessions` | Sessions/hour, token burn, cost per model, message/tool ratios, end-reason distribution |
| `~/.hermes/state.db` | `messages` | Messages per hour, token density by role |
| `~/.hermes/metrics.db` | `executions` | Execution latency, success ratio, total cost, token consumption over time |
| `~/.hermes/metrics.db` | `tool_calls` | Top tools leaderboard, tool call rate |
| `~/.herses/metrics.db` | `skill_usage` | Skill adoption heatmap |
| `~/.hermes/metrics.db` | `daily_stats` | Daily rollups of executions, tokens, costs, errors |
| `~/.hermes/ollama_usage.db` | `usage_calls` | Ollama request latency, model popularity, estimated spend |
| `~/.hermes/ollama_usage.db` | `usage_status` | Budget health (remaining session/weekly budget) |
| `~/.hermes/ollama_usage.db` | `batch_runs` | Batch job throughput and duration |
| `~/.hermes/db/cron_logs.db` | `cron_runs` | Cron reliability by job, error spike detection, exit-code distribution |
| `~/.hermes/logs/inbox_captures.db` | `inbox_captures` | Processing throughput, backlog depth, category breakdown, failure rate |
| `~/.hermes/kanban.db` | `tasks` | Backlog size, completion velocity (tasks/day), priority distribution, blocked tasks |
| `~/.hermes/kanban.db` | `task_runs` | Run duration, failure rates by task |

### 3.2 Log Files (via Promtail / Loki)

| File | Rotation Pattern | Labels Applied | Use Case |
|------|----------------|---------------|----------|
| `~/.hermes/logs/agent.log` | Yes (`.1`, `.2`, `.3`) | `app=hermes`, `component=agent` | Agent lifecycle, model activity, tool execution |
| `~/.hermes/logs/errors.log` | No | `app=hermes`, `component=errors`, `level=error` | Error tracking, rate alerting |
| `~/.hermes/logs/gateway.log` | No | `app=hermes`, `component=gateway` | Gateway events, platform connectivity |
| `~/.hermes/whatsapp/bridge.log` | No | `app=hermes`, `component=whatsapp` | WhatsApp bridge health |
| `~/.hermes/webui/*.log` | No | `app=hermes`, `component=webui` | WebUI bootstrap and runtime |
| `~/.hermes/cron/output/*.log` | No | `app=hermes`, `component=cron` | Cron job stdout/stderr captures |

### 3.3 Host Telemetry (via Node Exporter)

| Metric Family | Purpose |
|---------------|---------|
| `node_cpu_seconds_total` | CPU saturation — correlate with slow Hermes sessions |
| `node_memory_MemAvailable_bytes` | Memory pressure — correlate with OOM risk |
| `node_disk_io_time_seconds_total` | Disk I/O — SQLite is disk-bound under heavy write |
| `node_network_receive/transmit_bytes_total` | Network traffic — WhatsApp/HTTP gateway I/O |
| `node_load1` | System load — early warning for resource exhaustion |

---

## 4. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Host (Linux)                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Docker Compose Network                 │   │
│  │                                                          │   │
│  │  ┌──────────────┐   ┌──────────────┐  ┌─────────────┐  │   │
│  │  │   Grafana    │───│  Prometheus  │──│    Loki     │  │   │
│  │  │   (3000)     │   │   (9090)     │  │  (3100)     │  │   │
│  │  └──────────────┘   └──────┬───────┘  └──────┬──────┘  │   │
│  │                             │                  │        │   │
│  │        Pull metrics ◄───────┘                  │        │   │
│  │                             Push logs ──────────┘        │   │
│  │                                                          │   │
│  │  ┌─────────────────┐  ┌─────────────────┐              │   │
│  │  │  Node Exporter  │  │ SQLite Exporter │              │   │
│  │  │    (9100)       │  │    (9200)       │              │   │
│  │  └─────────────────┘  └────────┬────────┘              │   │
│  │                                 │                        │   │
│  │                      Bind-mount ~/.hermes/*.db           │   │
│  │                                                          │   │
│  │  ┌─────────────────┐                                      │   │
│  │  │    Promtail     │  ◄── Reads ~/.hermes/**/*.log        │   │
│  │  │    (tail)       │     ─── Pushes to Loki              │   │
│  │  └─────────────────┘                                      │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Design Decisions & Rationale

### 5.1 Why Prometheus + Loki instead of InfluxDB or TimescaleDB?
- Prometheus has the richest exporter ecosystem. Our custom SQLite exporter is trivial (~120 lines Python) using `prometheus-client`.
- Loki is purpose-built by Grafana Labs for log indexing. It is **orders of magnitude lighter** than Elasticsearch and plugs into Grafana with zero impedance mismatch.
- Both are de facto industry standards — better documentation, community support, and operator familiarity.

### 5.2 Why a custom SQLite Exporter rather than a generic SQL exporter?
- Generic SQL exporters (like `sql_exporter`) require complex configuration files per database dialect.
- Hermes has **6 distinct SQLite databases with different schemas**. A purpose-built exporter:
  - Understands Hermes schema evolution.
  - Can aggregate across DBs (e.g., total tokens = `state.db:sessions.tokens` + `ollama_usage.db:usage_calls.prompt_chars`).
  - Is trivial to extend when new DBs or columns are added.

### 5.3 Why read-only SQLite access (`?mode=ro`)
- Hermes databases may be WAL-mode locked during active write transactions.
- Opening connections with URI `file:/path/to.db?mode=ro` allows concurrent read without blocking writers.
- Prevents accidental corruption of production data.

### 5.4 Why mount `~/.hermes` as a volume rather than copy?
- Real-time observation requires live data. Copying introduces latency and ballooning disk usage.
- The exporter reloads SQL queries on each scrape interval (default 15s), ensuring near-real-time dashboards.

---

## 6. Security & Access

| Surface | Mitigation |
|---------|-----------|
| Grafana exposed on `:3000` | Bind to `127.0.0.1:3000` by default. Reverse proxy (nginx/traefik) if exposing externally. |
| SQLite DBs bind-mounted | Read-only container filesystem flag where possible. Exporter uses `mode=ro` URI. |
| Prometheus admin API | Disabled (`--web.enable-admin-api=false`). |
| Loki push auth | Internal Docker network only; no external ingress. |

---

## 7. Extensibility

| Future Enhancement | How |
|--------------------|-----|
| Alertmanager for Slack/PagerDuty | Add `alertmanager` container to compose; wire Grafana Alerting. |
| New Hermes database | Add query block to `queries.yml`; restart SQLite Exporter. |
| Tracing (OpenTelemetry) | Add `otel-collector` sidecar; instrument Hermes agent with `trace` SDK. |
| Historical archive | Prometheus remote-write to object storage (S3-compatible) for multi-month retention. |
| Multi-host deployment | Move TSDB to central VictoriaMetrics cluster; keep Promtail per node. |

---

## 8. Operational Notes

- **Retention**: Prometheus defaults to 15 days TSDB retention (sufficient for operational triage). Tune in `prometheus.yml`.
- **Rotation handling**: Promtail uses `positions.yaml` to track read offsets. Rotated files (`agent.log.1`) are automatically picked up via glob patterns.
- **Exporter restarts**: The SQLite exporter exposes a `/reload` HTTP endpoint to hot-reload `queries.yml` without container restart.
- **Backup strategy**: Grafana dashboards and Prometheus rules are provisioned as JSON/YAML files in Git. The `grafana-data` and `prometheus-data` volumes are ephemeral — dashboards survive recreation via provisioning.

---

## 9. Ports Reference

| Service | Container Port | Host Binding | Access Pattern |
|---------|---------------|-------------|----------------|
| Grafana | 3000 | `127.0.0.1:3000` | Browser UI |
| Prometheus | 9090 | `127.0.0.1:9090` | Direct query / Grafana datasource |
| Loki | 3100 | `127.0.0.1:3100` | Grafana datasource only |
| Node Exporter | 9100 | `127.0.0.1:9100` | Prometheus scrape only |
| SQLite Exporter | 9200 | `127.0.0.1:9200` | Prometheus scrape only |

---

*End of Document*
