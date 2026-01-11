.PHONY: help infra streaming batch all up down logs clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

infra: ## Start infrastructure services (postgres, kafka, minio, ml-api, adminer, kafka-ui)
	docker-compose up -d postgres flyway adminer minio minio-init ml-api kafka kafka-init kafka-ui

streaming: ## Start streaming pipeline (producer-1, producer-2, consumer)
	docker-compose --profile streaming up -d

batch: ## Start batch pipeline
	docker-compose --profile batch up

all: ## Start all services (infra + streaming + batch)
	docker-compose --profile all up -d

up: infra ## Alias for 'infra' - start infrastructure only
	@echo "Infrastructure started!"

down: ## Stop all services
	docker-compose down

logs-all: ## Follow all pipeline services logs (streaming + batch)
	docker-compose logs -f streaming-producer-1 streaming-producer-2 streaming-consumer batch

logs-streaming: ## Follow streaming services logs
	docker-compose logs -f streaming-producer-1 streaming-producer-2 streaming-consumer

logs-batch: ## Follow batch service logs
	docker-compose logs -f batch

logs-consumer: ## Follow consumer logs
	docker-compose logs -f streaming-consumer

logs-producers: ## Follow producer logs
	docker-compose logs -f streaming-producer-1 streaming-producer-2

logs-ml-api: ## Follow ML API logs
	docker-compose logs -f ml-api

logs: ## Follow all logs
	docker-compose logs -f

clean: ## Stop and remove all containers, networks, volumes
	docker-compose down -v
	docker system prune -f

rebuild-streaming: ## Rebuild and restart streaming services
	docker-compose --profile streaming up -d --build

rebuild-batch: ## Rebuild and restart batch service
	docker-compose --profile batch up -d --build

rebuild-all: ## Rebuild and restart all pipeline services (streaming + batch)
	docker-compose --profile all up -d --build

restart-consumer: ## Restart consumer
	docker-compose restart streaming-consumer

restart-producers: ## Restart producers
	docker-compose restart streaming-producer-1 streaming-producer-2
