"""The generic, deterministic reconciliation engine.

This module hardcodes operation *semantics* (what JOIN/COMPARE/MISSING/
DUPLICATE/FILTER/GROUP/AGGREGATE mean) and nothing about any specific
financial schema. Every field it touches comes from the validated
ReconciliationPlan's canonical field names, resolved at runtime against
whatever canonical mapping this job produced. No LLM calls happen here.
"""

from dataclasses import dataclass, field

import pandas as pd

from app.core.config import settings
from app.core.errors import PlanExecutionError
from app.core.util import to_native
from app.models.dataset import Dataset, DatasetRow
from app.models.enums import (
    AggregateFunction,
    ComparisonType,
    FilterOperator,
    JoinType,
    OperationType,
)
from app.models.plan import PlanStep, ReconciliationPlan
from app.models.result import CheckDetail, Evidence, ReconciliationResult
from app.models.schema import CanonicalMapping

_JOIN_HOW = {
    JoinType.INNER: "inner",
    JoinType.LEFT_OUTER: "left",
    JoinType.FULL_OUTER: "outer",
}


def _rowid_col(dataset_id: str) -> str:
    return f"__rowid__{dataset_id}"


@dataclass
class ExecutionContext:
    canonical_mapping: CanonicalMapping
    relations: dict[str, pd.DataFrame] = field(default_factory=dict)
    relation_sources: dict[str, set[str]] = field(default_factory=dict)
    join_sides: dict[str, dict[str, str]] = field(default_factory=dict)
    join_keys: dict[str, str] = field(default_factory=dict)
    group_cols: dict[str, list[str]] = field(default_factory=dict)
    row_lookup: dict[tuple[str, str], DatasetRow] = field(default_factory=dict)
    aggregate_outputs: dict[str, list[dict]] = field(default_factory=dict)


@dataclass
class ExecutionOutput:
    results: list[ReconciliationResult]
    aggregate_outputs: dict[str, list[dict]]


def _build_base_relation(dataset_id: str, rows: list[DatasetRow], canonical_mapping: CanonicalMapping) -> pd.DataFrame:
    field_map = canonical_mapping.mapping.get(dataset_id, {})  # canonical_name -> raw_field
    records = []
    for r in rows:
        record = {canonical: r.values.get(raw) for canonical, raw in field_map.items()}
        record[_rowid_col(dataset_id)] = r.row_id
        records.append(record)
    columns = list(field_map.keys()) + [_rowid_col(dataset_id)]
    return pd.DataFrame.from_records(records, columns=columns) if records else pd.DataFrame(columns=columns)


def _resolve_column(df: pd.DataFrame, name: str, step_id: str) -> str:
    if name in df.columns:
        return name
    candidates = [c for c in df.columns if c == name or c.startswith(f"{name}__")]
    if len(candidates) == 1:
        return candidates[0]
    raise PlanExecutionError(
        f"step '{step_id}': cannot resolve field '{name}' among columns {list(df.columns)}"
        + (f" (ambiguous: {candidates})" if candidates else "")
    )


def _is_missing(value: object) -> bool:
    try:
        result = pd.isna(value)
        return bool(result) if not hasattr(result, "__len__") else False
    except (TypeError, ValueError):
        return False


def _record_id(row: pd.Series, join_key_col: str | None, sources: set[str], ctx: ExecutionContext) -> str:
    if join_key_col and join_key_col in row.index and not _is_missing(row[join_key_col]):
        return f"{join_key_col}:{row[join_key_col]}"
    for dataset_id in sorted(sources):
        col = _rowid_col(dataset_id)
        if col in row.index and not _is_missing(row[col]):
            return str(row[col])
    return "unknown"


def _build_evidence(row: pd.Series, sources: set[str], ctx: ExecutionContext) -> list[Evidence]:
    evidence = []
    for dataset_id in sorted(sources):
        col = _rowid_col(dataset_id)
        if col not in row.index or _is_missing(row[col]):
            continue
        row_id = str(row[col])
        data_row = ctx.row_lookup.get((dataset_id, row_id))
        if data_row is None:
            continue
        field_map = ctx.canonical_mapping.mapping.get(dataset_id, {})
        canonical_values = {c: data_row.values.get(raw) for c, raw in field_map.items()}
        evidence.append(Evidence(dataset_id=dataset_id, row_id=row_id, values=canonical_values))
    return evidence


def _guard_join_size(step: PlanStep, merged: pd.DataFrame, left_df: pd.DataFrame, right_df: pd.DataFrame) -> None:
    """A JOIN on a genuine identifier produces at most a few times the
    larger input's row count. A JOIN on a low-cardinality field (e.g.
    "status" or "currency" chosen instead of an actual ID) produces a
    combinatorial blowup instead — every left row sharing a value pairs
    with every right row sharing it. Left unchecked, that cascades into
    tens of thousands of downstream results, each an "exception" queued
    for individual AI investigation: hours of runtime and real API
    spend for a plan that was never valid reconciliation logic. Refuse
    immediately rather than let that happen."""

    input_size = max(len(left_df), len(right_df), 1)
    if len(merged) > settings.max_join_output_rows or len(merged) > settings.max_join_output_multiplier * input_size:
        raise PlanExecutionError(
            f"step '{step.step_id}': JOIN on '{step.left_field}'/'{step.right_field}' produced "
            f"{len(merged)} rows from {len(left_df)}x{len(right_df)} input rows. That means this field "
            f"is not a unique identifier (a real join key duplicates rarely, if ever) — likely a "
            f"low-cardinality field like status/currency got used as the join key instead of an ID. "
            f"Refusing to execute what would be a combinatorial blowup."
        )


def _do_join(ctx: ExecutionContext, step: PlanStep) -> None:
    left_df = ctx.relations[step.left]
    right_df = ctx.relations[step.right]
    how = _JOIN_HOW[step.join_type]
    suffixes = (f"__{step.left}", f"__{step.right}")

    if step.left_field == step.right_field:
        merged = pd.merge(left_df, right_df, how=how, on=step.left_field, suffixes=suffixes)
        key_col = step.left_field
    else:
        merged = pd.merge(
            left_df, right_df, how=how, left_on=step.left_field, right_on=step.right_field, suffixes=suffixes
        )
        key_col = step.left_field

    _guard_join_size(step, merged, left_df, right_df)
    ctx.relations[step.step_id] = merged
    ctx.relation_sources[step.step_id] = ctx.relation_sources[step.left] | ctx.relation_sources[step.right]
    ctx.join_sides[step.step_id] = {"left": step.left, "right": step.right}
    ctx.join_keys[step.step_id] = key_col


_COMPARATORS = {
    FilterOperator.EQ: lambda a, b: a == b,
    FilterOperator.NE: lambda a, b: a != b,
    FilterOperator.GT: lambda a, b: a > b,
    FilterOperator.LT: lambda a, b: a < b,
    FilterOperator.GE: lambda a, b: a >= b,
    FilterOperator.LE: lambda a, b: a <= b,
}


@dataclass
class _ComparisonOutcome:
    passed: bool
    label: str
    error: str | None = None


def _evaluate_comparison(comparison: ComparisonType, a: object, b: object, tolerance: float | None, max_days: int | None) -> _ComparisonOutcome:
    if comparison == ComparisonType.EQUALS:
        passed = a == b
        return _ComparisonOutcome(passed, "EQUAL" if passed else "NOT_EQUAL")
    if comparison == ComparisonType.NOT_EQUALS:
        passed = a != b
        return _ComparisonOutcome(passed, "NOT_EQUAL" if passed else "EQUAL")
    if comparison == ComparisonType.TOLERANCE:
        try:
            diff = abs(float(a) - float(b))
        except (TypeError, ValueError):
            return _ComparisonOutcome(False, "NOT_COMPARABLE", error="values are not numeric")
        tol = tolerance if tolerance is not None else 0.0
        passed = diff <= tol
        return _ComparisonOutcome(passed, "WITHIN_TOLERANCE" if passed else "OUT_OF_TOLERANCE")
    if comparison in (ComparisonType.DATE_DIFF, ComparisonType.DATE_WITHIN):
        da, db = pd.to_datetime(a, errors="coerce"), pd.to_datetime(b, errors="coerce")
        if pd.isna(da) or pd.isna(db):
            return _ComparisonOutcome(False, "NOT_COMPARABLE", error="values are not valid dates")
        diff_days = abs((da - db).days)
        window = max_days if max_days is not None else 0
        passed = diff_days <= window
        return _ComparisonOutcome(passed, "WITHIN_WINDOW" if passed else "OUT_OF_WINDOW")
    raise PlanExecutionError(f"unsupported comparison type: {comparison}")


def _do_compare(ctx: ExecutionContext, step: PlanStep, job_id: str) -> list[ReconciliationResult]:
    df = ctx.relations[step.input]
    col_a = _resolve_column(df, step.field_a, step.step_id)
    col_b = _resolve_column(df, step.field_b, step.step_id)
    join_key_col = ctx.join_keys.get(step.input)
    sources = ctx.relation_sources.get(step.input, {step.input})

    results = []
    for _, row in df.iterrows():
        record_id = _record_id(row, join_key_col, sources, ctx)
        evidence = _build_evidence(row, sources, ctx)
        a, b = row.get(col_a), row.get(col_b)

        if _is_missing(a) or _is_missing(b):
            results.append(
                ReconciliationResult(
                    record_id=record_id,
                    job_id=job_id,
                    step_id=step.step_id,
                    status="EXCEPTION",
                    rule_applied=f"COMPARE:{step.comparison}",
                    checks=[CheckDetail(field=f"{step.field_a} vs {step.field_b}", expected=to_native(a), actual=to_native(b), result="MISSING_VALUE")],
                    evidence=evidence,
                    reason="one or both compared values are missing",
                )
            )
            continue

        outcome = _evaluate_comparison(step.comparison, a, b, step.tolerance, step.max_days)
        status = "EXCEPTION" if outcome.error else ("MATCHED" if outcome.passed else "MISMATCHED")
        rule = f"{step.comparison}"
        if step.comparison == ComparisonType.TOLERANCE:
            rule += f"({step.tolerance})"
        elif step.comparison in (ComparisonType.DATE_DIFF, ComparisonType.DATE_WITHIN):
            rule += f"({step.max_days}d)"

        results.append(
            ReconciliationResult(
                record_id=record_id,
                job_id=job_id,
                step_id=step.step_id,
                status=status,
                rule_applied=rule,
                checks=[CheckDetail(field=f"{step.field_a} vs {step.field_b}", expected=to_native(a), actual=to_native(b), result=outcome.label)],
                evidence=evidence,
                reason=outcome.error,
            )
        )
    return results


def _do_missing(ctx: ExecutionContext, step: PlanStep, job_id: str) -> list[ReconciliationResult]:
    df = ctx.relations[step.input]
    join = ctx.join_sides.get(step.input)
    if join is None:
        raise PlanExecutionError(f"step '{step.step_id}': input '{step.input}' is not a JOIN result")
    side_ref = join[step.side]
    side_sources = ctx.relation_sources.get(side_ref, {side_ref})
    rowid_cols = [c for d in side_sources if (c := _rowid_col(d)) in df.columns]
    if not rowid_cols:
        return []

    missing_mask = df[rowid_cols].isna().all(axis=1)
    join_key_col = ctx.join_keys.get(step.input)
    sources = ctx.relation_sources.get(step.input, set())

    results = []
    for _, row in df[missing_mask].iterrows():
        record_id = _record_id(row, join_key_col, sources, ctx)
        results.append(
            ReconciliationResult(
                record_id=record_id,
                job_id=job_id,
                step_id=step.step_id,
                status="EXCEPTION",
                rule_applied=f"MISSING:{step.side}",
                checks=[],
                evidence=_build_evidence(row, sources, ctx),
                reason=f"no counterpart found on the '{step.side}' side",
            )
        )
    return results


def _do_duplicate(ctx: ExecutionContext, step: PlanStep, job_id: str) -> list[ReconciliationResult]:
    df = ctx.relations[step.input]
    cols = [_resolve_column(df, f, step.step_id) for f in step.fields]
    dup_mask = df.duplicated(subset=cols, keep="first")
    join_key_col = ctx.join_keys.get(step.input, cols[0])
    sources = ctx.relation_sources.get(step.input, {step.input})

    results = []
    for _, row in df[dup_mask].iterrows():
        record_id = _record_id(row, join_key_col, sources, ctx)
        results.append(
            ReconciliationResult(
                record_id=record_id,
                job_id=job_id,
                step_id=step.step_id,
                status="EXCEPTION",
                rule_applied=f"DUPLICATE:{step.fields}",
                checks=[CheckDetail(field=",".join(step.fields), expected="unique", actual=[to_native(row[c]) for c in cols], result="DUPLICATE")],
                evidence=_build_evidence(row, sources, ctx),
                reason=f"duplicate value for {step.fields}",
            )
        )
    return results


def _do_filter(ctx: ExecutionContext, step: PlanStep) -> None:
    df = ctx.relations[step.input]
    col = _resolve_column(df, step.field, step.step_id)
    comparator = _COMPARATORS[step.operator]
    try:
        mask = comparator(df[col], step.value)
    except TypeError:
        mask = comparator(df[col].astype(str), str(step.value))
    ctx.relations[step.step_id] = df[mask]
    ctx.relation_sources[step.step_id] = ctx.relation_sources.get(step.input, {step.input})
    if step.input in ctx.join_keys:
        ctx.join_keys[step.step_id] = ctx.join_keys[step.input]
    if step.input in ctx.join_sides:
        ctx.join_sides[step.step_id] = ctx.join_sides[step.input]


def _do_group(ctx: ExecutionContext, step: PlanStep) -> None:
    ctx.relations[step.step_id] = ctx.relations[step.input]
    ctx.relation_sources[step.step_id] = ctx.relation_sources.get(step.input, {step.input})
    ctx.group_cols[step.step_id] = step.group_by or []


def _do_aggregate(ctx: ExecutionContext, step: PlanStep) -> None:
    df = ctx.relations[step.input]
    group_by = step.group_by or ctx.group_cols.get(step.input) or []
    agg_col = _resolve_column(df, step.agg_field, step.step_id) if step.agg_field else None

    if group_by:
        group_cols = [_resolve_column(df, g, step.step_id) for g in group_by]
        grouped = df.groupby(group_cols, dropna=False)
        if step.agg_function == AggregateFunction.SUM:
            out = grouped[agg_col].sum().reset_index()
        elif step.agg_function == AggregateFunction.AVG:
            out = grouped[agg_col].mean().reset_index()
        else:
            out = grouped.size().reset_index(name="count")
    else:
        if step.agg_function == AggregateFunction.SUM:
            value = df[agg_col].sum()
        elif step.agg_function == AggregateFunction.AVG:
            value = df[agg_col].mean()
        else:
            value = len(df)
        out = pd.DataFrame([{step.agg_function.value.lower(): value}])

    ctx.aggregate_outputs[step.step_id] = [
        {k: to_native(v) for k, v in record.items()} for record in out.to_dict(orient="records")
    ]
    ctx.relations[step.step_id] = out
    ctx.relation_sources[step.step_id] = set()


def run_plan(
    job_id: str,
    plan: ReconciliationPlan,
    datasets: list[Dataset],
    rows_by_dataset: dict[str, list[DatasetRow]],
    canonical_mapping: CanonicalMapping,
) -> ExecutionOutput:
    ctx = ExecutionContext(canonical_mapping=canonical_mapping)
    for dataset in datasets:
        rows = rows_by_dataset.get(dataset.dataset_id, [])
        ctx.relations[dataset.dataset_id] = _build_base_relation(dataset.dataset_id, rows, canonical_mapping)
        ctx.relation_sources[dataset.dataset_id] = {dataset.dataset_id}
        for r in rows:
            ctx.row_lookup[(dataset.dataset_id, r.row_id)] = r

    results: list[ReconciliationResult] = []
    for step in plan.steps:
        if step.operation == OperationType.JOIN:
            _do_join(ctx, step)
        elif step.operation == OperationType.COMPARE:
            results.extend(_do_compare(ctx, step, job_id))
        elif step.operation == OperationType.MISSING:
            results.extend(_do_missing(ctx, step, job_id))
        elif step.operation == OperationType.DUPLICATE:
            results.extend(_do_duplicate(ctx, step, job_id))
        elif step.operation == OperationType.FILTER:
            _do_filter(ctx, step)
        elif step.operation == OperationType.GROUP:
            _do_group(ctx, step)
        elif step.operation == OperationType.AGGREGATE:
            _do_aggregate(ctx, step)
        else:
            raise PlanExecutionError(f"unsupported operation: {step.operation}")

    return ExecutionOutput(results=results, aggregate_outputs=ctx.aggregate_outputs)
