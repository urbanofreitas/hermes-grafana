# Hermes Observability Stack

Full observability for [Hermes Agent](https://github.com/NousResearch/Hermes-Trainer) using Grafana, Prometheus, Loki, and a custom SQLite metrics exporter.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full design document.

## Quick Start

1. **Fix Docker permissions** (one-time):
   ```bash
   # Run as root or with sudo
   sudo groupadd -f docker
   sudo usermod -aG docker $USER
   sudo chmod 666 /var/run/docker.sock   # or: sudo chown root:docker /var/run/docker.sock
   # Then logout/login or run: newgrp docker
   ```

2. **Launch the stack**:
   ```bash
   cd ~/MyCode/hermes-grafana
   docker compose up -d
   ```

3. **Access Grafana**:
   - URL: http://localhost:3000
   - Login: `admin` / `hermes-grafana-2026`
   - Datasources: Prometheus (default) and Loki are pre-provisioned

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Grafana | 3000 | Dashboards |
| Prometheus | 9090 | Metrics TSDB |
| Loki | 3100 | Log aggregation |
| Node Exporter | 9100 | Host telemetry |
| SQLite Exporter | 9200 | Hermes DB metrics bridge |

## SQLite Exporter

Custom Python FastAPI service that translates Hermes SQLite queries into Prometheus metrics.

- Queries defined in: `sqlite-exporter/queries.yml`
- Hot-reload endpoint: `curl http://localhost:9200/reload`
- Health check: `curl http://localhost:9200/health`

## Dashboards

Pre-provisioned JSON dashboards are in `dashboards/`. Auto-imported on first Grafana startup.

## Logs

Promtail ships the following Hermes logs to Loki:
- `~/.hermes/logs/agent.log*`
- `~/.hermes/logs/errors.log*`
- `~/.hermes/logs/gateway.log*`
- `~/.hermes/whatsapp/bridge.log`
- `~/.hermes/webui/*.log`
- `~/.hermes/cron/output/*.log`

Search them in Grafana Explore → Loki datasource.

## License

MIT

---

## Related Projects

- **Hermes AI** — The main Hermes Agent runtime that this stack observes.  
  Repository: https://github.com/urbanofreitas/Hermes_AI  
  Cross-reference guide: `guides/hermes-grafana-observability.md`
