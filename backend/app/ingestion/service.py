from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.ingestion.csv_extractor import CsvExtractor
from app.ingestion.excel_extractor import ExcelExtractor
from app.ingestion.validate import validate_file
from app.models.dataset import Dataset
from app.storage import repository as repo

_EXTRACTORS = [CsvExtractor(), ExcelExtractor()]


def _extractor_for(path: Path):
    for extractor in _EXTRACTORS:
        if extractor.supports(path):
            return extractor
    return None  # validate_file() already rejects anything unsupported


def _unique_id(dataset_id: str, taken: set[str]) -> str:
    if dataset_id not in taken:
        return dataset_id
    n = 2
    while f"{dataset_id}_{n}" in taken:
        n += 1
    return f"{dataset_id}_{n}"


def ingest_uploaded_files(db: Session, job_id: str, uploads: list[tuple[str, bytes]]) -> list[Dataset]:
    """`uploads` is a list of (filename, content) pairs. Raw files are
    written immutably to disk first (original bytes, untouched), then
    extracted into structured datasets/rows persisted to the DB."""

    job_dir = settings.raw_storage_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in uploads:
        validate_file(filename, len(content))

    datasets: list[Dataset] = []
    taken_ids: set[str] = set()
    for filename, content in uploads:
        raw_path = job_dir / filename
        raw_path.write_bytes(content)

        extractor = _extractor_for(raw_path)
        for dataset, rows in extractor.extract(raw_path, job_id=job_id):
            unique_id = _unique_id(dataset.dataset_id, taken_ids)
            taken_ids.add(unique_id)
            if unique_id != dataset.dataset_id:
                dataset = dataset.model_copy(update={"dataset_id": unique_id})
                rows = [r.model_copy(update={"dataset_id": unique_id}) for r in rows]

            repo.save_dataset(db, dataset)
            repo.save_rows(db, job_id, rows)
            datasets.append(dataset)

    return datasets
