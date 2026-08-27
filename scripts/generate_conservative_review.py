#!/usr/bin/env python3
"""Generate conservative, auditable recommendations for unresolved project pairs."""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path


RECOMMENDATION_COLUMNS = [
    "candidate_id", "left_source", "left_record_id", "right_source",
    "right_record_id", "review_decision", "confidence", "auto_apply",
    "rule_id", "review_notes", "similarity", "country_iso3", "year",
    "left_title", "right_title",
]


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write(path: Path, output: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output)


def normalized_title(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_value).split())


def comparable_ratio(row: dict) -> float | None:
    try:
        return float(row["amount_ratio_if_comparable"])
    except (TypeError, ValueError):
        return None


def recommend(row: dict) -> dict:
    decision = "uncertain"
    confidence = "low"
    auto_apply = "false"
    rule_id = "manual_evidence_required"
    reason = "Title similarity alone is insufficient; retain both source records pending external-source verification."

    if row["review_hint"] == "qualifier_conflict_check_separate_projects":
        decision = "different_project"
        confidence = "high"
        auto_apply = "true"
        rule_id = "conflicting_project_component_identifier"
        reason = "Distinct lot, loan, phase, unit, package, section or stage identifiers indicate separately recorded project components."
    else:
        ratio = comparable_ratio(row)
        same_record_id = row["left_record_id"] == row["right_record_id"] and row["left_record_id"] != ""
        compatible = row["left_fund_type"] == row["right_fund_type"] and row["left_sector"] == row["right_sector"]
        amount_agrees = ratio is not None and .98 <= ratio <= 1.02
        exact_title = normalized_title(row["left_title"]) == normalized_title(row["right_title"])
        if same_record_id and compatible and amount_agrees:
            decision = "same_project"
            confidence = "high"
            auto_apply = "true"
            rule_id = "same_source_identifier_and_amount"
            reason = "The cross-source records share the same source-specific ID, fund type, sector and comparable amount (within 2%)."
        elif exact_title and compatible and (amount_agrees or ratio is None):
            decision = "same_project"
            confidence = "high"
            auto_apply = "true"
            rule_id = "exact_normalized_title_and_compatible_fields"
            reason = "Normalized titles are identical and the available fund, sector and amount evidence does not conflict."
        elif row["review_hint"] == "sector_conflict_check_context":
            confidence = "low"
            rule_id = "sector_conflict_requires_context"
            reason = "Sector labels conflict and may reflect classification error or genuinely different projects; external evidence is required."

    return {
        **{column: row.get(column, "") for column in RECOMMENDATION_COLUMNS},
        "review_decision": decision, "confidence": confidence,
        "auto_apply": auto_apply, "rule_id": rule_id, "review_notes": reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--recommendations", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    args = parser.parse_args()

    recommendations = [recommend(row) for row in rows(args.queue)]
    applied = [
        {
            "candidate_id": row["candidate_id"], "left_source": row["left_source"],
            "left_record_id": row["left_record_id"], "right_source": row["right_source"],
            "right_record_id": row["right_record_id"], "review_decision": row["review_decision"],
            "review_notes": f"AUTO_REVIEW {row['rule_id']}: {row['review_notes']}",
            "reviewed_at": "2026-08-12T00:00:00+08:00",
        }
        for row in recommendations if row["auto_apply"] == "true"
    ]
    write(args.recommendations, recommendations, RECOMMENDATION_COLUMNS)
    write(args.decisions, applied, [
        "candidate_id", "left_source", "left_record_id", "right_source",
        "right_record_id", "review_decision", "review_notes", "reviewed_at",
    ])
    print({
        "reviewed": len(recommendations), "autoApplied": len(applied),
        "decisions": dict(Counter(row["review_decision"] for row in recommendations)),
        "rules": dict(Counter(row["rule_id"] for row in recommendations)),
    })


if __name__ == "__main__":
    main()
