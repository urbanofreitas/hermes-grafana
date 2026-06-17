# Hermes Grafana Stack — Setup Guide

## Current Status

**Architecture is fully scaffolded.** All containers, configs, the custom SQLite exporter, and dashboards are written and ready. However, the Docker daemon on this host is currently inaccessible due to a **permission blocker** (see Blocker section below).

---

## Step 1: Fix Docker Socket Permissions (One-Time)

### Problem
- The Docker socket `/var/run/docker.sock` is owned by `root:root` with mode `660`.
- User `urbano` is **not** in the `docker` group.
- Snap Docker is the active installation.
- The `sudoers.d/apt-updates` file has syntax errors that block password-less `sudo`.

### Solution

#### Option A: Use sudo (requires typing password once)
Open a terminal and run:

```bash
sudo groupadd -f docker
sudo usermod -aG docker urbano
sudo chmod 666 /var/run/docker.sock
```

Then **logout and login again** (or reboot) so the group membership takes effect.

Verify with:
```bash
groups   # should now list "docker"
docker ps   # should work without sudo
```

#### Option B: Switch Docker context to Rancher Desktop (if RD is running)
If Rancher Desktop is active, it may expose its own Docker endpoint:

```bash
# Check if Rancher Desktop provides a socket
ls ~/.rd/docker.sock 2>/dev/null || echo "No RD socket"

# If it exists:
export DOCKER_HOST=unix://$HOME/.rd/docker.sock
docker ps
```

---

## Step 2: Start the Observability Stack

Once Docker is accessible:

```bash
cd ~/MyCode/hermes-grafana
docker compose up -d --build
```

This will:
1. Build the custom **SQLite Exporter** image (Python/FastAPI).
2. Pull and start **Prometheus**, **Grafana**, **Loki**, **Node Exporter**, and **Promtail**.
3. Auto-provision datasources (Prometheus + Loki) into Grafana.
4. Auto-import the three pre-built dashboards.

### Verify all containers are running

```bash
docker compose ps
```

Expected output (6 containers):
```
NAME                   STATUS
hermes-grafana         Up
hermes-loki            Up
hermes-node-exporter   Up
hermes-prometheus      Up
hermes-promtail        Up
hermes-sqlite-exporter Up
```

---

## Step 3: Access the Dashboards

### Grafana UI
- **URL**: http://localhost:3000
- **Username**: `admin`
- **Password**: `hermes-grafana-2026`

### Prometheus (optional)
- **URL**: http://localhost:9090
- Use for ad-hoc PromQL queries.

### SQLite Exporter Health Check
```bash
curl http://localhost:9200/health
```

### Reload Queries Without Restart
If you edit `sqlite-exporter/queries.yml`, hot-reload without restarting:
```bash
curl http://localhost:9200/reload
```

---

## Step 4: Confirm Data Flow

### Check Prometheus Targets
Open http://localhost:9090/targets — all three should be green:
- `prometheus` (self)
- `node-exporter`
- `sqlite-exporter`

### Check Loki Logs in Grafana
In Grafana, go to **Explore → Loki datasource** and run:
```
{app="hermes"}
```
You should see logs streaming from:
- `agent.log`
- `errors.log`
- `gateway.log`
- `whatsapp/bridge.log`
- `webui/*.log`
- `cron/output/*.log`

### Check SQLite Metrics in Grafana
Open **Dashboards → Hermes Overview**.
You should see panels populated with data from:
- `state.db` (sessions, messages)
- `metrics.db` (executions, tool calls, daily stats)
- `ollama_usage.db` (calls, latency, budget)
- `cron_logs.db` (runs, statuses, exit codes)
- `inbox_captures.db` (processing, categories)
- `kanban.db` (tasks, priorities, completions)

---

## Troubleshooting

### "permission denied while trying to connect to the Docker daemon"
→ Docker socket ownership is wrong. Re-run Step 1.

### "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"
→ Docker daemon isn't running or snap Docker socket path differs. Check:
```bash
sudo systemctl status docker
sudo snap restart docker
```

### SQLite Exporter returns empty metrics
→ Ensure `~/.hermes` contains the expected `.db` files:
```bash
ls ~/.hermes/*.db ~/.hermes/db/*.db ~/.hermes/logs/*.db ~/.hermes/kanban.db
```
Check exporter logs:
```bash
docker compose logs sqlite-exporter
```

### No logs in Loki
→ Check Promtail is reading files:
```bash
docker compose logs promtail
```
Ensure the Hermes home directory is mounted read-only and accessible.

### Dashboards not appearing
→ They provision on first boot. Wait 10–20 seconds after Grafana starts, then refresh. Check:
```bash
docker compose logs grafana | grep "provision"
```

---

## Project Layout

```
~/MyCode/hermes-grafana/
├── ARCHITECTURE.md          # Full design document
├── CHANGELOG.md             # Session history and status
├── README.md                # High-level overview
├── SETUP.md                 # This file
├── docker-compose.yml       # 6-service orchestration
├── .env                     # HERMES_HOME path
├── dashboards/              # Pre-built Grafana dashboards (JSON)
│   ├── hermes-overview.json
│   ├── system-resources.json
│   └── log-explorer.json
├── grafana/provisioning/    # Auto-provision datasources + dashboards
│   └── datasources/
│       └── datasources.yml
├── loki/
│   └── loki-config.yml
├── prometheus/
│   ├── prometheus.yml
│   └── rules/               # Placeholder for alert rules
├── promtail/
│   └── promtail-config.yml
└── sqlite-exporter/         # Custom Python/FastAPI bridge
    ├── Dockerfile
    ├── main.py
    ├── queries.yml          # SQL → Prometheus metric mappings
    └── requirements.txt
```

---

## Next Steps (Post-Startup)

1. **Bookmark** http://localhost:3000 in your browser.
2. **Change the default admin password** in Grafana → Administration → Users.
3. **Add Alertmanager** if you want Slack/email alerts on cron failures or cost spikes.
4. **Extend dashboards** by adding panels in Grafana UI, then export the JSON back to `dashboards/` so it survives recreation.
5. **Commit the repo** to GitHub to preserve dashboards and configs:
   ```bash
   cd ~/MyCode/hermes-grafana
   git init
   git add .
   git commit -m "Initial Hermes Grafana observability stack"
   ```

---

*Generated 2026-06-17*
