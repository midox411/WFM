#!/bin/bash
# Cree plusieurs bases de donnees dans la meme instance Postgres au premier demarrage.
# La liste des bases vient de la variable d'environnement POSTGRES_MULTIPLE_DATABASES
# (definie dans docker-compose.yml), ex: "wfm_app,airflow,mlflow"
set -e

if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
    echo "Creation des bases : $POSTGRES_MULTIPLE_DATABASES"
    IFS=',' read -ra DBS <<< "$POSTGRES_MULTIPLE_DATABASES"
    for db in "${DBS[@]}"; do
        db_trimmed=$(echo "$db" | xargs)
        echo "  -> $db_trimmed"
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
            SELECT 'CREATE DATABASE $db_trimmed OWNER $POSTGRES_USER'
            WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db_trimmed')\gexec
EOSQL
    done
fi
