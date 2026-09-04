from pathlib import Path

import pandas as pd

from app.core.errors import ExtractionFailedError
from app.ingestion.base import Extractor, dataframe_to_dataset, sanitize_dataset_id
from app.models.dataset import Dataset, DatasetRow


class CsvExtractor(Extractor):
    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".csv"

    def extract(self, path: Path, *, job_id: str) -> list[tuple[Dataset, list[DatasetRow]]]:
        try:
            df = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001 — deliberately broad: any parse failure is ours to report
            raise ExtractionFailedError(f"could not parse CSV '{path.name}': {exc}") from exc
        if df.empty:
            raise ExtractionFailedError(f"'{path.name}' has no rows")
        dataset_id = sanitize_dataset_id(path.stem)
        return [dataframe_to_dataset(df, job_id=job_id, dataset_id=dataset_id, source_file=path.name)]
