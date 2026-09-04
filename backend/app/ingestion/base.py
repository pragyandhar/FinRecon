import re
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from app.ingestion.stats import compute_column_stats
from app.models.dataset import Dataset, DatasetColumn, DatasetRow


def sanitize_dataset_id(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
    return slug or "dataset"


def dataframe_to_dataset(
    df: pd.DataFrame, *, job_id: str, dataset_id: str, source_file: str, sheet: str | None = None
) -> tuple[Dataset, list[DatasetRow]]:
    df = df.dropna(axis="columns", how="all")
    columns = [DatasetColumn(name=str(c), raw_type=str(df[c].dtype)) for c in df.columns]
    rows = [
        DatasetRow(
            row_id=f"{dataset_id}_{i:06d}",
            dataset_id=dataset_id,
            values={str(k): _clean(v) for k, v in record.items()},
            source_file=source_file,
            sheet=sheet,
            row_index=i,
        )
        for i, record in enumerate(df.to_dict(orient="records"))
    ]
    dataset = Dataset(
        dataset_id=dataset_id,
        job_id=job_id,
        source_file=source_file,
        columns=columns,
        row_count=len(rows),
        column_stats=compute_column_stats(df),
    )
    return dataset, rows


def _clean(value: object) -> object:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


class Extractor(ABC):
    @abstractmethod
    def supports(self, path: Path) -> bool: ...

    @abstractmethod
    def extract(self, path: Path, *, job_id: str) -> list[tuple[Dataset, list[DatasetRow]]]:
        """Returns one (Dataset, rows) pair per logical dataset found in
        the file (a CSV yields one, a multi-sheet workbook yields one per
        non-empty sheet)."""
