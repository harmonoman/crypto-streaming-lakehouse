# Naming Conventions

## RabbitMQ

All RabbitMQ artifacts are prefixed with the domain (`crypto`) and use dot-separated namespacing.

| Artifact | Pattern | Example |
|---|---|---|
| Exchange | `{domain}.{entity}.exchange` | `crypto.trades.exchange` |
| Main queue | `{domain}.{entity}.queue` | `crypto.trades.queue` |
| Dead-letter queue | `{domain}.{entity}.dlq` | `crypto.trades.dlq` |
| Routing key (live) | `{entity}.{action}` | `trades.raw` |
| Routing key (dead) | `{entity}.dead` | `trades.dead` |

### Rules

- All exchanges and queues must be `durable: true` — no exceptions.
- Every main queue must declare both `x-dead-letter-exchange` **and** `x-dead-letter-routing-key`.
- **`x-dead-letter-routing-key` is required.** Without it, RabbitMQ dead-letters messages using the original routing key. If that key has no DLQ binding, messages are silently dropped — not routed to the DLQ.
- Routing keys use lowercase with dots as separators.
- Every main queue must set `x-max-length` (message count) and `x-max-length-bytes` (memory cap).

### Topology Diagram

```
crypto.trades.exchange (direct)
    │
    ├── [trades.raw]    ──▶  crypto.trades.queue   (TTL: 30min, max: 100k msgs / 500MB)
    │                            │ NACK / TTL / overflow
    │                            ▼
    └── [trades.dead]   ──▶  crypto.trades.dlq
```

---

## PostgreSQL

| Artifact | Pattern | Example |
|---|---|---|
| Schema | layer name | `bronze`, `silver`, `gold` |
| Table | `{layer}.{entity}` | `bronze.raw_trades` |
| Index | `idx_{table}_{column}` | `idx_raw_trades_trade_id` |
| Migration file | `{NNN}_{description}.sql` | `001_bronze_schema.sql` |

---

## dbt Models

| Layer | Pattern | Example |
|---|---|---|
| Staging (silver) | `stg_{entity}` | `stg_trades` |
| Gold | `gold_{entity}_{window}` | `gold_vwap_1min` |

---

## Docker

| Artifact | Pattern | Example |
|---|---|---|
| Container name | `crypto_{service}` | `crypto_postgres` |
| Network | `crypto_net` | — |
| Volume | `{service}_data` | `postgres_data` |