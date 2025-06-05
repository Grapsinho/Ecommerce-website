.PHONY: up migrate logs down

up:
	docker-compose up --build -d

migrate:
	docker-compose exec web python manage.py migrate

logs:
	docker-compose logs -f

down:
	docker-compose down -v
