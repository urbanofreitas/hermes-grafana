# Hermes Grafana Stack — Changelog

## [Unreleased] — 2026-06-17

### Project Initialization
**Session scope**: Full scaffold of the Hermes observability stack. Docker permission blocker encountered — stack ready to start once Docker access is resolved.

---

### Added

#### Architecture & Documentation
- **ARCHITECTURE.md** — Complete design document covering:
  - Stack rationale (Prometheus + Loki + Grafana)
  - All 6 SQLite database schemas mapped to metrics
  - Log file sources and labels
  - Host telemetry correlation strategy
  - Security, extensibility, and operational notes
- **README.md** — Quick-start overview with ports, services, and operational pointers
- **SETUP.md** — Step-by-step manual setup guide including Docker permission fix, stack startup, verification, and troubleshooting
- **CHANGELOG.md** — This file

#### Orchestration
- **docker-compose.yml** — Defines all 6 services:
  - `hermes-grafana` (Grafana OSS 12.0.1)
  - `hermes-prometheus` (Prometheus v3.4.0, 30d retention)
  - `hermes-loki` (Loki 3.5.0, filesystem-backed, 168h log retention)
  - `hermes-promtail` (Promtail 3.5.0)
  - `hermes-node-exporter` (Node Exporter v1.9.1)
  - `hermes-sqlite-exporter` (custom FastAPI image, built from source)
- **.env** — Sets `HERMES_HOME=/home/urbano/.hermes`

#### Configuration Files
- **prometheus/prometheus.yml** — Scrapes self, node-exporter (`:9100`), sqlite-exporter (`:9200`) every 15s
- **loki/loki-config.yml** — Single-tenant filesystem storage, TSDB index schema v13, 168h retention
- **promtail/promtail-config.yml** — Ships all Hermes logs with structured labels:
  - `component=agent` → `logs/agent.log*`
  - `component=errors` → `logs/errors.log*` (with `level=error`)
  - `component=gateway` → `logs/gateway.log*`
  - `component=whatsapp` → `whatsapp/bridge.log`
  - `component=webui` → `webui/*.log`
  - `component=cron` → `cron/output/*.log`
  - `component=misc` → all other `**/*.log`
- **grafana/provisioning/datasources/datasources.yml** — Auto-provisions Prometheus (default) and Loki datasources

#### Custom SQLite Exporter
- **sqlite-exporter/Dockerfile** — Python 3.13 slim base, FastAPI + prometheus-client
- **sqlite-exporter/requirements.txt** — `fastapi`, `uvicorn[standard]`, `prometheus-client`, `pyyaml`
- **sqlite-exporter/main.py** — FastAPI app with:
  - Hot-reloadable `queries.yml` parser
  - Read-only SQLite access via `file:...?mode=ro` URIs
  - Dynamic Gauge/Histogram/Summary collector registry
  - Endpoints: `/`, `/health`, `/reload`, `/metrics`
- **sqlite-exporter/queries.yml** — 27 query definitions mapping Hermes DBs to Prometheus metrics:
  - `state.db`: sessions hourly, by model, avg tokens, cost, end-reason distribution, messages by role/hour
  - `metrics.db`: daily executions, tokens, cost, avg duration, success rate, tool calls, daily rollups
  - `ollama_usage.db`: calls by hour/model, avg latency, estimated cost, budget remaining
  - `cron_logs.db`: runs by status/job, exit code distribution
  - `inbox_captures.db`: status/category counts, avg processing time
  - `kanban.db`: tasks by status/priority, completions (7d), avg completion time

#### Pre-Built Dashboards (JSON)
- **dashboards/hermes-overview.json** — Panels: total sessions, sessions by model pie chart, hourly rate, daily cost, daily tokens, cron success rate, kanban tasks by status, tasks completed (7d), avg completion time
- **dashboards/system-resources.json** — Panels: CPU utilization, memory used/available, disk utilization (/ and /home), network RX/TX throughput
- **dashboards/log-explorer.json** — Panels: Loki log views filtered by component (errors, agent, gateway, whatsapp, cron)

---

### Blockers
- **Docker daemon permission denied** — `/var/run/docker.sock` is `root:root 660`; user `urbano` is not in the `docker` group.
- **Sudoers syntax error** — `/etc/sudoers.d/apt-updates` has malformed lines that prevent password-less `sudo` execution.
- **Resolution**: Manual intervention required (see SETUP.md Step 1). Once fixed, `docker compose up -d --build` will start the entire stack.

---

### Remaining Tasks (Post-Fix)
- [ ] Run `docker compose up -d --build`
- [ ] Verify all 6 containers are healthy (`docker compose ps`)
- [ ] Confirm Prometheus targets green (http://localhost:9090/targets)
- [ ] Confirm Loki logs flowing (Grafana Explore → Loki)
- [ ] Verify SQLite metrics populated (Grafana → Hermes Overview dashboard)
- [ ] Change default Grafana admin password
- [ ] Optional: Git-init and push the repo
- [ ] Optional: Add Alertmanager for cron/cost alerting

---

*Status as of 2026-06-17 — all code written, deployment pending Docker permission fix.*
