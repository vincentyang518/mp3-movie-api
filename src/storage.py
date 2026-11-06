"""Persist one movie collection and query it using SQL."""
import logging
import sqlite3

import pandas as pd

from .database import get_connection, initialize_database

logger = logging.getLogger(__name__)
MOVIE_COLUMNS = ["title", "release_year", "rating", "genre"]


class MovieStorage:
    def __init__(self, db_path="data/movies.db"):
        self.db_path = db_path
        initialize_database(db_path)

    def save(self, df):
        values = df.loc[:, MOVIE_COLUMNS].astype(object)
        values = values.where(pd.notna(values), None)
        connection = get_connection(self.db_path)
        try:
            connection.execute("BEGIN")
            connection.execute("DELETE FROM movies")
            connection.executemany(
                "INSERT INTO movies (title, release_year, rating, genre) VALUES (?, ?, ?, ?)",
                values.itertuples(index=False, name=None),
            )
            connection.commit()
            logger.debug("Stored movies in SQLite: rows=%s", len(values))
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self):
        connection = get_connection(self.db_path)
        try:
            rows = connection.execute(
                "SELECT title, release_year, rating, genre FROM movies ORDER BY id"
            ).fetchall()
            return pd.DataFrame([tuple(row) for row in rows], columns=MOVIE_COLUMNS)
        finally:
            connection.close()

    @staticmethod
    def _validate_columns(columns):
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")
        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error("Unsupported column: %s", column)
                raise ValueError(f"Unsupported column: {column}")

    def select_columns(self, columns, limit=5):
        self._validate_columns(columns)
        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            rows = connection.execute(
                f"SELECT {selected_columns} FROM movies ORDER BY id LIMIT ?", (limit,)
            ).fetchall()
            logger.debug("Selected movies: columns=%s, rows=%s", columns, len(rows))
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def count_movies(self):
        connection = get_connection(self.db_path)
        try:
            return connection.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
        finally:
            connection.close()

    def query_movies(self, columns, min_rating, limit):
        self._validate_columns(columns)
        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            rows = connection.execute(
                f"SELECT {selected_columns} FROM movies WHERE rating >= ? "
                "ORDER BY rating DESC, id ASC LIMIT ?", (min_rating, limit)
            ).fetchall()
            logger.debug("Queried movies: columns=%s, rows=%s", columns, len(rows))
            return [dict(row) for row in rows]
        finally:
            connection.close()
