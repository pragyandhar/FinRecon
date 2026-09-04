from pathlib import Path

import pandas as pd

from app.core.errors import ExtractionFailedError
from app.ingestion.base import Extractor, dataframe_to_dataset, sanitize_dataset_id
from app.models.dataset import Dataset, DatasetRow


class ExcelExtractor(Extractor):
    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in {".xlsx", ".xls"}

    def extract(self, path: Path, *, job_id: str) -> list[tuple[Dataset, list[DatasetRow]]]:
        try:
            sheets = pd.read_excel(path, sheet_name=None)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionFailedError(f"could not parse Excel '{path.name}': {exc}") from exc

        non_empty = {name: df for name, df in sheets.items() if not df.empty}
        if not non_empty:
            raise ExtractionFailedError(f"'{path.name}' has no non-empty sheets")

        single_sheet = len(non_empty) == 1
        results: list[tuple[Dataset, list[DatasetRow]]] = []
        for sheet_name, df in non_empty.items():
            base = path.stem if single_sheet else f"{path.stem}_{sheet_name}"
            dataset_id = sanitize_dataset_id(base)
            results.append(
                dataframe_to_dataset(
                    df, job_id=job_id, dataset_id=dataset_id, source_file=path.name, sheet=sheet_name
                )
            )
        return results
