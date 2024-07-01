install-dependencies:
	@pip install -r ./deployment/hls-stream/requirements.txt

run-dev:
	@python src/hls-stream/api.py --watch

run:
	docker compose -f ./deployment/docker-compose.yml up -d --pull never


build:
	@docker compose -f ./deployment/docker-compose.yml build

restart:
	@docker compose -f ./deployment/docker-compose.yml restart

down:
	@docker compose -f ./deployment/docker-compose.yml down

delete:
	@docker compose -f ./deployment/docker-compose.yml down --remove-orphans -v
