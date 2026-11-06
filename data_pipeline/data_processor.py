"""Reusable data-cleaning functions for the MP1 pipeline."""

import logging

import pandas as pd


logger = logging.getLogger(__name__)


def remove_duplicates(df):
    """Remove duplicate rows."""
    rows_before = len(df)
    result = df.drop_duplicates()
    logger.debug(
        "remove_duplicates: %d → %d rows",
        rows_before,
        len(result),
    )
    return result


def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    if axis == "rows":
        rows_before = len(df)
        result = df.dropna(axis=0)
        logger.debug(
            "handle_missing: %d → %d rows",
            rows_before,
            len(result),
        )
        return result

    if axis == "columns":
        columns_before = len(df.columns)
        result = df.dropna(axis=1)
        logger.debug(
            "handle_missing: %d → %d columns",
            columns_before,
            len(result.columns),
        )
        return result

    logger.error("Unsupported missing-value axis: %s", axis)
    raise ValueError(f"Unsupported missing-value axis: {axis}")


def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    if method not in {"iqr", "zscore"}:
        logger.error("Unsupported outlier method: %s", method)
        raise ValueError(f"Unsupported outlier method: {method}")

    result = df
    for column in columns:
        if column not in result.columns:
            logger.warning("Column not found: %s", column)
            continue

        if not pd.api.types.is_numeric_dtype(result[column]):
            logger.warning("Column is not numeric: %s", column)
            continue

        rows_before = len(result)
        if method == "iqr":
            first_quartile = result[column].quantile(0.25)
            third_quartile = result[column].quantile(0.75)
            iqr = third_quartile - first_quartile
            lower = first_quartile - threshold * iqr
            upper = third_quartile + threshold * iqr
            result = result[
                result[column].isna() | result[column].between(lower, upper)
            ]
            logger.debug(
                "%s: method=%s, threshold=%s, lower=%s, upper=%s, removed=%d",
                column,
                method,
                threshold,
                lower,
                upper,
                rows_before - len(result),
            )
        else:
            mean = result[column].mean()
            standard_deviation = result[column].std()
            if pd.isna(standard_deviation) or standard_deviation == 0:
                outliers = pd.Series(False, index=result.index)
            else:
                zscores = (result[column] - mean) / standard_deviation
                outliers = zscores.abs() > threshold
            result = result[~outliers]
            logger.debug(
                "%s: method=%s, threshold=%s, removed=%d",
                column,
                method,
                threshold,
                rows_before - len(result),
            )

    return result


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    processing = config["processing"]
    result = df

    if processing["remove_duplicates"]:
        result = remove_duplicates(result)

    missing = processing["missing"]
    if missing["enabled"]:
        result = handle_missing(result, missing["axis"])

    outliers = processing["outliers"]
    if outliers["enabled"]:
        result = remove_outliers(
            result,
            outliers["columns"],
            outliers["method"],
            outliers["threshold"],
        )

    return result


def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    return {
        "rows_before": len(df_before),
        "rows_after": len(df_after),
        "rows_removed": len(df_before) - len(df_after),
        "columns_before": len(df_before.columns),
        "columns_after": len(df_after.columns),
        "columns_removed": len(df_before.columns) - len(df_after.columns),
    }
