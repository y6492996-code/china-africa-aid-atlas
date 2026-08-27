import unittest
import csv
import tempfile
from pathlib import Path

from scripts.build_research_panels import (
    apply_matching,
    build_match_review_queue,
    apply_review_decisions,
    detect_amount_outliers,
    fit_multiple_mean_breaks,
    fund_type,
    kendall_tau_b,
    lineage_classification,
    spearman_correlation,
    title_similarity,
)
from scripts.generate_conservative_review import recommend


class ResearchPanelRulesTest(unittest.TestCase):
    def test_exact_project_titles_are_high_confidence(self):
        score = title_similarity("Kaleta Hydropower Plant (240MW)", "Kaleta Hydropower Plant (240MW)")
        self.assertGreaterEqual(score, 0.85)

    def test_sibling_lots_are_not_auto_matched(self):
        score = title_similarity(
            "Bahir Dar Power Transmission Project, Lot 1",
            "Bahir Dar Power Transmission Project, Lot 2",
        )
        self.assertLess(score, 0.85)
        self.assertGreaterEqual(score, 0.75)

    def test_fund_type_preserves_basic_instruments(self):
        self.assertEqual(fund_type("Concessional loan"), "loan")
        self.assertEqual(fund_type("Grant and technical assistance"), "grant")
        self.assertEqual(fund_type("Equity investment"), "equity")

    def test_match_review_queue_exposes_qualifier_conflicts(self):
        def record(key, title):
            source, record_id = key.split(":", 1)
            return {
                "_record_key": key, "source_db": source, "record_id": record_id,
                "project_name": title, "amount_value": 100, "price_basis": "nominal_usd",
                "amount_measure": "loan_commitment", "fund_type": "loan",
                "sector_harmonized": "energy",
            }
        records = [
            record("codf:1", "Bui Hydropower Project Loan 1"),
            record("cla:2", "Bui Hydropower Project Loan 2"),
        ]
        candidates = [{
            "candidate_id": "MC-1", "left_record_key": "codf:1",
            "right_record_key": "cla:2", "country_iso3": "GHA",
            "year": 2012, "similarity": 0.84, "status": "needs_review",
        }]
        queue = build_match_review_queue(candidates, records)
        self.assertEqual(queue[0]["review_hint"], "qualifier_conflict_check_separate_projects")
        self.assertEqual(queue[0]["suggested_decision"], "different_project")
        self.assertEqual(queue[0]["suggestion_confidence"], "high")

    def test_zero_mad_groups_are_not_overinterpreted(self):
        records = []
        for index, amount in enumerate([100] * 10 + [1_000_000_000]):
            records.append({
                "_record_key": f"aiddata:{index}", "source_db": "aiddata",
                "record_id": str(index), "country_iso3": "ETH", "year": 2010,
                "project_name": f"Project {index}", "amount_value": amount,
                "amount_unit": "USD", "price_basis": "constant_2023_usd",
                "amount_measure": "commitment", "is_outlier": False,
            })
        outliers = detect_amount_outliers(records)
        self.assertEqual(len(records), 11)
        self.assertEqual(len(outliers), 0)

    def test_rank_correlations_handle_order_and_ties(self):
        self.assertAlmostEqual(spearman_correlation([1, 2, 3], [10, 20, 30]), 1)
        self.assertAlmostEqual(kendall_tau_b([1, 2, 3], [30, 20, 10]), -1)
        tied = kendall_tau_b([1, 1, 2], [1, 2, 3])
        self.assertIsNotNone(tied)
        self.assertGreater(tied, 0)

    def test_multiple_mean_breaks_find_clear_level_shift(self):
        years = list(range(2000, 2016))
        fit = fit_multiple_mean_breaks(years, [1.0] * 8 + [10.0] * 8)
        self.assertIsNotNone(fit)
        self.assertEqual(fit["break_indices"], [8])
        self.assertGreater(fit["bic_improvement"], 10)

    def test_lineage_flags_related_compilations(self):
        self.assertEqual(lineage_classification("codf", "cla"), "likely_shared_lineage")
        self.assertEqual(lineage_classification("aiddata", "chapo"), "documented_cross_reference_overlap")
        self.assertEqual(lineage_classification("codf", "aiddata"), "distinct_source_comparison")

    def test_reviewed_same_project_links_are_applied(self):
        records = [
            {"_record_key": "codf:1", "project_match_id": "SRC-1", "match_status": "needs_review", "match_confidence": .8},
            {"_record_key": "cla:2", "project_match_id": "SRC-2", "match_status": "needs_review", "match_confidence": .8},
        ]
        candidates = [{"candidate_id": "MC-1", "left_record_key": "codf:1", "right_record_key": "cla:2", "status": "needs_review", "review_decision": ""}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["candidate_id", "review_decision", "review_notes", "reviewed_at"])
                writer.writeheader()
                writer.writerow({"candidate_id": "MC-1", "review_decision": "same_project", "review_notes": "verified", "reviewed_at": "2026-08-12"})
            applied = apply_review_decisions(records, candidates, path)
        self.assertEqual(applied[0]["application_status"], "applied")
        self.assertEqual(records[0]["project_match_id"], records[1]["project_match_id"])
        self.assertEqual(records[0]["match_status"], "human_confirmed")

    def test_direct_reference_pairs_are_not_auto_bridged_by_generic_titles(self):
        def record(key, title, direct_refs):
            source, _ = key.split(":", 1)
            return {
                "_record_key": key, "_direct_refs": direct_refs,
                "source_db": source, "country_iso3": "NER", "year": 2011,
                "project_name": title, "project_match_id": f"SRC-{key}",
                "match_status": "unmatched", "match_confidence": 0,
                "candidate_count": 0,
            }

        records = [
            record("aiddata:21273", "China donates Anti-Malarial Medicine to Niger (June)", ["chapo:21273"]),
            record("chapo:21273", "China donated anti-Malarial medicine to Niger (june)", ["aiddata:21273"]),
            record("aiddata:58576", "China Donates Anti-malarial Medicine to Niger (December)", ["chapo:58576"]),
            record("chapo:58576", "China donated anti-Malarial medicine to Niger", ["aiddata:58576"]),
        ]

        apply_matching(records)
        by_key = {row["_record_key"]: row for row in records}
        self.assertEqual(by_key["aiddata:21273"]["project_match_id"], by_key["chapo:21273"]["project_match_id"])
        self.assertEqual(by_key["aiddata:58576"]["project_match_id"], by_key["chapo:58576"]["project_match_id"])
        self.assertNotEqual(by_key["aiddata:21273"]["project_match_id"], by_key["chapo:58576"]["project_match_id"])

    def test_conservative_review_only_auto_applies_strong_evidence(self):
        base = {
            "candidate_id": "MC-1", "left_source": "codf", "left_record_id": "A.1",
            "right_source": "cla", "right_record_id": "A.2", "country_iso3": "GHA",
            "year": "2010", "similarity": "0.82", "left_title": "Project Loan 1",
            "right_title": "Project Loan 2", "left_fund_type": "loan",
            "right_fund_type": "loan", "left_sector": "energy", "right_sector": "energy",
            "amount_ratio_if_comparable": "1", "review_hint": "qualifier_conflict_check_separate_projects",
        }
        conflict = recommend(base)
        self.assertEqual(conflict["review_decision"], "different_project")
        self.assertEqual(conflict["auto_apply"], "true")
        ambiguous = recommend({**base, "review_hint": "title_similarity_check_same_project", "amount_ratio_if_comparable": ""})
        self.assertEqual(ambiguous["review_decision"], "uncertain")
        self.assertEqual(ambiguous["auto_apply"], "false")


if __name__ == "__main__":
    unittest.main()
