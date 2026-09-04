import pandas as pd

from app.models.dataset import ColumnStats

_SAMPLE_SIZE = 5


def _to_native(value: object) -> object:
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return str(value)


def _infer_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    non_null = series.dropna()
    if non_null.empty:
        return "string"
    sample = non_null.head(20)
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    if parsed.notna().mean() >= 0.8:
        return "date"
    return "string"


def compute_column_stats(df: pd.DataFrame) -> list[ColumnStats]:
    """Deterministic per-column statistics. This — not raw rows — is what
    gets sent to the schema-understanding model, to keep prompts small
    and avoid leaking full financial records unnecessarily."""

    stats: list[ColumnStats] = []
    total = len(df)
    for column in df.columns:
        series = df[column]
        inferred_type = _infer_type(series)
        null_rate = float(series.isna().mean()) if total else 0.0
        unique_rate = float(series.nunique(dropna=True) / total) if total else 0.0
        samples = [_to_native(v) for v in series.dropna().unique()[:_SAMPLE_SIZE]]
        stats.append(
            ColumnStats(
                name=str(column),
                inferred_type=inferred_type,
                null_rate=round(null_rate, 4),
                unique_rate=round(unique_rate, 4),
                sample_values=samples,
            )
        )
    return stats
