.PHONY: up down logs eval seed clean

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api web

seed:
	docker compose exec api python -c "from db import bootstrap; bootstrap(force=True)"

eval:
	docker compose exec api python -m eval.run

clean:
	docker compose down -v
