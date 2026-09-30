# Makefile - png6-data-cleaning (Backend.md authority).
COMPOSE := docker compose -f deploy/docker-compose.yml

.PHONY: build up down logs migrate test

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

migrate:
	$(COMPOSE) run --rm api alembic upgrade head

test:
	$(COMPOSE) run --rm api pytest -q
