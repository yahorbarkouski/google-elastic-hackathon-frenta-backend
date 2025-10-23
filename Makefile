.PHONY: docker-up docker-down install test test-comprehensive run

docker-up:
	docker-compose up -d
	@echo "Waiting for Elasticsearch to be ready..."
	@sleep 10

docker-down:
	docker-compose down

install:
	uv pip install -e .

test: docker-up
	pytest tests/ -v -s

test-comprehensive: docker-up
	pytest tests/test_comprehensive_search.py::test_indexing_comprehensive_apartment -v -s
	pytest tests/test_comprehensive_search.py::test_search_queries_comprehensive -v -s

test-granular:
	pytest tests/test_claim_extraction_granular.py -v -s

test-embeddings:
	pytest tests/test_embedding_quality.py -v -s

test-all: docker-up
	pytest tests/ -v -s

run:
	python -m app.main

reindex-metadata:
	python scripts/reindex_image_metadata.py

