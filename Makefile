.PHONY: all up down test burst clean status snmp-compare

all: up test

up:
	@echo "Starting Lab 5 TIG Streaming Telemetry Stack..."
	docker compose up -d --build

down:
	@echo "Stopping Lab 5 Stack..."
	docker compose down -v --remove-orphans

test:
	@echo "Running Lab 5 Telemetry Verification Suite..."
	python3 verify_telemetry_pipeline.py

burst:
	@echo "Triggering On-Demand GPU All-Reduce Microburst..."
	curl -s -X POST http://localhost:8080/burst/inject -H "Content-Type: application/json" -d '{"burst_mbps": 18500.0, "duration_sec": 1.5}' | jq .

snmp-compare:
	@echo "Running Streaming Telemetry vs SNMP Analysis..."
	python3 snmp_comparison/compare_streaming_vs_snmp.py

status:
	@echo "Checking Telemetry Agent & Health Status..."
	curl -s http://localhost:8080/health | jq .

clean: down
	@echo "Clean complete."
