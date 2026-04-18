# Real-Time Crypto Streaming & Lakehouse Analytics

A production-style, event-driven data pipeline that ingests real-time cryptocurrency trade data and transforms it into analytical insights using a modern lakehouse architecture.

The system simulates a quantitative trading firm environment where:

- High-frequency trade data must be ingested without loss
- Analytical workloads must not impact transactional systems
- Real-time insights (VWAP, volatility, trade counts) are required

---

## Architecture

### End-to-End Data Flow

```
Coinbase WebSocket
        ↓
Python Producer (WebSocket Client)
        ↓
RabbitMQ (Message Broker / Buffer)
        ↓
Python Consumer (Worker)
        ↓
PostgreSQL (Bronze → Silver → Gold)
        ↓
dbt (Transformation Layer)
        ↓
DuckDB + DuckLake (Lakehouse OLAP)
        ↓
Metabase (BI Dashboard)
```

### Core Components

**Producer** — Python + WebSockets
Connects to the Coinbase Advanced Trade WebSocket feed, filters for a configured trading pair (default: BTC-USD), validates incoming messages via Pydantic, and publishes serialized JSON events to RabbitMQ with publisher confirms.

**RabbitMQ** — Message Broker
Buffers incoming trade events and decouples ingestion from persistence. Provides resilience during downstream outages via a durable queue and a dead-letter queue (DLQ) for poison messages.

**Consumer** — Python Worker
Subscribes to the RabbitMQ queue with manual ACK. Accumulates messages in a batch buffer and flushes to PostgreSQL using bulk inserts. Idempotent by design — duplicate `trade_id` values are silently rejected at the database level.

**PostgreSQL** — Medallion Storage (OLTP)

| Layer | Schema | Purpose |
|---|---|---|
| Bronze | `bronze` | Raw JSON ingestion — `bronze.raw_trades` |
| Silver | `silver` | Typed, deduplicated trades — `stg_trades` |
| Gold | `gold` | Aggregated metrics — VWAP, volatility, trade stats |

**dbt** — Transformation Layer
SQL-based transformations with incremental models for performance. Implements the full medallion architecture: staging models parse and cast JSONB fields; gold models compute VWAP, moving windows, and volatility indicators. Data quality enforced via built-in and custom generic tests.

**DuckDB + DuckLake** — Lakehouse (OLAP)
Analytical storage optimized for read workloads. Gold layer outputs are exported as Parquet (Snappy-compressed, partitioned by date) and registered as DuckDB views. Optional S3 backend via `boto3`.

**Metabase** — BI Dashboard
Connects directly to DuckDB. Visualizes VWAP, trade volume, buy/sell ratio, and price volatility with 60-second auto-refresh.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Ingestion | Python 3.11, WebSockets |
| Messaging | RabbitMQ 3.12 |
| Storage (OLTP) | PostgreSQL 15 |
| Transformations | dbt Core |
| Lakehouse | DuckDB + DuckLake + S3 (optional) |
| BI | Metabase |
| Orchestration | Airflow (stretch goal — Phase 7) |
| Infrastructure | Docker Compose |

---

## 🚀 Quick Start

### Option A — Dev Container (recommended)

Everything runs inside a pre-configured container. No local Python, Postgres, or RabbitMQ installation required.

**Prerequisites**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine + Compose v2
- [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

**1. Clone and configure**
```bash
git clone <repo-url>
cd crypto-streaming-pipeline
cp .env.example .env
```

Open `.env` and fill in the required values:
```
POSTGRES_PASSWORD=yourpassword
RABBITMQ_DEFAULT_PASS=yourpassword   # minimum 20 characters

# Also update the connection strings with the same password:
DATABASE_URL=postgresql://crypto_user:yourpassword@host.docker.internal:5432/crypto_pipeline
AMQP_URL=amqp://crypto_rabbit:yourpassword@host.docker.internal:5672/
```

**2. Open in Dev Container**

Open the VS Code Command Palette (`Cmd/Ctrl + Shift + P`) and run:
```
Dev Containers: Reopen in Container
```

VS Code will build the container image and install all Python dependencies automatically (~2 min on first run; instant thereafter).

**3. Start the infrastructure**
```bash
docker compose up -d
```

Verify all services are healthy before proceeding:
```bash
docker compose ps
```

**4. Run migrations and bootstrap RabbitMQ**
```bash
python infra/migrate.py
python infra/rabbitmq_setup.py
```

**5. Start the pipeline**
```bash
# Terminal 1 — producer
python -m producer.main

# Terminal 2 — consumer
python -m consumer.main
```

**6. Run dbt transformations**
```bash
cd dbt && dbt run
```

**7. Export to lakehouse**
```bash
python lakehouse/export.py
```

---

### Option B — Manual Setup (without Dev Container)

```bash
# Python 3.11+ required
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install all dependencies
uv sync --group dev

cp .env.example .env
# Edit .env — fill in passwords and update DATABASE_URL and AMQP_URL

docker compose up -d
python infra/migrate.py
python infra/rabbitmq_setup.py

# Then run producer, consumer, dbt, and lakehouse export as above
```

---

## 🌐 Service URLs

| Service | URL | Credentials |
|---|---|---|
| RabbitMQ Management UI | http://localhost:15672 | `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` from `.env` |
| Metabase | http://localhost:3000 | Configured on first launch |
| PostgreSQL | `localhost:5432` | `POSTGRES_USER` / `POSTGRES_PASSWORD` from `.env` |
| Producer metrics | http://localhost:8000/metrics | — |
| Consumer metrics | http://localhost:8001/metrics | — |

---

## 📁 Project Structure

```
crypto-streaming-pipeline/
│
├── .devcontainer/
│   ├── devcontainer.json       # VS Code Dev Container config
│   └── Dockerfile              # Dev container image
│
├── producer/                   # WebSocket → RabbitMQ
│   ├── main.py
│   ├── ws_client.py
│   ├── publisher.py
│   ├── schemas.py
│   ├── validator.py
│   ├── metrics.py
│   ├── logger.py
│   └── config.py
│
├── consumer/                   # RabbitMQ → PostgreSQL (Bronze)
│   ├── main.py
│   ├── consumer.py
│   ├── repository.py
│   ├── batch_buffer.py
│   └── metrics.py
│
├── shared/                     # Shared utilities
│   ├── logger.py
│   └── metrics.py
│
├── infra/                      # Infrastructure scripts
│   ├── migrate.py              # SQL migration runner
│   └── rabbitmq_setup.py       # Queue/exchange bootstrap
│
├── migrations/                 # Numbered SQL migration files
│   └── 001_bronze_schema.sql
│
├── dbt/                        # dbt transformation project
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── silver/
│       └── gold/
│
├── lakehouse/                  # DuckDB / DuckLake export
│   ├── exporter.py
│   ├── init_catalog.py
│   └── schema.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── benchmark/
│
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Key Metrics (Gold Layer)

Computed by dbt models in the `gold` schema and served through the DuckDB lakehouse to Metabase:

- **VWAP** — Volume Weighted Average Price per 1-minute window
- **Trade count** — number of trades per minute
- **High / Low price** — per window
- **Volatility** — standard deviation of price per window
- **Buy/sell ratio** — buy volume as a percentage of total volume per window
- **Moving averages** — rolling VWAP across configurable windows (stretch)

---

## Fault Tolerance

| Layer | Strategy |
|---|---|
| WebSocket drop | Exponential backoff reconnect (1s → 60s max, 10 attempts) |
| RabbitMQ unavailable | Producer buffers locally with in-memory retry deque |
| Consumer crash | Manual ACK — unacknowledged messages requeued automatically |
| Poison messages | NACK with `requeue=False` routes to dead-letter queue (DLQ) |
| Duplicate delivery | `ON CONFLICT (trade_id) DO NOTHING` at the DB layer |
| dbt failures | Incremental models — only failed windows need reprocessing |

---

## Reference

### Naming Conventions

| Artifact | Pattern | Example |
|---|---|---|
| Docker containers | `crypto_*` | `crypto_postgres` |
| Docker network | `crypto_net` | — |
| RabbitMQ exchange | `crypto.*.exchange` | `crypto.trades.exchange` |
| RabbitMQ queues | `crypto.*.queue` | `crypto.trades.queue` |
| Postgres schemas | layer name | `bronze`, `silver`, `gold` |
| dbt models (silver) | `stg_*` | `stg_trades` |
| dbt models (gold) | `gold_*` | `gold_vwap_1min` |

### Data Contract: Producer → Consumer

Messages published to `crypto.trades.exchange` with routing key `trades.raw`. Content-type: `application/json`.

```json
{
  "trade_id":   "string  — unique Coinbase trade ID (used for deduplication)",
  "price":      "string  — execution price in USD (cast to NUMERIC(18,8) in silver)",
  "size":       "string  — trade size in BTC (cast to NUMERIC(18,8) in silver)",
  "side":       "string  — enum: buy | sell",
  "time":       "string  — ISO 8601 UTC timestamp → traded_at in silver",
  "product_id": "string  — expected: BTC-USD (filtered by producer)"
}
```

### Environment Variables

| Variable | Service | Required | Description |
|---|---|---|---|
| `POSTGRES_USER` | Postgres | Yes | Database user |
| `POSTGRES_PASSWORD` | Postgres | **Yes — no default** | Database password |
| `POSTGRES_DB` | Postgres | Yes | Database name |
| `DATABASE_URL` | App | Yes | psycopg2 connection string |
| `RABBITMQ_DEFAULT_USER` | RabbitMQ | Yes | Admin user |
| `RABBITMQ_DEFAULT_PASS` | RabbitMQ | **Yes — no default** | Admin password (min 20 chars) |
| `AMQP_URL` | App | Yes | pika connection string |
| `RABBITMQ_EXCHANGE` | App | Yes | Exchange name |
| `RABBITMQ_QUEUE` | App | Yes | Main queue name |
| `WEBSOCKET_URL` | Producer | Yes | Coinbase WS endpoint |
| `PRODUCT_ID` | Producer | Yes | Trading pair (default: `BTC-USD`) |
| `CONSUMER_PREFETCH` | Consumer | No | RabbitMQ prefetch count (default: `100`) |
| `BATCH_SIZE` | Consumer | No | Insert batch size (default: `200`) |
| `BATCH_TIMEOUT_MS` | Consumer | No | Batch flush timeout (default: `2000`) |

See `.env.example` for the complete list with defaults.

---

## 🧪 Running Tests

```bash
# Unit tests
uv run pytest tests/unit/

# Integration tests (requires docker compose up -d)
uv run pytest tests/integration/

# Full suite
uv run pytest

# Full suite with coverage report
uv run pytest --cov=. --cov-report=html
open htmlcov/index.html

# dbt data quality tests (requires dbt run first)
cd dbt && uv run dbt test
```

> **Note:** Coverage flags are opt-in. Running `uv run pytest` without `--cov` is the default.

---

## 🔧 Dependency Management

| Task | Command |
|---|---|
| Install all deps (incl. dev) | `uv sync --group dev` |
| Add a runtime dependency | `uv add <package>` |
| Add a dev dependency | `uv add --group dev <package>` |
| Run a script | `uv run python <script>` |

Always commit `uv.lock` to version control.

---

## 🗺️ Project Roadmap

### Phase 1 — Infrastructure Setup
**Goal:** Establish local environment; verify connectivity across all services.

Tasks: `docker-compose.yml`, Postgres + RabbitMQ containers, connection validation, queue/exchange bootstrap.

**Deliverable:** All containers healthy; services communicating on `crypto_net`.

---

### Phase 2 — Producer (Streaming Ingestion)
**Goal:** Establish a stable WebSocket connection and push trade events to RabbitMQ.

Tasks: WebSocket client with exponential backoff reconnect, BTC-USD filter, Pydantic message validation, RabbitMQ publisher with delivery confirms.

**Deliverable:** Live BTC-USD trade data flowing into RabbitMQ at production rate.

---

### Phase 3 — Consumer + Bronze Layer
**Goal:** Persist raw trade events safely and efficiently.

Tasks: RabbitMQ consumer with manual ACK, `bronze.raw_trades` schema + migration, idempotent insert (`ON CONFLICT`), batch buffer with configurable flush size/timeout.

**Deliverable:** Continuous ingestion into Postgres Bronze layer with zero message loss.

---

### Phase 4 — dbt (Silver + Gold)
**Goal:** Transform raw Bronze data into analytics-ready models.

Tasks: dbt project init, staging model (`stg_trades`) with JSONB parsing + deduplication, gold aggregation models (VWAP, volatility, buy/sell stats), custom generic tests, source freshness checks.

**Deliverable:** Clean Silver layer + queryable Gold layer with passing data quality tests.

---

### Phase 5 — Lakehouse Export
**Goal:** Move analytical workload off Postgres and into a read-optimised lakehouse.

Tasks: Incremental Parquet export from Gold tables, DuckDB catalog registration, Parquet partitioning (year/month/day), optional S3 backend.

**Deliverable:** Queryable DuckDB lakehouse with <200ms VWAP query response.

---

### Phase 6 — BI Dashboard
**Goal:** Deliver business insights to non-technical stakeholders.

Tasks: Metabase → DuckDB connection, VWAP time-series chart, volume bar chart, buy/sell ratio chart, volatility chart, 60-second auto-refresh.

**Deliverable:** Live analytics dashboard accessible at http://localhost:3000.

---

### Phase 7 — Orchestration *(stretch)*
**Goal:** Fully automate the pipeline end-to-end.

Tasks: Airflow DAG scheduling dbt runs and lakehouse export, alerting on source freshness failures, backfill support.

**Deliverable:** Hands-free pipeline with scheduled transforms and automated data quality monitoring.