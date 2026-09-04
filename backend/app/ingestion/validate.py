from pathlib import Path

from app.core.config import settings
from app.core.errors import FileTooLargeError, UnsupportedFileTypeError

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def validate_file(filename: str, size_bytes: int) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"'{filename}' has unsupported extension '{ext}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}."
        )
    if size_bytes > settings.max_file_size_bytes:
        raise FileTooLargeError(
            f"'{filename}' is {size_bytes / 1_048_576:.1f} MB, "
            f"exceeds limit of {settings.max_file_size_mb} MB."
        )
