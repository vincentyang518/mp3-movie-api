import logging

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src import (
    MovieCache, MovieStorage, MovieUploadInfo, MovieDataResponse,
    MovieProcessingReport, ProcessConfig, HealthResponse,
)
from src.middleware import log_requests
from src.storage import MOVIE_COLUMNS
from src.utils import setup_logging
from io import BytesIO

setup_logging(verbose=True)
logger = logging.getLogger(__name__)
app = FastAPI(title="MP3 Movie API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()
cache = MovieCache()


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", version="1.0.0")


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")
    content = await file.read()
    try:
        df = pd.read_csv(BytesIO(content))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Unable to parse CSV file") from exc
    if len(df.columns) != len(MOVIE_COLUMNS) or set(df.columns) != set(MOVIE_COLUMNS):
        raise HTTPException(status_code=400, detail=f"Require exactly these columns: {MOVIE_COLUMNS}")
    if df.empty:
        raise HTTPException(status_code=400, detail="CSV must contain at least one data row")
    df = df.loc[:, MOVIE_COLUMNS]
    storage.save(df)
    cache.invalidate()
    logger.info("Uploaded movies: filename=%s, rows=%s", filename, len(df))
    return MovieUploadInfo(filename=filename, rows=len(df), columns=len(MOVIE_COLUMNS),
                           column_names=MOVIE_COLUMNS)


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    cached = cache.get(limit)
    if cached is not None:
        logger.info("Movie cache hit: limit=%s", limit)
        return cached
    data = storage.select_columns(MOVIE_COLUMNS, limit)
    total = storage.count_movies()
    response = {"data": data, "total_rows": total}
    cache.set(limit, response)
    logger.info("Retrieved movies: returned_rows=%s, total_rows=%s", len(data), total)
    return response


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1),
):
    try:
        data = storage.query_movies(columns, min_rating, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("Queried movies: columns=%s, min_rating=%s, returned_rows=%s",
                columns, min_rating, len(data))
    return data


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    df = storage.get()
    if df.empty:
        raise HTTPException(status_code=400, detail="No movies to process")
    settings = config.model_dump()
    validation = settings["validation"]
    try:
        validated = validate_dataframe(df, validation["required_columns"],
                                       validation["numeric_columns"])
        validation_removed = len(df) - len(validated)
        before = validated.copy(deep=True)
        processed = process_data(validated, settings)
        if list(processed.columns) != MOVIE_COLUMNS:
            raise ValueError("Processing must preserve all four movie columns; use missing.axis='rows'")
        report = create_cleaning_report(before, processed)
    except ValueError as exc:
        logger.error("Movie processing failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage.save(processed)
    cache.invalidate()
    logger.info("Processed movies: validation_rows_removed=%s, cleaning_report=%s",
                validation_removed, report)
    return {"validation_rows_removed": validation_removed, "cleaning_report": report}
