# MP3 Parts 1 and 2 - Verification

Verified on November 13, 2026 with Python 3.12.14. The Part 1 application and tests were retained, and Part 2 adds a dedicated FakeRedis cache and cache-aware integration tests.

## Automated checks

Command: `python -m pytest tests -v`

Result: **38 passed**. This includes all three required Part 2 tests:

- `test_movies_persist`: a new storage object reads 20 rows, all four DataFrame columns, original title order, and IDs 1 through 20 matching the API.
- `test_cache_and_processing`: separate entries for limits 100 and 1, repeated retrieval, exact cleaning report, invalidation of both limits, and refreshed 16-row data with Movie A through Movie P and IDs 1 through 16.
- `test_cache_hit_skips_database`: SQL selection and counting are replaced with test-failing functions; repeated retrieval still succeeds with the cached response.

Additional checks cover a 90-second TTL and expiration using a controlled clock, cache DEBUG logs, upload invalidation across limits, failed validation/processing/save preserving the database and cache, uncached search, and empty processed collections. Existing Part 1 checks cover SQL schema, NULL round-trips, query allowlists, upload validation, transaction rollback, processing defaults, OpenAPI, and persistence in a separate Python process.

The test run emits one dependency deprecation warning about Starlette's httpx-based TestClient. The tests use the TestClient interface specified by the assignment; the warning does not affect the results.

`python -m pip check` reports no broken requirements. `requirements.txt` records the complete verified environment using `python -m pip freeze`.

## Actual Uvicorn restart and HTTP checks

A live HTTP verification used a disposable working directory and SQLite database, starting and stopping two actual Uvicorn processes:

1. Upload the supplied fixture: 20 rows.
2. Retrieve limit 100 twice: miss, then hit, identical responses.
3. Retrieve limit 1: separate cache miss.
4. Process using `process_config.json`: zero validation removals, 20 -> 16 rows, four columns retained.
5. Retrieve limit 100: miss, 16 records, ordered titles Movie A through Movie P, IDs 1 through 16; repeating hits.
6. Stop and restart Uvicorn without uploading: the same 16 records remain in SQLite and the new process has an empty cache.
7. Upload the original sample again: the next retrieval misses and returns 20 rows.

Server logs confirmed four misses and two hits for limit 100 across this sequence, a separate limit 1 miss, and three invalidations after successful writes.

## Delivery checks

- The fixture matches the CSV provided for Part 2.
- README starts with a seven-sentence application/module explanation and includes installation, API startup, test commands, a sample processing request, and its expected response.
- `.gitignore` excludes databases, virtual environments, bytecode, and pytest caches.
- The ZIP is generated from the final Git commit and excludes local database/environment/cache files.
- The existing private GitHub repository remains the submission repository. Instructor/TA access must be managed by the repository owner.
