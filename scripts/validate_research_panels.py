#!/usr/bin/env python3
"""Validate the generated research-panel artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def number(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.casefold() in {"na", "nan", "none", ".", "tbd"}:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel-dir", required=True, type=Path)
    args = parser.parse_args()

    wide = list(rows(args.panel_dir / "master_panel_wide.csv"))
    assert len(wide) == 1350, f"Expected 1350 wide-panel rows, got {len(wide)}"
    keys = {(row["iso3"], row["year"]) for row in wide}
    assert len(keys) == 1350, "Country-year keys are not unique"
    assert len({row["iso3"] for row in wide}) == 54, "Panel must contain 54 sovereign countries"
    assert {int(row["year"]) for row in wide} == set(range(2000, 2025)), "Panel years must be 2000-2024"

    project = list(rows(args.panel_dir / "project_level_master.csv"))
    required = {"project_match_id", "source_db", "record_id", "country_iso3", "year", "amount_value", "price_basis", "match_status"}
    assert required <= set(project[0]), "Project master is missing required columns"
    assert all(row["amount_value"] != "0" for row in project if row["amount_missing"].casefold() == "true"), "Missing amounts were replaced with zero"

    long_source = list(rows(args.panel_dir / "long_source.csv"))
    assert len(long_source) == 54 * 25 * 8, "Source long panel is not balanced"
    assert len({(row["panel_id"], row["year"]) for row in long_source}) == len(long_source), "Long-source key is not unique"

    long_fund = list(rows(args.panel_dir / "long_fundtype.csv"))
    assert len({(row["panel_id"], row["year"]) for row in long_fund}) == len(long_fund), "Long-fundtype key is not unique"

    matches = list(rows(args.panel_dir / "match_candidates.csv"))
    review_queue = list(rows(args.panel_dir / "match_review_queue.csv"))
    review_payload = json.loads((args.panel_dir / "match_review_queue.json").read_text(encoding="utf-8"))
    pending_ids = {row["candidate_id"] for row in matches if row["status"] == "needs_review"}
    assert {row["candidate_id"] for row in review_queue} == pending_ids, "Review queue does not exactly cover pending candidates"
    assert all(row["review_decision"] == "" for row in review_queue), "Review decisions must remain blank until manually adjudicated"
    assert len(review_payload["rows"]) == len(review_queue), "Web review payload and CSV queue differ"
    assert int(review_payload["appliedReviewCount"]) == len([row for row in rows(args.panel_dir / "match_review_decisions_applied.csv") if row["application_status"] == "applied"]), "Applied review count is missing from the web payload"
    assert all(row["suggested_decision"] in {"", "different_project"} for row in review_queue), "Unexpected automatic suggestion"
    queue_record_keys = {
        f"{row[side + '_source']}:{row[side + '_record_id']}"
        for row in review_queue for side in ("left", "right")
    }
    unresolved_project_keys = {
        f"{row['source_db']}:{row['record_id']}" for row in project
        if row["match_status"] == "needs_review"
    }
    assert unresolved_project_keys <= queue_record_keys, "A project marked needs_review is missing from the review queue"

    applied_reviews = list(rows(args.panel_dir / "match_review_decisions_applied.csv"))
    match_groups = list(rows(args.panel_dir / "confirmed_match_groups.csv"))
    project_entities = list(rows(args.panel_dir / "project_entity_index.csv"))
    assert all(row["application_status"] in {"applied", "candidate_not_found", "invalid_decision"} for row in applied_reviews), "Unexpected review application status"
    assert all(int(row["member_count"]) >= 2 for row in match_groups), "Confirmed group contains fewer than two records"
    assert sum(int(row["member_count"]) for row in project_entities) == len(project), "Project entity index does not cover every source record"
    assert all(row["amount_policy"] == "no_cross_source_amount_selected_or_summed" for row in project_entities), "Entity index must not select or sum cross-source amounts"

    missingness = list(rows(args.panel_dir / "panel_missingness.csv"))
    assert missingness, "Panel missingness profile is empty"
    assert all(int(row["observed_count"]) + int(row["missing_count"]) == 1350 for row in missingness), "Missingness counts do not reconcile to the balanced panel"
    missingness_by_variable = {row["variable"]: row for row in missingness}
    for column in ("aidexports_total_usd", "aidexports_medical_usd", "aidexports_non_medical_usd", "fdi_stock_usd", "fdi_flow_usd"):
        actual = [number(row.get(column)) for row in wide]
        known = [value for value in actual if value is not None]
        profile = missingness_by_variable[column]
        assert int(profile["observed_count"]) == len(known), f"Observed count is wrong for {column}"
        assert int(profile["zero_count"]) == sum(value == 0 for value in known), f"Zero count is wrong for {column}"

    outliers = list(rows(args.panel_dir / "outlier_candidates.csv"))
    outlier_keys = {row["record_key"] for row in outliers}
    project_outlier_keys = {f"{row['source_db']}:{row['record_id']}" for row in project if row["is_outlier"].casefold() == "true"}
    assert outlier_keys == project_outlier_keys, "Outlier queue and project-level flags do not reconcile"

    quality = list(rows(args.panel_dir / "project_quality_summary.csv"))
    assert len(quality) == 9, "Quality summary must contain one row per project/event source"

    descriptive = list(rows(args.panel_dir / "source_descriptive_statistics.csv"))
    assert len(descriptive) == 14, "Descriptive statistics must contain all analytical metrics"
    assert all(int(row["observed_count"]) + int(row["missing_count"]) == 1350 for row in descriptive), "Descriptive missingness does not reconcile"

    annual = list(rows(args.panel_dir / "annual_source_trends.csv"))
    assert len(annual) == 14 * 25, "Annual trend table must contain every metric-year"
    assert len({(row["metric_id"], row["year"]) for row in annual}) == len(annual), "Annual trend keys are not unique"
    coverage_fields = {"source_first_observed_year", "source_last_observed_year", "year_complete", "coverage_status", "coverage_note"}
    assert coverage_fields <= set(annual[0]), "Annual trend table is missing coverage metadata"
    aidexports_2024 = next(row for row in annual if row["metric_id"] == "aidexports" and row["year"] == "2024")
    assert aidexports_2024["coverage_status"] == "observed_partial_year", "Partial 2024 aid-export coverage is not flagged"
    assert aidexports_2024["year_complete"].casefold() == "false", "Partial 2024 aid-export year is marked complete"

    country_summary = list(rows(args.panel_dir / "country_source_summary.csv"))
    assert len({(row["metric_id"], row["iso3"]) for row in country_summary}) == len(country_summary), "Country-source keys are not unique"

    correlations = list(rows(args.panel_dir / "cross_source_correlations.csv"))
    assert correlations, "Rank-correlation output is empty"
    assert all(-1 <= float(row["spearman_rho"]) <= 1 for row in correlations), "Invalid Spearman coefficient"
    assert all(-1 <= float(row["kendall_tau_b"]) <= 1 for row in correlations), "Invalid Kendall coefficient"
    assert all(row["comparability_tier"] in {"same_basis_rank_comparison", "different_basis_rank_only"} for row in correlations), "Correlation comparability tier is missing"

    break_models = list(rows(args.panel_dir / "structural_break_models.csv"))
    breakpoints = list(rows(args.panel_dir / "structural_breakpoints.csv"))
    robustness = list(rows(args.panel_dir / "correlation_robustness.csv"))
    assert break_models, "Structural-break model output is empty"
    assert len({(row["metric_id"], row["series_variant"]) for row in break_models}) == len(break_models), "Break-model keys are not unique"
    assert all(int(row["break_count"]) == len([year for year in row["break_years"].split("|") if year]) for row in break_models), "Break counts do not reconcile"
    assert all(int(model["start_year"]) <= int(row["break_year"]) <= int(model["end_year"]) for row in breakpoints for model in break_models if model["metric_id"] == row["metric_id"] and model["series_variant"] == row["series_variant"]), "Breakpoint outside modeled run"
    assert len(robustness) == len(correlations), "Robustness output must cover every baseline comparison"
    assert all(-1 <= float(row["robust_spearman"]) <= 1 for row in robustness), "Invalid robust Spearman coefficient"
    assert all(row["lineage_classification"] in {"likely_shared_lineage", "documented_cross_reference_overlap", "distinct_source_comparison"} for row in robustness), "Unexpected lineage label"

    empirical_report = json.loads((args.panel_dir / "empirical_report.json").read_text(encoding="utf-8"))
    assert empirical_report["summary"]["metricsProfiled"] == len(descriptive), "Empirical report metric count differs"
    assert empirical_report["summary"]["breakModels"] == len(break_models), "Empirical report break-model count differs"
    assert empirical_report["summary"]["breakpoints"] == len(breakpoints), "Empirical report breakpoint count differs"
    assert empirical_report["summary"]["robustnessRows"] == len(robustness), "Empirical report robustness count differs"

    dictionary = list(rows(args.panel_dir / "data_dictionary.csv"))
    dictionary_pairs = {(row["table"], row["column"]) for row in dictionary}
    required_dictionary_pairs = {
        ("long_source", column) for column in long_source[0]
    } | {
        ("long_fundtype", column) for column in long_fund[0]
    } | {
        ("match_candidates", column) for column in matches[0]
    }
    assert required_dictionary_pairs <= dictionary_pairs, "Core long or matching tables are missing from the data dictionary"
    assert "china_eu_dfchina_2017_usd" in wide[0], "China-EU finance USD column is missing"
    assert "china_eu_dfchina_2017_usd_million" not in wide[0], "Obsolete China-EU million-USD label remains"

    summary = {
        "wideRows": len(wide), "countries": len({row["iso3"] for row in wide}),
        "years": [min(int(row["year"]) for row in wide), max(int(row["year"]) for row in wide)],
        "projectRows": len(project), "projectSources": dict(Counter(row["source_db"] for row in project)),
        "matchStatus": dict(Counter(row["match_status"] for row in project)),
        "longSourceRows": len(long_source), "longFundtypeRows": len(long_fund),
        "matchReviewRows": len(review_queue), "outlierCandidateRows": len(outliers),
        "panelVariablesProfiled": len(missingness),
        "descriptiveMetrics": len(descriptive), "annualTrendRows": len(annual),
        "countrySummaryRows": len(country_summary), "correlationRows": len(correlations),
        "breakModels": len(break_models), "breakpoints": len(breakpoints),
        "robustnessRows": len(robustness),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
