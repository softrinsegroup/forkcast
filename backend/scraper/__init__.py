"""
Standalone recipe scraper CLI.

Lives inside the backend project so it can import the shared Pydantic models,
but always runs as its own process (`python -m scraper <root-url>`) and talks
to the backend only via POST /recipes/ingest. See __main__.py.
"""
