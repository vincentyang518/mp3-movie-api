"""Validate tabular data before processing."""

import logging

import pandas as pd


logger = logging.getLogger(__name__)


def validate_dataframe(df, required_columns, numeric_columns):
    """Validate required columns and remove invalid numeric values."""
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error("Missing required column(s): %s", ", ".join(missing_columns))
        raise ValueError(f"Missing required column(s): {', '.join(missing_columns)}")

    result = df.copy()
    rows_before = len(result)

    for col in numeric_columns:
        if col not in result.columns:
            logger.error("Missing numeric column: %s", col)
            raise ValueError(f"Missing numeric column: {col}")

        invalid_rows = []
        for index, value in result[col].items():
            if pd.notna(value):
                try:
                    float(value)
                except (TypeError, ValueError):
                    invalid_rows.append(index)

        if invalid_rows:
            logger.warning(
                "Removed %d rows with invalid numeric values in %s",
                len(invalid_rows),
                col,
            )
            result = result.drop(index=invalid_rows)

        result[col] = pd.to_numeric(result[col])

    logger.debug("Validation: %d → %d rows", rows_before, len(result))
    return result
