from typing import Any

from pydantic import BaseModel, Field


class ColumnStats(BaseModel):
    """Deterministic stats computed in code and handed to the schema-
    understanding model instead of raw rows, to keep prompts small."""

    name: str
    inferred_type: str  # "string" | "number" | "date" | "boolean"
    null_rate: float
    unique_rate: float
    sample_values: list[Any] = Field(default_factory=list)


class DatasetColumn(BaseModel):
    name: str
    raw_type: str


class DatasetRow(BaseModel):
    row_id: str
    dataset_id: str
    values: dict[str, Any]
    # Provenance back to the original file.
    source_file: str
    sheet: str | None = None
    row_index: int


class Dataset(BaseModel):
    dataset_id: str
    job_id: str
    source_file: str
    columns: list[DatasetColumn]
    row_count: int
    column_stats: list[ColumnStats] = Field(default_factory=list)
