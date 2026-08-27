#!/usr/bin/env python3
"""Audit reviewed project-match decisions for logical contradictions.

The checks deliberately operate on both the decision graph and the generated
entity index.  This catches direct duplicates as well as transitive conflicts
that are invisible when candidate pairs are inspected one at a time.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ALLOWED_DECISIONS = {"same_project", "different_project"}
UNCERTAINTY_RE = re.compile(
    r"\b(?:uncertain|unsure|maybe|possibly|insufficient|cannot determine|not sure)\b|"
    r"暂不确定|不确定|可能|待审|需要人工",
    re.IGNORECASE,
)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def record_key(source: str, record_id: str) -> str:
    return f"{source.strip()}:{record_id.strip()}"


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        self.parent.setdefault(value, value)
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def audit(
    decisions_path: Path,
    audit_path: Path,
    candidates_path: Path,
    applied_path: Path,
    entities_path: Path,
) -> dict:
    decisions = read_rows(decisions_path)
    audit_rows = read_rows(audit_path)
    candidates = read_rows(candidates_path)
    applied_rows = read_rows(applied_path)
    entities = read_rows(entities_path)

    errors: list[dict] = []
    warnings: list[dict] = []

    decision_id_counts = Counter(row.get("candidate_id", "").strip() for row in decisions)
    duplicate_ids = sorted(key for key, count in decision_id_counts.items() if key and count > 1)
    for candidate_id in duplicate_ids:
        errors.append({"type": "duplicate_candidate_id", "candidate_id": candidate_id})

    decision_by_id = {row.get("candidate_id", "").strip(): row for row in decisions}
    candidate_by_id = {row.get("candidate_id", "").strip(): row for row in candidates}
    audit_by_id = {row.get("candidate_id", "").strip(): row for row in audit_rows}
    applied_by_id = {row.get("candidate_id", "").strip(): row for row in applied_rows}

    pair_decisions: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    same_graph = UnionFind()
    resolved_pairs: list[tuple[str, str, str, str]] = []

    for row in decisions:
        candidate_id = row.get("candidate_id", "").strip()
        decision = row.get("review_decision", "").strip()
        if decision not in ALLOWED_DECISIONS:
            errors.append({"type": "invalid_or_uncertain_decision", "candidate_id": candidate_id, "value": decision})

        candidate = candidate_by_id.get(candidate_id)
        if candidate is None:
            errors.append({"type": "candidate_not_found", "candidate_id": candidate_id})
            left = record_key(row.get("left_source", ""), row.get("left_record_id", ""))
            right = record_key(row.get("right_source", ""), row.get("right_record_id", ""))
        else:
            left = candidate.get("left_record_key", "").strip()
            right = candidate.get("right_record_key", "").strip()
            supplied = {
                record_key(row.get("left_source", ""), row.get("left_record_id", "")),
                record_key(row.get("right_source", ""), row.get("right_record_id", "")),
            }
            if supplied != {left, right}:
                errors.append({
                    "type": "decision_endpoint_mismatch", "candidate_id": candidate_id,
                    "decision_endpoints": sorted(supplied), "candidate_endpoints": sorted((left, right)),
                })

        pair = tuple(sorted((left, right)))
        pair_decisions[pair].add(decision)
        pair_ids[pair].append(candidate_id)
        resolved_pairs.append((candidate_id, left, right, decision))
        if decision == "same_project":
            same_graph.union(left, right)

        audit_row = audit_by_id.get(candidate_id)
        if audit_row is None:
            errors.append({"type": "missing_audit_row", "candidate_id": candidate_id})
        elif audit_row.get("review_decision", "").strip() != decision:
            errors.append({"type": "audit_decision_mismatch", "candidate_id": candidate_id})

        applied = applied_by_id.get(candidate_id)
        if applied is None:
            errors.append({"type": "missing_applied_row", "candidate_id": candidate_id})
        elif applied.get("application_status", "").strip() != "applied":
            errors.append({
                "type": "decision_not_applied", "candidate_id": candidate_id,
                "status": applied.get("application_status", "").strip(),
            })
        elif applied.get("review_decision", "").strip() != decision:
            errors.append({"type": "applied_decision_mismatch", "candidate_id": candidate_id})

        note = " ".join((row.get("review_notes", ""), (audit_row or {}).get("rule_evidence", "")))
        confidence = (audit_row or {}).get("confidence", "").strip().casefold()
        if UNCERTAINTY_RE.search(note) or confidence in {"", "low", "uncertain"}:
            warnings.append({
                "type": "uncertainty_language_or_confidence", "candidate_id": candidate_id,
                "confidence": confidence,
            })

    for pair, values in pair_decisions.items():
        if len(values) > 1:
            errors.append({
                "type": "opposing_decisions_for_same_pair", "record_pair": list(pair),
                "decisions": sorted(values), "candidate_ids": pair_ids[pair],
            })

    for candidate_id, left, right, decision in resolved_pairs:
        if decision == "different_project" and same_graph.find(left) == same_graph.find(right):
            errors.append({
                "type": "transitive_decision_contradiction", "candidate_id": candidate_id,
                "record_pair": sorted((left, right)),
            })

    entity_by_record: dict[str, str] = {}
    entity_member_counts: list[int] = []
    for entity in entities:
        entity_id = entity.get("project_entity_id", "").strip()
        members = [value for value in entity.get("member_record_keys", "").split("|") if value]
        entity_member_counts.append(len(members))
        for member in members:
            previous = entity_by_record.setdefault(member, entity_id)
            if previous != entity_id:
                errors.append({"type": "record_in_multiple_entities", "record_key": member})

    for candidate_id, left, right, decision in resolved_pairs:
        left_entity = entity_by_record.get(left)
        right_entity = entity_by_record.get(right)
        if left_entity is None or right_entity is None:
            errors.append({
                "type": "record_missing_from_entity_index", "candidate_id": candidate_id,
                "missing": [key for key, entity in ((left, left_entity), (right, right_entity)) if entity is None],
            })
        elif decision == "same_project" and left_entity != right_entity:
            errors.append({
                "type": "same_project_split_across_entities", "candidate_id": candidate_id,
                "entities": [left_entity, right_entity],
            })
        elif decision == "different_project" and left_entity == right_entity:
            errors.append({
                "type": "different_project_collapsed_into_one_entity", "candidate_id": candidate_id,
                "entity": left_entity,
            })

    extra_audit_ids = sorted(set(audit_by_id) - set(decision_by_id))
    extra_applied_ids = sorted(set(applied_by_id) - set(decision_by_id))
    if extra_audit_ids:
        warnings.append({"type": "audit_rows_without_current_decision", "count": len(extra_audit_ids), "sample": extra_audit_ids[:10]})
    if extra_applied_ids:
        warnings.append({"type": "applied_rows_without_current_decision", "count": len(extra_applied_ids), "sample": extra_applied_ids[:10]})

    origin_counts = Counter(row.get("decision_origin", "").strip() for row in audit_rows)
    confidence_counts = Counter(row.get("confidence", "").strip() for row in audit_rows)
    decision_counts = Counter(row.get("review_decision", "").strip() for row in decisions)

    return {
        "status": "pass" if not errors and not warnings else "fail" if errors else "pass_with_warnings",
        "counts": {
            "decisions": len(decisions),
            "same_project": decision_counts.get("same_project", 0),
            "different_project": decision_counts.get("different_project", 0),
            "uncertain_or_invalid": len(decisions) - sum(decision_counts.get(value, 0) for value in ALLOWED_DECISIONS),
            "unique_candidate_ids": len(decision_id_counts),
            "unique_record_pairs": len(pair_decisions),
            "audit_rows": len(audit_rows),
            "applied_rows": len(applied_rows),
            "project_entities": len(entities),
            "entity_members": sum(entity_member_counts),
        },
        "decision_origins": dict(sorted(origin_counts.items())),
        "confidence": dict(sorted(confidence_counts.items())),
        "checks": {
            "duplicate_candidate_ids": len(duplicate_ids),
            "opposing_pair_decisions": sum(len(values) > 1 for values in pair_decisions.values()),
            "transitive_contradictions": sum(item["type"] == "transitive_decision_contradiction" for item in errors),
            "final_entity_contradictions": sum(item["type"] in {
                "same_project_split_across_entities", "different_project_collapsed_into_one_entity"
            } for item in errors),
            "uncertainty_flags": sum(item["type"] == "uncertainty_language_or_confidence" for item in warnings),
        },
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--applied", required=True, type=Path)
    parser.add_argument("--entities", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = audit(args.decisions, args.audit, args.candidates, args.applied, args.entities)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
