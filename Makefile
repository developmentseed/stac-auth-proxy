# STAC Auth Proxy Makefile
# Easily manage different backend configurations

.PHONY: help up-pgstac up-opensearch up-all down clean logs ps

# Default backend
BACKEND ?= pgstac

help:
	@echo "STAC Auth Proxy - Backend Management"
	@echo ""
	@echo "Available commands:"
	@echo "  make up-pgstac      - Start with PostgreSQL/pgSTAC backend"
	@echo "  make up-opensearch  - Start with OpenSearch backend"
	@echo "  make up-all         - Start both backends (ports will conflict)"
	@echo "  make down           - Stop all services"
	@echo "  make clean          - Stop services and remove volumes"
	@echo "  make logs           - View logs (use BACKEND=pgstac|opensearch)"
	@echo "  make ps             - List running services"
	@echo ""
	@echo "Environment variables:"
	@echo "  STAC_PORT          - STAC API port (default: 8001)"
	@echo "  UPSTREAM_URL       - Proxy upstream URL (auto-configured)"

# Start with pgSTAC backend
up-pgstac:
	@echo "Starting with pgSTAC backend..."
	@export COMPOSE_PROFILES=pgstac && \
	export UPSTREAM_URL=http://stac:8001 && \
	docker-compose up -d
	@echo ""
	@echo "Services started:"
	@echo "  STAC API (pgSTAC):    http://localhost:8001"
	@echo "  Auth Proxy:           http://localhost:8000"
	@echo "  Mock OIDC:            http://localhost:8888"
	@echo "  PostgreSQL:           localhost:5439"

# Start with OpenSearch backend
up-opensearch:
	@echo "Starting with OpenSearch backend..."
	@export COMPOSE_PROFILES=opensearch && \
	export UPSTREAM_URL=http://stac-opensearch:8001 && \
	docker-compose up -d
	@echo ""
	@echo "Services started:"
	@echo "  STAC API (OpenSearch): http://localhost:8001"
	@echo "  Auth Proxy:            http://localhost:8000"
	@echo "  Mock OIDC:             http://localhost:8888"
	@echo "  OpenSearch:            http://localhost:9200"

# Start all services (for development/testing)
up-all:
	@echo "Starting all services (both backends)..."
	@echo "WARNING: Both STAC APIs will try to use port 8001"
	@export COMPOSE_PROFILES=all && \
	docker-compose up -d

# Stop all services
down:
	docker-compose --profile pgstac --profile opensearch down

# Clean up (stop and remove volumes)
clean:
	docker-compose --profile pgstac --profile opensearch down -v
	rm -rf .pgdata

# View logs
logs:
	@if [ "$(BACKEND)" = "opensearch" ]; then \
		docker-compose --profile opensearch logs -f stac-os database-os proxy; \
	else \
		docker-compose --profile pgstac logs -f stac-pg database-pg proxy; \
	fi

# List running services
ps:
	docker-compose --profile pgstac --profile opensearch ps

# Test endpoints
test-stac:
	@echo "Testing STAC API..."
	@curl -s http://localhost:8001 | jq .
	@echo ""
	@echo "Testing Auth Proxy..."
	@curl -s http://localhost:8000 | jq .

# Initialize pgSTAC database
init-pgstac:
	@echo "Initializing pgSTAC database..."
	docker-compose --profile pgstac exec database-pg psql -U username -d postgis -c "CREATE EXTENSION IF NOT EXISTS postgis;"
	docker-compose --profile pgstac exec database-pg psql -U username -d postgis -c "CREATE EXTENSION IF NOT EXISTS btree_gist;"

# Initialize OpenSearch index
init-opensearch:
	@echo "Initializing OpenSearch indices..."
	@echo "This would typically be done by the STAC API on first run"