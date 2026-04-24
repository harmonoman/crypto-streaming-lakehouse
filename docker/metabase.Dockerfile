# Uses eclipse-temurin (Debian/Ubuntu JRE) instead of Alpine-based metabase image
# because the DuckDB driver requires glibc which Alpine does not provide.
FROM eclipse-temurin:21-jre

ENV MB_PLUGINS_DIR=/plugins
ENV MB_DB_FILE=/metabase-data/metabase.db

RUN mkdir -p /plugins /app

# Metabase JAR
ADD https://downloads.metabase.com/v0.49.6/metabase.jar /app/metabase.jar

# DuckDB driver — version matches DuckDB 1.5.2 in the project
ADD https://github.com/motherduckdb/metabase_duckdb_driver/releases/download/1.5.2.0/duckdb.metabase-driver.jar /plugins/

RUN chmod 744 /plugins/duckdb.metabase-driver.jar

EXPOSE 3000
CMD ["java", "-jar", "/app/metabase.jar"]
