# Real-Time Crypto Streaming & Lakehouse Analytics
## Overview

This project implements a production-style, event-driven data pipeline that ingests real-time cryptocurrency trade data and transforms it into analytical insights using a modern lakehouse architecture.

The system simulates a quantitative trading firm environment where:

- High-frequency trade data must be ingested without loss
- Analytical workloads must not impact transactional systems
- Real-time insights (VWAP, volatility, trade counts) are required

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
PostgreSQL (Bronze Layer)
        ↓
dbt (Silver + Gold Transformations)
        ↓
DuckDB + DuckLake (Lakehouse OLAP)
        ↓
Metabase (BI Dashboard)
```

## Core Components
1. Producer (Python + WebSockets)
    - Connects to Coinbase WebSocket feed
    - Filters for trading pair (e.g., BTC-USD)
    - Streams raw JSON messages to RabbitMQ
2. RabbitMQ (Message Broker)
    - Buffers incoming trade events
    - Decouples ingestion from persistence
    - Ensures resilience during downstream outages
3. Consumer (Python Worker)
    - Subscribes to RabbitMQ queue
    - Processes messages in real-time
    - Inserts raw JSON into PostgreSQL
4. PostgreSQL (Medallion Layers)
    - Bronze: Raw JSON ingestion
    - Silver: Cleaned + typed trades
    - Gold: Aggregated metrics (VWAP, windows, stats)
5. dbt (Transformation Layer)
    - SQL-based transformations
    - Data modeling with medallion architecture
    - Incremental models for performance
6. DuckDB + DuckLake (Lakehouse)
    - Analytical storage optimized for reads
    - Stores Gold layer outputs as Parquet
    - Lightweight OLAP engine
7. Metabase (Analytics)
    - Dashboarding layer
    - Connects directly to DuckDB
    - Visualizes trading metrics

## Tech Stack
```
Layer	                    Technology
-------------------------------------------------
Ingestion	                Python, WebSockets
Messaging	                RabbitMQ
Storage (OLTP)	            PostgreSQL
Transformations	            dbt
Lakehouse	                DuckDB + DuckLake + S3 (optional)
BI	                        Metabase
Orchestration (Optional)	Airflow
Infrastructure	            Docker Compose
```

## Setup Instructions
1. Clone Repo
    - `git clone <repo-url>`
    - `cd crypto-streaming-lakehouse`
2. Start Infrastructure
    - `docker-compose up -d`

    Services:
    - Postgres
    - RabbitMQ
    - (Optional) Metabase
3. Run Producer
    - `python producer/main.py`
4. Run Consumer
    - `python consumer/main.py`
5. Run dbt
    - `dbt run`
6. Run Lakehouse Export
    - `python lakehouse/export.py`

## Key Metrics (Gold Layer)
- VWAP (Volume Weighted Average Price)
- Trade count per minute
- High/Low price per window
- Moving averages
- Volatility indicators

## Fault Tolerance Strategy
- RabbitMQ buffers during outages
- Consumer retry logic
- Idempotent inserts
- dbt incremental models
--- 

## PROJECT ROADMAP
### Phase 1: Infrastructure Setup (Day 1)
- #### Goals
    - Establish local environment
    - Verify connectivity across services
- #### Tasks
    - Create docker-compose.yml
    - Spin up Postgres + RabbitMQ
    - Validate connections (CLI + UI)
    - Define queue + exchange
- #### Deliverable
    - Running containers + verified connectivity

### Phase 2: Producer (Streaming Ingestion)
- #### Goals
    - Establish stable WebSocket connection
    - Push events to RabbitMQ
- #### Tasks
    - Implement WebSocket client
    - Filter BTC-USD trades
    - Serialize JSON payloads
    - Publish messages to queue
    - Handle reconnect logic
- #### Deliverable
    - Live trade data flowing into RabbitMQ

### Phase 3: Consumer + Bronze Layer- 
- #### Goals
    - Persist raw events safely
- #### Tasks
    - Build RabbitMQ consumer
    - Design bronze_trades table
    - Insert raw JSON
    - Implement retry/backoff logic
    - Optimize batch inserts
- #### Deliverable
    - Continuous ingestion into Postgres

### Phase 4: dbt (Silver + Gold)- 
- #### Goals
    - Transform raw data into analytics-ready models
- #### Tasks
    - Initialize dbt project
    - Create staging models
    - Parse JSON fields
    - Cast data types
    - Deduplicate trades
    - Build aggregations
- #### Deliverable
    - Clean Silver + Gold layers

### Phase 5: Lakehouse Export
- #### Goals
    - Move analytics workload off Postgres
- #### Tasks
    - Extract Gold data
    - Write to DuckDB
    - Store as Parquet via DuckLake
    - Validate query performance
- #### Deliverable
    - Queryable DuckDB lakehouse

### Phase 6: BI Dashboard
- #### Goals
    - Deliver business insights
- #### Tasks
    - Connect Metabase to DuckDB
    - Build dashboards
    - Create charts for VWAP, volume, volatility
- #### Deliverable
    - Real-time analytics dashboard

### Phase 7 (Stretch): Orchestration
- #### Goals
    - Automate pipeline
- #### Tasks
    - Add Airflow DAG
    - Schedule dbt + export jobs
- #### Deliverable
    - Fully automated pipeline