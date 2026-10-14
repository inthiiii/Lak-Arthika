"""DuckDB analytical views over the historical Parquet lake."""

from datetime import date
from pathlib import Path
from typing import Any

import duckdb


def _sql_path(path: Path) -> str:
    """Escape a trusted local path for a DuckDB string literal."""

    return str(path.resolve()).replace("'", "''")


def refresh_analytics(
    *,
    database_path: Path,
    partitioned_root: Path,
    markets_path: Path,
) -> None:
    """Create replaceable analytical views over Parquet and market references."""

    partitions = list(partitioned_root.glob("year=*/month=*/prices.parquet"))
    if not partitions:
        raise FileNotFoundError(f"No price partitions found below {partitioned_root}")
    if not markets_path.exists():
        raise FileNotFoundError(markets_path)

    database_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_glob = _sql_path(partitioned_root / "year=*" / "month=*" / "prices.parquet")
    market_csv = _sql_path(markets_path)

    with duckdb.connect(str(database_path)) as connection:
        connection.execute(
            f"""
            CREATE OR REPLACE VIEW prices AS
            SELECT * EXCLUDE (year, month)
            FROM read_parquet('{parquet_glob}', hive_partitioning = true, union_by_name = true)
            """
        )
        connection.execute(
            f"""
            CREATE OR REPLACE VIEW markets AS
            SELECT * FROM read_csv_auto('{market_csv}', header = true)
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW price_history AS
            SELECT
                p.*,
                m.market_id,
                m.district,
                m.province,
                m.latitude,
                m.longitude,
                avg(p.price_midpoint_lkr) OVER (
                    PARTITION BY p.market, p.commodity
                    ORDER BY p.observation_date
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ) AS moving_average_7,
                avg(p.price_midpoint_lkr) OVER (
                    PARTITION BY p.market, p.commodity
                    ORDER BY p.observation_date
                    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                ) AS moving_average_30
            FROM prices p
            LEFT JOIN markets m ON lower(p.market) = lower(m.market_name)
            """
        )


def _rows_as_dicts(cursor: Any) -> list[dict[str, object]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def query_price_history(
    *,
    database_path: Path,
    market: str | None = None,
    commodity: str | None = None,
    district: str | None = None,
    province: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 1_000,
) -> list[dict[str, object]]:
    """Query filtered history using bound parameters."""

    clauses: list[str] = []
    parameters: list[object] = []
    filters = {
        "market": market,
        "commodity": commodity,
        "district": district,
        "province": province,
    }

    for column, value in filters.items():
        if value:
            clauses.append(f"lower({column}) = lower(?)")
            parameters.append(value.strip())

    if start_date:
        clauses.append("observation_date >= ?")
        parameters.append(start_date)
    if end_date:
        clauses.append("observation_date <= ?")
        parameters.append(end_date)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(limit)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        cursor = connection.execute(
            f"""
            SELECT * FROM price_history
            {where}
            ORDER BY observation_date DESC, market, commodity
            LIMIT ?
            """,
            parameters,
        )
        return _rows_as_dicts(cursor)


def query_price_summary(
    *,
    database_path: Path,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, object]]:
    """Return market/commodity statistics for the requested period."""

    clauses: list[str] = []
    parameters: list[object] = []
    if start_date:
        clauses.append("observation_date >= ?")
        parameters.append(start_date)
    if end_date:
        clauses.append("observation_date <= ?")
        parameters.append(end_date)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with duckdb.connect(str(database_path), read_only=True) as connection:
        cursor = connection.execute(
            f"""
            SELECT
                market,
                commodity,
                min(observation_date) AS first_observation_date,
                max(observation_date) AS latest_observation_date,
                count(*) AS observation_count,
                avg(price_midpoint_lkr) AS average_price_lkr,
                stddev_pop(price_midpoint_lkr) AS volatility_lkr,
                min(price_min_lkr) AS minimum_price_lkr,
                max(price_max_lkr) AS maximum_price_lkr
            FROM prices
            {where}
            GROUP BY market, commodity
            ORDER BY market, commodity
            """,
            parameters,
        )
        return _rows_as_dicts(cursor)
