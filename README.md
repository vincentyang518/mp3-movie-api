# MP3 Movie API - Parts 1 and 2

This FastAPI application uploads, stores, searches, and cleans a collection of movies. The `main.py` module defines the HTTP endpoints, while `src/models.py` defines the request and response models. Uploaded CSV files must contain exactly `title`, `release_year`, `rating`, and `genre`, and each successful upload replaces the current collection. The `src/database.py` and `src/storage.py` modules persist movies in SQLite and use SQL for retrieval, filtering, sorting, and counting, so data survives server restarts. The `data_pipeline` modules validate numeric fields and apply configurable duplicate removal, missing-value handling, and outlier removal before saving the processed collection. The `src/cache.py` module uses a dedicated FakeRedis instance to cache each complete `GET /movies` response by its limit for 90 seconds, while `GET /movies/search` always queries SQLite. Successful uploads and processing invalidate every cached limit immediately after saving, failed writes preserve the cache, and tests verify persistence, invalidation, and database-free cache hits.

## Install and run

Use Python 3.12 (the verified version) and run these commands from the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs for Swagger UI. SQLite is created automatically at `data/movies.db`; run from the same repository root when restarting. FakeRedis is an in-process cache and requires no Redis server; it starts empty after a restart. Generated databases, virtual environments, and Python caches are ignored by Git.

## Tests

```bash
python -m pytest tests -v
```

Tests use isolated temporary SQLite databases and a fresh cache per test. See `VERIFICATION.md` for the checks performed.

## Sample upload and processing request

Start with the provided 20-row fixture:

```bash
curl -X POST http://127.0.0.1:8000/upload \
  -F 'file=@fixtures/sample_movies.csv;type=text/csv'
curl 'http://127.0.0.1:8000/movies?limit=100'
curl 'http://127.0.0.1:8000/movies?limit=100'
curl 'http://127.0.0.1:8000/movies?limit=1'
```

The first retrieval for each limit misses the cache; repeating limit 100 hits it. To process, use `POST /movies/process` with the following JSON (also saved in `process_config.json`):

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {"enabled": true, "axis": "rows"},
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```

```bash
curl -X POST http://127.0.0.1:8000/movies/process \
  -H 'Content-Type: application/json' \
  --data-binary @process_config.json
```

Expected processing response:

```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```

The next `GET /movies?limit=100` misses and returns `total_rows: 16` with Movie A through Movie P and IDs 1 through 16, in order. Repeating it hits the cache. Restarting the server preserves those 16 SQLite rows; uploading the sample again replaces them with 20 rows and clears all cached limits. Passing `{}` to processing uses the existing Part 1 defaults and produces 18 rows because outlier removal is disabled by default.

## Repository

https://github.com/vincentyang518/mp3-movie-api

The repository is private; the instructor or TA needs access to view it.
