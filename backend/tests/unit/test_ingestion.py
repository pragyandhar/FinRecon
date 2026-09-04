import pandas as pd
import pytest

from app.core.config import settings
from app.core.errors import ExtractionFailedError, FileTooLargeError, UnsupportedFileTypeError
from app.ingestion.service import ingest_uploaded_files
from app.ingestion.validate import validate_file


@pytest.fixture(autouse=True)
def _isolated_raw_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "raw_storage_dir", str(tmp_path))


def test_validate_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError):
        validate_file("data.pdf", 100)


def test_validate_rejects_oversized_file():
    with pytest.raises(FileTooLargeError):
        validate_file("data.csv", settings.max_file_size_bytes + 1)


def test_csv_ingestion_produces_dataset_and_rows(db_session):
    csv_bytes = b"Txn ID,Amount Paid\nTX1,1000\nTX2,500\n"
    datasets = ingest_uploaded_files(db_session, "job_csv", [("payments.csv", csv_bytes)])

    assert len(datasets) == 1
    assert datasets[0].dataset_id == "payments"
    assert datasets[0].row_count == 2
    assert {c.name for c in datasets[0].columns} == {"Txn ID", "Amount Paid"}


def test_empty_csv_raises_extraction_failed(db_session):
    with pytest.raises(ExtractionFailedError):
        ingest_uploaded_files(db_session, "job_empty", [("empty.csv", b"Txn ID,Amount\n")])


def test_excel_multi_sheet_becomes_multiple_datasets(db_session, tmp_path):
    xlsx_path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(xlsx_path) as writer:
        pd.DataFrame({"order_id": ["O1", "O2"], "amount": [10, 20]}).to_excel(writer, sheet_name="Orders", index=False)
        pd.DataFrame({"pay_ref": ["O1", "O2"], "paid": [10, 19]}).to_excel(writer, sheet_name="Payments", index=False)

    datasets = ingest_uploaded_files(db_session, "job_xlsx", [("book.xlsx", xlsx_path.read_bytes())])
    ids = {d.dataset_id for d in datasets}
    assert ids == {"book_orders", "book_payments"}
    assert all(d.row_count == 2 for d in datasets)


def test_dataset_id_collision_gets_suffixed(db_session):
    csv_bytes = b"a,b\n1,2\n"
    # "data.csv" and "Data.CSV" both sanitize to dataset_id "data".
    datasets = ingest_uploaded_files(
        db_session, "job_collide", [("data.csv", csv_bytes), ("Data.CSV", csv_bytes)]
    )
    ids = sorted(d.dataset_id for d in datasets)
    assert ids == ["data", "data_2"]
