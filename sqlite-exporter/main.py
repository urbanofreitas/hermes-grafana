import os
import sqlite3
import time
import yaml
from contextlib import closing
from prometheus_client import Gauge, Counter, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
import uvicorn

DB_ROOT = os.environ.get("HERMES_DB_ROOT", "/hermes")
EXPORTER_PORT = int(os.environ.get("EXPORTER_PORT", "9200"))
METRICS_PREFIX = "hermes"

app = FastAPI()

# ── Load query definitions ────────────────────────────────────
def load_queries():
    queries_path = os.path.join(os.path.dirname(__file__), "queries.yml")
    with open(queries_path, "r") as f:
        return yaml.safe_load(f).get("queries", [])

QUERIES = load_queries()

# ── Registry of Prometheus collectors ─────────────────────────
COLLECTORS = {}

def get_collector(metric_name, metric_type, description, labels):
    key = (metric_name, tuple(labels))
    if key not in COLLECTORS:
        cls = {"gauge": Gauge, "counter": Counter, "histogram": Histogram, "summary": Summary}[metric_type]
        if cls == Counter:
            COLLECTORS[key] = cls(f"{METRICS_PREFIX}_{metric_name}", description, labels)
        elif cls == Gauge:
            COLLECTORS[key] = cls(f"{METRICS_PREFIX}_{metric_name}", description, labels)
        elif cls == Histogram:
            COLLECTORS[key] = cls(f"{METRICS_PREFIX}_{metric_name}", description, labels, buckets=[0.01,0.1,0.5,1,2,5,10,30,60,120,300])
        elif cls == Summary:
            COLLECTORS[key] = cls(f"{METRICS_PREFIX}_{metric_name}", description, labels)
    return COLLECTORS[key]

# ── Query execution ──────────────────────────────────────────
def exec_sql(db_path, sql, params=()):
    uri = f"file:{db_path}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5.0) as conn:
            conn.row_factory = sqlite3.Row
            with closing(conn.execute(sql, params)) as cur:
                return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        return [{"error": str(exc)}]

# ── Metric refresh ───────────────────────────────────────────
def refresh_metrics():
    for q in QUERIES:
        db_rel = q.get("db")
        sql = q.get("sql")
        metric_name = q.get("metric")
        metric_type = q.get("type", "gauge")
        description = q.get("description", "")
        label_keys = q.get("labels", [])
        value_key = q.get("value", "value")
        db_path = os.path.join(DB_ROOT, db_rel) if db_rel else os.path.join(DB_ROOT, q.get("db_path", ""))

        if not os.path.exists(db_path):
            continue

        rows = exec_sql(db_path, sql)
        collector = get_collector(metric_name, metric_type, description, label_keys)

        for row in rows:
            if "error" in row:
                continue
            label_vals = {k: str(row.get(k, "unknown")) for k in label_keys}
            val = row.get(value_key, 0)
            if val is None:
                val = 0

            try:
                if metric_type == "gauge":
                    collector.labels(**label_vals).set(float(val))
                elif metric_type == "counter":
                    # Counters need careful handling; gauge is safer for SQL snapshots
                    pass
                elif metric_type == "histogram":
                    collector.labels(**label_vals).observe(float(val))
                elif metric_type == "summary":
                    collector.labels(**label_vals).observe(float(val))
            except Exception:
                pass

@app.get("/")
async def root():
    return {"service": "hermes-sqlite-exporter", "prefix": METRICS_PREFIX}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/reload")
async def reload():
    global QUERIES
    QUERIES = load_queries()
    COLLECTORS.clear()
    return {"status": "reloaded", "queries_loaded": len(QUERIES)}

@app.get("/metrics")
async def metrics():
    refresh_metrics()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=EXPORTER_PORT, log_level="warning")
