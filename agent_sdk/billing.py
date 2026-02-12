"""Chargeback and billing helpers."""

from __future__ import annotations

from typing import Iterable, Dict, Any, List, Sequence, Union

from agent_sdk.observability.stream_envelope import RunMetadata


def _parse_group_fields(group_by: Union[str, Sequence[str]]) -> List[str]:
    if isinstance(group_by, str):
        fields = [field.strip() for field in group_by.split(",") if field.strip()]
    else:
        fields = [field.strip() for field in group_by if field.strip()]
    return fields or ["org_id"]


def _extract_cost(metadata: Dict[str, Any]) -> float:
    for key in ("cost_usd", "total_cost_usd", "cost"):
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _group_value(run: RunMetadata, field: str) -> str:
    if field == "org_id":
        return run.org_id
    if field == "model":
        return run.model or "unknown"
    if field == "status":
        return run.status.value if hasattr(run.status, "value") else str(run.status)
    return run.tags.get(field, "unknown")


def generate_chargeback_report(
    runs: Iterable[RunMetadata],
    group_by: Union[str, Sequence[str]] = "org_id",
) -> List[Dict[str, Any]]:
    """Aggregate usage into chargeback-friendly rows."""
    group_fields = _parse_group_fields(group_by)
    aggregate: Dict[tuple, Dict[str, Any]] = {}
    session_sets: Dict[tuple, set[str]] = {}
    for run in runs:
        key = tuple(_group_value(run, field) for field in group_fields)
        session_sets.setdefault(key, set()).add(run.session_id)
        entry = aggregate.setdefault(
            key,
            {
                "run_count": 0,
                "session_count": 0,
                "token_count": 0,
                "cost_usd": 0.0,
            },
        )
        entry["run_count"] += 1
        entry["token_count"] += int(run.metadata.get("token_count", 0) or 0)
        entry["cost_usd"] += _extract_cost(run.metadata)

    results: List[Dict[str, Any]] = []
    for key, entry in aggregate.items():
        entry["session_count"] = len(session_sets.get(key, set()))
        row = {field: key[idx] for idx, field in enumerate(group_fields)}
        row.update(entry)
        row["cost_usd"] = round(float(row.get("cost_usd", 0.0) or 0.0), 6)
        results.append(row)
    return results
