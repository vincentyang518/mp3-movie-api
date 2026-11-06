# Verification

- Automated tests: **30 passed** (`python -m pytest -q`).
- Assignment examples: exact upload, retrieval and search responses match.
- Replacement upload: second upload keeps 20 rows; IDs start from 1.
- Persistence: fresh Python process reads the existing SQLite collection.
- Live server: upload through HTTP, stop Uvicorn, restart Uvicorn, then retrieve 20 rows without uploading again; search result matches the assignment.
- Transaction rollback: a SQLite trigger rejects the second insert; the entire previous collection remains intact.
- Error handling: unsupported files, empty/malformed CSV, wrong columns, invalid query parameters and processing configuration.
- NULL values: missing fields round-trip as SQL NULL and JSON null.
- Original MP2: SHA-256 hashes of original project files were checked after completion; no files changed.

Test environment: Python 3.9, FastAPI 0.128.8, pandas 2.3.3, pytest 8.4.2.

The MP3 working folder contains a generated demo database with the original 20 sample rows. The ZIP excludes the generated database, virtual environments and caches. GitHub repository creation/push has not been performed.

## Second review against Part 1

| Requirement | Result |
| --- | --- |
| Separate MP3 project, preserve MP2 | PASS; original 18 project file hashes unchanged |
| Required source, fixtures, tests and pipeline structure | PASS |
| New virtual environment and requirements installation | PASS; project-local `venv/` created; `pip check` reports no broken requirements |
| Ignore generated database, environment and caches | PASS |
| pathlib database location; create missing parent directories | PASS |
| sqlite3.Row; id INTEGER PRIMARY KEY; nullable movie fields | PASS; schema checked directly with PRAGMA |
| Atomic replacement, rollback, NULL conversion, connection closing | PASS |
| SQL SELECT, COUNT, WHERE, ORDER BY, LIMIT | PASS; SQL handles filtering, sorting and counting |
| Allowlist column names; bind rating and limit parameters | PASS |
| Empty DataFrame retains all movie column names | PASS |
| Required Pydantic response models and public exports | PASS |
| Upload extension, parse, exact columns, nonempty input and column order | PASS |
| GET /movies, GET /movies/search, POST /movies/process | PASS |
| Retain MP2 processing configuration, validation and cleaning report | PASS; reused original modules and models |
| Default processing and expected processing failures | PASS; failures preserve the collection |
| DEBUG and INFO logs required by the assignment | PASS; checked with captured log records |
| /docs OpenAPI routes and response schemas | PASS; checked generated OpenAPI; manual Swagger UI walkthrough remains available |
| Assignment's exact upload/retrieval/search JSON | PASS |
| Second upload replaces rather than appends | PASS; 20 rows remain |
| Persistence through actual Uvicorn stop and restart | PASS |
| Unsupported upload returns 400, /health remains available | PASS |
| New GitHub repository, git commit and git push | NOT DONE; local code is ready but this submission step remains |

No application-code defects were found during the second review. Six additional test cases were added for default MP2 processing, configuration failures, actual schema, required logs and OpenAPI. The ZIP was regenerated from the reviewed source.
