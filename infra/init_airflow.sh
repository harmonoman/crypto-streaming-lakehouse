#!/bin/bash
# infra/init_airflow.sh
#
# One-time Airflow initialization script.
# Run this AFTER docker compose up -d to initialize the metadata database
# and create the admin user.
#
# Why not embed this in docker-compose?
#   docker-compose is for service lifecycle, not one-time setup operations.
#   Keeping initialization explicit makes it clear what's happening and
#   easier to debug when something goes wrong.
#
# Why use environment variables for the password?
#   Passwords must never be hardcoded. The AIRFLOW_ADMIN_PASSWORD variable
#   is set in your .env file. Falls back to "admin" for local development
#   only — always set a real password in production.
#
# Usage:
#   ./infra/init_airflow.sh

set -e

echo "Initializing Airflow metadata database..."
docker exec crypto_airflow airflow db migrate

echo "Creating Airflow admin user..."
docker exec crypto_airflow airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@crypto-pipeline.local \
  --password "${AIRFLOW_ADMIN_PASSWORD:-admin}" || \
  echo "  Admin user already exists — skipping creation."

echo ""
echo "Airflow initialization complete."
echo "Access the UI at: http://localhost:8080"
echo "Username: admin"
