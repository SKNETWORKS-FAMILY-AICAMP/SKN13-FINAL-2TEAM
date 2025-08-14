.PHONY: help build run stop clean logs shell test

# Default target
help:
	@echo "Available commands:"
	@echo "  build     - Build Docker image"
	@echo "  run       - Run container with docker-compose"
	@echo "  stop      - Stop containers"
	@echo "  clean     - Remove containers and images"
	@echo "  logs      - Show container logs"
	@echo "  shell     - Open shell in running container"
	@echo "  test      - Test the application"

# Build Docker image
build:
	docker build -t fastapi-app .

# Build production image
build-prod:
	docker build -f Dockerfile.prod -t fastapi-app:prod .

# Run with docker-compose
run:
	docker-compose up -d

# Run in foreground
run-fg:
	docker-compose up

# Stop containers
stop:
	docker-compose down

# Clean up
clean:
	docker-compose down --rmi all --volumes --remove-orphans
	docker system prune -f

# Show logs
logs:
	docker-compose logs -f

# Open shell in container
shell:
	docker-compose exec fastapi-app /bin/bash

# Test the application
test:
	curl -f http://localhost:8000/health || echo "Application not responding"

# Build and run in one command
dev: build run
	@echo "Application is starting..."
	@echo "Check logs with: make logs"
	@echo "Stop with: make stop"
