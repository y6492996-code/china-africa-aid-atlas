#!/usr/bin/env python3
"""Build the research-ready China-Africa data panels.

The pipeline deliberately keeps every database statistically independent.
Project/event sources are standardized into a source-preserving master table;
macro sources are joined only at the country-year panel stage. Monetary fields
retain a price-basis label and are never added across databases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from statistics import median
from typing import Iterable


START_YEAR = 2000
END_YEAR = 2024
MATCH_REVIEW_THRESHOLD = 0.75
MATCH_AUTO_THRESHOLD = 0.85


PROJECT_COLUMNS = [
    "project_match_id", "source_db", "record_id", "country_iso3",
    "country_name_en", "country_name_zh", "panel_eligible", "year",
    "year_basis", "project_name", "description", "amount_value",
    "amount_unit", "price_basis", "amount_measure", "metric_value",
    "metric_unit", "flow_type_raw", "fund_type", "sector_raw",
    "sector_harmonized", "sector_mapping_method", "latitude", "longitude",
    "geo_precision", "is_regional", "is_framework", "amount_missing",
    "is_estimated", "is_imputed", "is_outlier", "match_status",
    "match_confidence", "candidate_count", "source_file",
]


MATCH_REVIEW_COLUMNS = [
    "candidate_id", "country_iso3", "year", "similarity", "review_hint",
    "suggested_decision", "suggestion_confidence", "suggestion_reason",
    "left_source", "left_record_id", "left_title", "left_amount_value",
    "left_price_basis", "left_fund_type", "left_sector",
    "right_source", "right_record_id", "right_title", "right_amount_value",
    "right_price_basis", "right_fund_type", "right_sector",
    "amount_ratio_if_comparable", "review_decision", "review_notes",
]


OUTLIER_COLUMNS = [
    "outlier_id", "record_key", "source_db", "record_id", "country_iso3",
    "year", "project_name", "amount_value", "amount_unit", "price_basis",
    "amount_measure", "detection_method", "robust_z", "group_known_count",
    "group_median_amount", "review_decision", "review_notes",
]


QUALITY_COLUMNS = [
    "source_db", "source_label", "primary_value_field", "total_records",
    "panel_eligible_records", "value_known_count", "value_missing_count",
    "value_missing_rate", "country_known_rate", "year_known_rate",
    "title_known_rate", "sector_classified_rate", "fund_type_classified_rate",
    "estimated_count", "regional_count", "framework_count",
    "outlier_candidate_count", "needs_match_review_count",
]


MISSINGNESS_COLUMNS = [
    "variable", "panel_rows", "observed_count", "missing_count",
    "missing_rate", "zero_count", "negative_count", "countries_with_data",
    "years_with_data", "first_observed_year", "last_observed_year",
]


DESCRIPTIVE_COLUMNS = [
    "metric_id", "metric_label", "category", "unit", "price_basis",
    "amount_measure", "panel_rows", "observed_count", "missing_count",
    "missing_rate", "countries_with_data", "years_with_data", "mean",
    "median", "std_dev", "p25", "p75", "minimum", "maximum",
    "zero_count", "negative_count",
]


ANNUAL_TREND_COLUMNS = [
    "metric_id", "metric_label", "year", "observed_country_count",
    "record_count", "total_value", "mean_value", "median_value", "unit",
    "price_basis", "amount_measure", "source_first_observed_year",
    "source_last_observed_year", "year_complete", "coverage_status",
    "coverage_note",
]


MATCH_CANDIDATE_COLUMNS = [
    "candidate_id", "left_record_key", "right_record_key", "country_iso3",
    "year", "similarity", "status", "review_decision", "method",
    "left_title", "right_title",
]


LONG_SOURCE_COLUMNS = [
    "panel_id", "iso3", "country_name_en", "year", "source",
    "source_label", "amount_usd", "record_count", "amount_known_count",
    "price_basis", "amount_measure",
]


LONG_FUNDTYPE_COLUMNS = [
    "panel_id", "iso3", "country_name_en", "year", "source", "fund_type",
    "amount_usd", "amount_known_count", "price_basis",
]


DATA_DICTIONARY_COLUMNS = [
    "table", "column", "module", "description", "unit", "key_role",
    "missing_rule",
]


COUNTRY_SUMMARY_COLUMNS = [
    "metric_id", "metric_label", "iso3", "country_name_en",
    "observed_year_count", "first_observed_year", "last_observed_year",
    "total_value", "annual_mean", "annual_median", "rank_within_metric",
    "unit", "price_basis", "aggregation_caveat",
]


CORRELATION_COLUMNS = [
    "scope", "left_metric", "left_label", "right_metric", "right_label",
    "paired_observations", "shared_country_years", "spearman_rho",
    "kendall_tau_b", "left_price_basis", "right_price_basis",
    "comparability_tier", "interpretation_limit",
]


BREAK_MODEL_COLUMNS = [
    "metric_id", "metric_label", "series_variant", "start_year", "end_year",
    "observations", "min_segment_length", "selected_segments", "break_count",
    "break_years", "bic", "no_break_bic", "bic_improvement", "transform",
    "method", "interpretation_limit",
]


BREAKPOINT_COLUMNS = [
    "metric_id", "metric_label", "series_variant", "break_number", "break_year",
    "pre_start_year", "pre_end_year", "post_start_year", "post_end_year",
    "pre_mean_original", "post_mean_original", "relative_change",
    "bic_improvement", "evidence_strength", "unit", "price_basis",
]


ROBUSTNESS_COLUMNS = [
    "scope", "left_metric", "right_metric", "lineage_classification",
    "baseline_n", "robust_n", "baseline_spearman", "robust_spearman",
    "delta_spearman", "baseline_kendall", "robust_kendall", "delta_kendall",
    "flagged_outliers_removed", "stability", "interpretation_limit",
]


REVIEW_APPLIED_COLUMNS = [
    "candidate_id", "left_record_key", "right_record_key", "review_decision",
    "review_notes", "reviewed_at", "application_status",
]


MATCH_GROUP_COLUMNS = [
    "project_match_id", "member_count", "source_count", "sources",
    "country_iso3", "year", "member_record_keys", "group_basis",
]


PROJECT_ENTITY_COLUMNS = [
    "project_entity_id", "country_iso3", "year", "canonical_title",
    "member_count", "source_count", "sources", "member_record_keys",
    "match_basis", "amount_policy",
]


SOURCE_META = {
    "aiddata": {"label": "AidData", "price_basis": "constant_2023_usd", "measure": "commitment"},
    "codf": {"label": "CODF", "price_basis": "nominal_usd", "measure": "loan_commitment"},
    "cla": {"label": "CLA", "price_basis": "nominal_usd", "measure": "loan_commitment"},
    "cancel": {"label": "Debt cancellation", "price_basis": "nominal_usd", "measure": "debt_cancellation"},
    "restruct": {"label": "Debt restructuring", "price_basis": "nominal_usd", "measure": "debt_restructuring"},
    "cofi": {"label": "COFI", "price_basis": "nominal_usd", "measure": "investment"},
    "cgef": {"label": "CGEF", "price_basis": "nominal_usd", "measure": "loan_commitment"},
    "cgp": {"label": "CGP", "price_basis": "not_applicable", "measure": "capacity"},
    "chapo": {"label": "CHAPO", "price_basis": "constant_2021_usd", "measure": "commitment"},
}


ANALYSIS_METRICS = [
    {"id": "aiddata", "label": "AidData commitments", "column": "aiddata_total_usd", "count": "aiddata_count", "category": "project_finance", "unit": "USD", "price_basis": "constant_2023_usd", "measure": "commitment"},
    {"id": "codf", "label": "CODF loan commitments", "column": "codf_total_usd", "count": "codf_count", "category": "project_finance", "unit": "USD", "price_basis": "nominal_usd", "measure": "loan_commitment"},
    {"id": "cla", "label": "CLA loan commitments", "column": "cla_total_usd", "count": "cla_count", "category": "project_finance", "unit": "USD", "price_basis": "nominal_usd", "measure": "loan_commitment"},
    {"id": "cancel", "label": "Debt cancellation", "column": "cancel_total_usd", "count": "cancel_count", "category": "debt", "unit": "USD", "price_basis": "nominal_usd", "measure": "debt_cancellation"},
    {"id": "restruct", "label": "Debt restructuring", "column": "restruct_total_usd", "count": "restruct_count", "category": "debt", "unit": "USD", "price_basis": "nominal_usd", "measure": "debt_restructuring"},
    {"id": "cofi", "label": "COFI investment", "column": "cofi_total_usd", "count": "cofi_count", "category": "investment", "unit": "USD", "price_basis": "nominal_usd", "measure": "investment"},
    {"id": "cgef", "label": "CGEF loan commitments", "column": "cgef_total_usd", "count": "cgef_count", "category": "project_finance", "unit": "USD", "price_basis": "nominal_usd", "measure": "loan_commitment"},
    {"id": "chapo", "label": "CHAPO commitments", "column": "chapo_total_usd", "count": "chapo_count", "category": "project_finance", "unit": "USD", "price_basis": "constant_2021_usd", "measure": "commitment"},
    {"id": "aidexports", "label": "Aid exports", "column": "aidexports_total_usd", "count": "aidexports_month_count", "category": "trade_proxy", "unit": "USD", "price_basis": "nominal_usd", "measure": "monthly_exports_annual_sum"},
    {"id": "fdi_stock", "label": "FDI stock", "column": "fdi_stock_usd", "count": "", "category": "investment", "unit": "USD", "price_basis": "nominal_usd", "measure": "stock"},
    {"id": "fdi_flow", "label": "FDI flow", "column": "fdi_flow_usd", "count": "", "category": "investment", "unit": "USD", "price_basis": "nominal_usd", "measure": "flow"},
    {"id": "ihme", "label": "IHME DAH disbursement", "column": "ihme_disbursement_2023_usd_million", "count": "ihme_observation_count", "category": "health", "unit": "USD million", "price_basis": "constant_2023_usd", "measure": "disbursement"},
    {"id": "china_eu_finance", "label": "China development finance", "column": "china_eu_dfchina_2017_usd", "count": "", "category": "project_finance", "unit": "USD", "price_basis": "constant_2017_usd", "measure": "development_finance"},
    {"id": "cgp_capacity", "label": "CGP capacity", "column": "cgp_capacity_mw", "count": "cgp_count", "category": "energy", "unit": "MW", "price_basis": "not_applicable", "measure": "capacity"},
]


CORRELATION_METRICS = {"aiddata", "codf", "cla", "cgef", "chapo", "china_eu_finance"}


AMOUNT_SOURCES = ["aiddata", "codf", "cla", "cancel", "restruct", "cofi", "cgef", "chapo"]


def read_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(path: Path, rows: Iterable[dict], columns: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
            count += 1
    return count


def parse_number(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.casefold() in {"na", "nan", "none", ".", "tbd"}:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def parse_year(value) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def truthy(value) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y"}


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:14].upper()}"


def norm_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    value = value.replace("&", " and ").replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value).strip()


STOPWORDS = {
    "the", "a", "an", "and", "of", "for", "to", "in", "on", "project",
    "program", "programme", "china", "chinese", "africa", "government",
}


def title_tokens(value: str) -> set[str]:
    return {token for token in norm_text(value).split() if len(token) >= 3 and token not in STOPWORDS}


def title_qualifiers(value: str) -> set[str]:
    """Keep phase/lot/loan/unit identifiers that distinguish sibling projects."""
    text = norm_text(value)
    qualifiers = set()
    for marker, identifier in re.findall(
        r"\b(phase|lot|loan|unit|package|section|stage)\s*(\d+|[ivx]+|[a-z])\b", text
    ):
        qualifiers.add(f"{marker}:{identifier}")
    return qualifiers


def title_similarity(left: str, right: str) -> float:
    a, b = norm_text(left), norm_text(right)
    if not a or not b:
        return 0.0
    at, bt = title_tokens(a), title_tokens(b)
    if not at or not bt or not (at & bt):
        return 0.0
    jaccard = len(at & bt) / len(at | bt)
    sequence = SequenceMatcher(None, a, b).ratio()
    containment = len(at & bt) / min(len(at), len(bt))
    score = max(jaccard, sequence, containment * 0.92)
    left_qualifiers, right_qualifiers = title_qualifiers(left), title_qualifiers(right)
    if left_qualifiers and right_qualifiers and left_qualifiers != right_qualifiers:
        score = min(score, MATCH_AUTO_THRESHOLD - 0.01)
    return round(score, 4)


SECTOR_RULES = [
    ("health", {"120", "health", "medical", "hospital", "clinic", "卫生", "医疗"}),
    ("education", {"110", "education", "school", "university", "教育"}),
    ("water_sanitation", {"140", "water", "sanitation", "waste", "供水", "卫生设施", "废物"}),
    ("transport", {"210", "transport", "rail", "road", "airport", "port", "交通", "铁路", "公路", "港口"}),
    ("communications", {"220", "communication", "telecom", "ict", "通信", "信息"}),
    ("energy", {"230", "energy", "power", "electric", "hydro", "solar", "coal", "gas", "能源", "电力", "水电"}),
    ("finance", {"240", "bank", "financial", "finance", "金融"}),
    ("industry_mining", {"250", "320", "industry", "mining", "construction", "工业", "采矿", "建筑"}),
    ("agriculture", {"310", "agriculture", "forestry", "fishing", "农业", "林业", "渔业"}),
    ("government", {"150", "public administration", "government", "治理", "公共管理"}),
    ("environment", {"410", "environment", "climate", "环境", "气候"}),
    ("debt", {"600", "debt", "债务"}),
    ("humanitarian", {"720", "730", "740", "emergency", "relief", "disaster", "紧急", "救灾"}),
    ("multisector", {"430", "multisector", "多部门"}),
]


def harmonize_sector(raw: str, title: str = "") -> tuple[str, str]:
    raw_norm = norm_text(raw)
    text = f" {raw_norm} {norm_text(title)} "
    for label, keywords in SECTOR_RULES:
        if any((keyword.isdigit() and raw_norm == keyword) or norm_text(keyword) in text for keyword in keywords):
            return label, "rule_based_v1"
    return ("unspecified" if not raw_norm else "other"), "rule_based_v1"


def fund_type(value: str, fallback: str = "unspecified") -> str:
    text = norm_text(value)
    if any(word in text for word in ["grant", "donation", "technical assistance", "scholarship", "赠款", "捐赠", "援助"]):
        return "grant"
    if any(word in text for word in ["debt forgiveness", "debt cancellation", "免除", "减免"]):
        return "debt_relief"
    if any(word in text for word in ["equity", "fdi", "股权"]):
        return "equity"
    if any(word in text for word in ["loan", "credit", "debt", "贷款", "债权"]):
        return "loan"
    return fallback


@dataclass
class CountryReference:
    by_iso: dict[str, dict]
    by_name: dict[str, str]
    sovereign: list[str]


def load_country_reference(data_dir: Path) -> CountryReference:
    by_iso: dict[str, dict] = {}
    by_name: dict[str, str] = {}
    sovereign: list[str] = []
    for row in read_rows(data_dir / "fdi_africa_metadata.csv"):
        iso = (row.get("ISO_A3") or "").strip().upper()
        if not iso or iso == "SDN-H":
            continue
        record = {
            "iso3": iso,
            "name_en": (row.get("Country_EN") or iso).strip(),
            "name_zh": (row.get("Country_CN") or row.get("Country_EN") or iso).strip(),
            "sovereign": truthy(row.get("Is_Sovereign")),
        }
        by_iso[iso] = record
        by_name[norm_text(record["name_en"])] = iso
        by_name[norm_text(record["name_zh"])] = iso
        if record["sovereign"]:
            sovereign.append(iso)

    aliases = {
        "swaziland": "SWZ", "eswatini": "SWZ", "the gambia": "GMB", "gambia": "GMB",
        "cabo verde": "CPV", "cape verde": "CPV", "ivory coast": "CIV", "cote d ivoire": "CIV",
        "republic of the congo": "COG", "congo republic": "COG", "congo brazzaville": "COG",
        "democratic republic of the congo": "COD", "dr congo": "COD", "drc": "COD",
        "united republic of tanzania": "TZA", "tanzania": "TZA",
        "sao tome and principe": "STP", "regional africa": "AFR", "regional": "AFR",
        "区域性": "AFR",
    }
    for name, iso in aliases.items():
        by_name[norm_text(name)] = iso
    sovereign.sort()
    if len(sovereign) != 54:
        raise ValueError(f"Expected 54 sovereign African countries, found {len(sovereign)}")
    return CountryReference(by_iso, by_name, sovereign)


def resolve_country(ref: CountryReference, value: str, kind: str = "name") -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if kind == "iso3":
        return raw.upper()
    return ref.by_name.get(norm_text(raw), "")


def base_record(
    ref: CountryReference, source: str, source_file: str, record_id: str,
    iso: str, year: int | None, year_basis: str, title: str,
) -> dict:
    country = ref.by_iso.get(iso, {})
    record_key = f"{source}:{record_id}"
    return {
        "project_match_id": stable_id("SRC", record_key),
        "source_db": source,
        "record_id": record_id,
        "country_iso3": iso,
        "country_name_en": country.get("name_en", "Regional Africa" if iso == "AFR" else ""),
        "country_name_zh": country.get("name_zh", "区域性" if iso == "AFR" else ""),
        "panel_eligible": iso in ref.sovereign and year is not None and START_YEAR <= year <= END_YEAR,
        "year": year if year is not None else "",
        "year_basis": year_basis,
        "project_name": str(title or "").strip(),
        "description": "",
        "amount_value": "",
        "amount_unit": "USD",
        "price_basis": SOURCE_META[source]["price_basis"],
        "amount_measure": SOURCE_META[source]["measure"],
        "metric_value": "",
        "metric_unit": "",
        "flow_type_raw": "",
        "fund_type": "unspecified",
        "sector_raw": "",
        "sector_harmonized": "unspecified",
        "sector_mapping_method": "rule_based_v1",
        "latitude": "",
        "longitude": "",
        "geo_precision": "country",
        "is_regional": iso == "AFR",
        "is_framework": False,
        "amount_missing": True,
        "is_estimated": False,
        "is_imputed": False,
        "is_outlier": False,
        "match_status": "unmatched",
        "match_confidence": 0,
        "candidate_count": 0,
        "source_file": source_file,
        "_record_key": record_key,
        "_direct_refs": [],
    }


def set_amount(record: dict, value: float | None, multiplier: float = 1.0) -> None:
    record["amount_value"] = round(value * multiplier, 6) if value is not None else ""
    record["amount_missing"] = value is None


def project_rows(data_dir: Path, ref: CountryReference) -> list[dict]:
    output: list[dict] = []

    filename = "aiddata_africa_clean.csv"
    for row in read_rows(data_dir / filename):
        iso = resolve_country(ref, row.get("Country_of_Activity", ""))
        record = base_record(ref, "aiddata", filename, row.get("AidData_Record_ID", ""), iso,
                             parse_year(row.get("Commitment_Year")), "commitment_year", row.get("Title", ""))
        set_amount(record, parse_number(row.get("Clean_Amount_USD")))
        record["flow_type_raw"] = row.get("Flow_Type", "")
        record["fund_type"] = fund_type(record["flow_type_raw"])
        record["sector_raw"] = row.get("Sector_Code", "")
        record["sector_harmonized"], record["sector_mapping_method"] = harmonize_sector(record["sector_raw"], record["project_name"])
        record["is_framework"] = False
        output.append(record)

    filename = "bu_codf_africa_clean.csv"
    for row in read_rows(data_dir / filename):
        iso = "AFR" if truthy(row.get("Is_Regional")) else resolve_country(ref, row.get("国家", ""))
        record = base_record(ref, "codf", filename, row.get("贷款号", ""), iso,
                             parse_year(row.get("年份")), "loan_commitment_year", row.get("项目", ""))
        set_amount(record, parse_number(row.get("Clean_Amount_USD")))
        record["flow_type_raw"] = "Loan"
        record["fund_type"] = "loan"
        record["sector_raw"] = row.get("行业", "") or row.get("能源类型", "")
        record["sector_harmonized"], record["sector_mapping_method"] = harmonize_sector(record["sector_raw"], record["project_name"])
        output.append(record)

    filename = "cla_africa_clean.csv"
    for row in read_rows(data_dir / filename):
        iso = "AFR" if (row.get("country_iso") or "").strip().upper() == "AFR" else resolve_country(ref, row.get("country_en_standard", ""))
        record = base_record(ref, "cla", filename, row.get("BU ID", ""), iso,
                             parse_year(row.get("Year")), "loan_commitment_year", row.get("Project Name", ""))
        set_amount(record, parse_number(row.get("Loan_USD_M")), 1_000_000)
        record["flow_type_raw"] = "Loan"
        record["fund_type"] = "loan"
        record["sector_raw"] = row.get("Sector", "") or row.get("Energy Source", "")
        record["sector_harmonized"], record["sector_mapping_method"] = harmonize_sector(record["sector_raw"], record["project_name"])
        output.append(record)

    filename = "cancellation_africa_clean.csv"
    for row in read_rows(data_dir / filename):
        iso = resolve_country(ref, row.get("ISO_A3", ""), "iso3")
        record = base_record(ref, "cancel", filename, row.get("Record_ID", ""), iso,
                             parse_year(row.get("Year")), "agreement_year", "Debt cancellation")
        set_amount(record, parse_number(row.get("Cancel_Amount_USD_Mn")), 1_000_000)
        record["flow_type_raw"] = "Debt cancellation"
        record["fund_type"] = "debt_relief"
        record["sector_raw"] = "Debt"
        record["sector_harmonized"] = "debt"
        record["is_estimated"] = truthy(row.get("Is_Estimated"))
        output.append(record)

    filename = "restructuring_africa_clean.csv"
    for row in read_rows(data_dir / filename):
        iso = resolve_country(ref, row.get("ISO_A3", ""), "iso3")
        record = base_record(ref, "restruct", filename, row.get("Record_ID", ""), iso,
                             parse_year(row.get("Year_Numeric")), "agreement_year", row.get("Related_Projects") or row.get("Description", ""))
        set_amount(record, parse_number(row.get("Restructure_Amount_USD_Mn")), 1_000_000)
        record["description"] = row.get("Description", "")
        record["flow_type_raw"] = row.get("Type_of_Finance_Full", "") or "Debt restructuring"
        record["fund_type"] = "loan"
        record["sector_raw"] = "Debt"
        record["sector_harmonized"] = "debt"
        record["is_estimated"] = truthy(row.get("Is_Estimated"))
        output.append(record)

    filename = "cofi_africa_clean.csv"
    for row in read_rows(data_dir / filename):
        iso = resolve_country(ref, row.get("country_iso3c", ""), "iso3")
        base_id = row.get("unique_id", "")
        events = []
        debt_amount = parse_number(row.get("debt_investment_amount_USD"))
        equity_amounts = [parse_number(row.get("equity_investor_amount_1_USD")), parse_number(row.get("equity_investor_amount_2_USD"))]
        equity_amount = sum(value for value in equity_amounts if value is not None) if any(value is not None for value in equity_amounts) else None
        if parse_year(row.get("debt_investment_year")) or debt_amount is not None:
            events.append(("debt", parse_year(row.get("debt_investment_year")), debt_amount, "loan"))
        if parse_year(row.get("equity_investment_year")) or equity_amount is not None:
            events.append(("equity", parse_year(row.get("equity_investment_year")), equity_amount, "equity"))
        if not events:
            events.append(("total", parse_year(row.get("commissioning_year")), parse_number(row.get("total_investment_amount_USD")), fund_type(row.get("investment_type_standard", ""), "unspecified")))
        for event_name, year, amount, event_fund in events:
            record = base_record(ref, "cofi", filename, f"{base_id}:{event_name}", iso, year,
                                 f"{event_name}_investment_year" if event_name != "total" else "commissioning_year_fallback", row.get("power_plant_name", ""))
            set_amount(record, amount)
            record["flow_type_raw"] = row.get("investment_type_standard", "")
            record["fund_type"] = event_fund
            record["sector_raw"] = row.get("primary_fuel", "") or "Energy"
            record["sector_harmonized"] = "energy"
            capacity = parse_number(row.get("installed_capacity"))
            record["metric_value"] = "" if capacity is None else capacity
            record["metric_unit"] = "MW"
            record["latitude"] = row.get("latitude", "")
            record["longitude"] = row.get("longitude", "")
            record["geo_precision"] = "coordinates" if record["latitude"] and record["longitude"] else "subnational"
            output.append(record)

    filename = "CGEF_Africa_2024_Cleaned.csv"
    for row in read_rows(data_dir / filename):
        iso = resolve_country(ref, row.get("国家", ""))
        record = base_record(ref, "cgef", filename, row.get("贷款号", ""), iso,
                             parse_year(row.get("年份")), "loan_commitment_year", row.get("项目名称", ""))
        set_amount(record, parse_number(row.get("贷款金额（百万美元）")), 1_000_000)
        record["flow_type_raw"] = "Loan"
        record["fund_type"] = "loan"
        record["sector_raw"] = row.get("能源类型", "") or row.get("能源次级部门", "")
        record["sector_harmonized"] = "energy"
        output.append(record)

    filename = "CGP_Africa_2025_Cleaned.csv"
    for row in read_rows(data_dir / filename):
        iso = resolve_country(ref, row.get("国家", ""))
        record = base_record(ref, "cgp", filename, row.get("CGP ID", ""), iso,
                             parse_year(row.get("融资年份")) or parse_year(row.get("投产年份")),
                             "financing_year" if parse_year(row.get("融资年份")) else "commissioning_year_fallback",
                             row.get("发电厂名称", "") or row.get("发电机组名称", ""))
        record["amount_missing"] = True
        capacity = parse_number(row.get("产能 （兆瓦）"))
        record["metric_value"] = "" if capacity is None else capacity
        record["metric_unit"] = "MW"
        record["flow_type_raw"] = row.get("投资类型", "")
        record["fund_type"] = "equity" if truthy(row.get("外国直接投资？")) else ("loan" if truthy(row.get("涉及中国开发性金融机构?")) else "unspecified")
        record["sector_raw"] = row.get("技术", "")
        record["sector_harmonized"] = "energy"
        record["geo_precision"] = "subnational" if row.get("州/省") else "country"
        direct_ref = (row.get("BU_ID") or "").strip()
        if direct_ref:
            record["_direct_refs"].extend([f"cla:{direct_ref}", f"cgef:{direct_ref}"])
        output.append(record)

    filename = "chapo_africa_clean.csv"
    for row in read_rows(data_dir / filename):
        iso = resolve_country(ref, row.get("country_iso", ""), "iso3")
        record = base_record(ref, "chapo", filename, row.get("AidData_ID", ""), iso,
                             parse_year(row.get("Commitment_Year")), "commitment_year", row.get("New_Short_Title") or row.get("Short_Title", ""))
        set_amount(record, parse_number(row.get("Amount_USD")))
        record["description"] = row.get("Description", "")
        record["flow_type_raw"] = row.get("Flow_Type", "")
        record["fund_type"] = fund_type(record["flow_type_raw"], "grant")
        record["sector_raw"] = "Health"
        record["sector_harmonized"] = "health"
        direct_ref = (row.get("AidData_ID") or "").strip()
        if direct_ref:
            record["_direct_refs"].append(f"aiddata:{direct_ref}")
        output.append(record)

    return output


class UnionFind:
    def __init__(self, keys: Iterable[str]):
        self.parent = {key: key for key in keys}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def apply_matching(records: list[dict]) -> list[dict]:
    by_key = {record["_record_key"]: record for record in records}
    uf = UnionFind(by_key)
    direct_pairs: set[tuple[str, str]] = set()
    for record in records:
        for target in record["_direct_refs"]:
            if target in by_key and target != record["_record_key"]:
                pair = tuple(sorted((record["_record_key"], target)))
                direct_pairs.add(pair)
                uf.union(*pair)

    blocks: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for record in records:
        if record["country_iso3"] in {"", "AFR"} or not record["project_name"] or not isinstance(record["year"], int):
            continue
        blocks[(record["country_iso3"], record["year"])].append(record)

    candidates: list[dict] = []
    for (iso, year), block in blocks.items():
        token_index: dict[str, list[dict]] = defaultdict(list)
        for record in block:
            for token in title_tokens(record["project_name"]):
                token_index[token].append(record)
        seen_pairs: set[tuple[str, str]] = set()
        for left in block:
            possible: dict[str, dict] = {}
            for token in title_tokens(left["project_name"]):
                for right in token_index[token]:
                    if right["source_db"] != left["source_db"]:
                        possible[right["_record_key"]] = right
            for right in possible.values():
                pair = tuple(sorted((left["_record_key"], right["_record_key"])))
                if pair in seen_pairs or pair in direct_pairs:
                    continue
                seen_pairs.add(pair)
                score = title_similarity(left["project_name"], right["project_name"])
                if score < MATCH_REVIEW_THRESHOLD:
                    continue
                status = "auto_high_confidence" if score >= MATCH_AUTO_THRESHOLD else "needs_review"
                candidates.append({
                    "candidate_id": stable_id("MC", *pair), "left_record_key": pair[0],
                    "right_record_key": pair[1], "country_iso3": iso, "year": year,
                    "similarity": score, "status": status, "review_decision": "",
                    "method": "normalized_title_sequence_token_v1",
                    "left_title": by_key[pair[0]]["project_name"],
                    "right_title": by_key[pair[1]]["project_name"],
                })

    candidate_by_key: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        candidate_by_key[candidate["left_record_key"]].append(candidate)
        candidate_by_key[candidate["right_record_key"]].append(candidate)

    # Auto-union only reciprocal unique best matches above the requested 0.85 threshold.
    best: dict[str, tuple[float, str, int]] = {}
    for key, items in candidate_by_key.items():
        ranked = sorted(items, key=lambda item: item["similarity"], reverse=True)
        top = ranked[0]
        other = top["right_record_key"] if top["left_record_key"] == key else top["left_record_key"]
        best[key] = (top["similarity"], other, len([item for item in ranked if item["similarity"] == top["similarity"]]))
    direct_members = {member for pair in direct_pairs for member in pair}
    for key, (score, other, ties) in best.items():
        other_best = best.get(other)
        # A direct source cross-reference is stronger evidence than title
        # similarity.  Do not let a record that already belongs to a direct
        # pair auto-bridge into another referenced pair: short/generic titles
        # can otherwise collapse distinct dated events into one entity.
        if key in direct_members or other in direct_members:
            continue
        if score >= MATCH_AUTO_THRESHOLD and ties == 1 and other_best and other_best[1] == key and other_best[2] == 1:
            uf.union(key, other)

    groups: dict[str, list[str]] = defaultdict(list)
    for key in by_key:
        groups[uf.find(key)].append(key)
    for members in groups.values():
        if len(members) <= 1:
            continue
        group_id = stable_id("PM", *sorted(members))
        direct_group = any(left in members and right in members for left, right in direct_pairs)
        for key in members:
            record = by_key[key]
            record["project_match_id"] = group_id
            record["match_status"] = "direct_reference" if direct_group else "auto_high_confidence"
            record["match_confidence"] = 1 if direct_group else max((item["similarity"] for item in candidate_by_key.get(key, [])), default=0)

    for key, record in by_key.items():
        items = candidate_by_key.get(key, [])
        record["candidate_count"] = len(items)
        if record["match_status"] == "unmatched" and items:
            record["match_status"] = "needs_review"
            record["match_confidence"] = max(item["similarity"] for item in items)

    candidates.extend({
        "candidate_id": stable_id("MC", left, right), "left_record_key": left,
        "right_record_key": right, "country_iso3": by_key[left]["country_iso3"],
        "year": by_key[left]["year"], "similarity": 1, "status": "direct_reference",
        "review_decision": "confirmed_by_source_id", "method": "source_cross_reference",
        "left_title": by_key[left]["project_name"], "right_title": by_key[right]["project_name"],
    } for left, right in sorted(direct_pairs))
    candidates.sort(key=lambda item: (-float(item["similarity"]), item["candidate_id"]))
    return candidates


def apply_review_decisions(records: list[dict], candidates: list[dict], decision_path: Path | None) -> list[dict]:
    """Apply reviewed same-project links while preserving all source records."""
    if decision_path is None or not decision_path.exists():
        return []
    by_key = {record["_record_key"]: record for record in records}
    candidate_by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    uf = UnionFind(by_key)
    existing_groups: dict[str, list[str]] = defaultdict(list)
    for record in records:
        existing_groups[record["project_match_id"]].append(record["_record_key"])
    for members in existing_groups.values():
        for member in members[1:]:
            uf.union(members[0], member)

    applied = []
    for decision in read_rows(decision_path):
        candidate_id = (decision.get("candidate_id") or "").strip()
        value = (decision.get("review_decision") or "").strip()
        candidate = candidate_by_id.get(candidate_id)
        status = "applied"
        if candidate is None:
            status = "candidate_not_found"
            left_key = f"{decision.get('left_source', '')}:{decision.get('left_record_id', '')}"
            right_key = f"{decision.get('right_source', '')}:{decision.get('right_record_id', '')}"
        else:
            left_key = candidate["left_record_key"]
            right_key = candidate["right_record_key"]
            if value not in {"same_project", "different_project", "uncertain"}:
                status = "invalid_decision"
            else:
                candidate["review_decision"] = value
                candidate["status"] = "reviewed"
                if value == "same_project":
                    uf.union(left_key, right_key)
        applied.append({
            "candidate_id": candidate_id, "left_record_key": left_key,
            "right_record_key": right_key, "review_decision": value,
            "review_notes": decision.get("review_notes", ""),
            "reviewed_at": decision.get("reviewed_at", ""), "application_status": status,
        })

    groups: dict[str, list[str]] = defaultdict(list)
    for key in by_key:
        groups[uf.find(key)].append(key)
    for members in groups.values():
        if len(members) <= 1:
            continue
        group_id = stable_id("PM", *sorted(members))
        for key in members:
            by_key[key]["project_match_id"] = group_id
            if any(
                row["application_status"] == "applied" and row["review_decision"] == "same_project"
                and key in {row["left_record_key"], row["right_record_key"]}
                for row in applied
            ):
                by_key[key]["match_status"] = "human_confirmed"
                by_key[key]["match_confidence"] = 1
    return applied


def build_match_groups(records: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["project_match_id"]].append(record)
    output = []
    for group_id, members in grouped.items():
        if len(members) <= 1:
            continue
        statuses = {member["match_status"] for member in members}
        basis = "human_confirmed" if "human_confirmed" in statuses else "direct_reference" if "direct_reference" in statuses else "automatic_high_confidence"
        output.append({
            "project_match_id": group_id, "member_count": len(members),
            "source_count": len({member["source_db"] for member in members}),
            "sources": "|".join(sorted({member["source_db"] for member in members})),
            "country_iso3": members[0]["country_iso3"], "year": members[0]["year"],
            "member_record_keys": "|".join(sorted(member["_record_key"] for member in members)),
            "group_basis": basis,
        })
    return sorted(output, key=lambda row: (row["country_iso3"], str(row["year"]), row["project_match_id"]))


def build_project_entity_index(records: list[dict]) -> list[dict]:
    """One row per matched entity, deliberately without a cross-source amount."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["project_match_id"]].append(record)
    output = []
    for entity_id, members in grouped.items():
        statuses = {member["match_status"] for member in members}
        basis = (
            "human_confirmed" if "human_confirmed" in statuses
            else "direct_reference" if "direct_reference" in statuses
            else "automatic_high_confidence" if len(members) > 1
            else "source_record"
        )
        canonical = max(members, key=lambda member: (len(member["project_name"]), member["_record_key"]))
        output.append({
            "project_entity_id": entity_id, "country_iso3": canonical["country_iso3"],
            "year": canonical["year"], "canonical_title": canonical["project_name"],
            "member_count": len(members), "source_count": len({member["source_db"] for member in members}),
            "sources": "|".join(sorted({member["source_db"] for member in members})),
            "member_record_keys": "|".join(sorted(member["_record_key"] for member in members)),
            "match_basis": basis,
            "amount_policy": "no_cross_source_amount_selected_or_summed",
        })
    return sorted(output, key=lambda row: (row["country_iso3"], str(row["year"]), row["project_entity_id"]))


def build_match_review_queue(candidates: list[dict], records: list[dict]) -> list[dict]:
    """Create a queue for every unresolved candidate that was not merged.

    A high title score alone does not guarantee an automatic match: reciprocal
    uniqueness and direct-reference safeguards can still prevent a union.  Any
    such unmerged candidate must remain visible for review instead of falling
    through the gap between candidate scoring and final entity assignment.
    """
    by_key = {record["_record_key"]: record for record in records}
    queue = []
    for candidate in candidates:
        if candidate["status"] in {"direct_reference", "reviewed"}:
            continue
        left = by_key[candidate["left_record_key"]]
        right = by_key[candidate["right_record_key"]]
        if left["project_match_id"] == right["project_match_id"]:
            continue
        candidate["status"] = "needs_review"
        left_qualifiers = title_qualifiers(left["project_name"])
        right_qualifiers = title_qualifiers(right["project_name"])
        if left_qualifiers and right_qualifiers and left_qualifiers != right_qualifiers:
            hint = "qualifier_conflict_check_separate_projects"
            suggested_decision = "different_project"
            suggestion_confidence = "high"
            suggestion_reason = "Conflicting lot, loan, phase, unit, package, section or stage identifiers."
        elif left["sector_harmonized"] != right["sector_harmonized"]:
            hint = "sector_conflict_check_context"
            suggested_decision = ""
            suggestion_confidence = "low"
            suggestion_reason = "Sector classifications conflict; inspect the project context."
        else:
            hint = "title_similarity_check_same_project"
            suggested_decision = ""
            suggestion_confidence = "low"
            suggestion_reason = "Title similarity alone is insufficient for an automatic decision."

        left_amount = parse_number(left["amount_value"])
        right_amount = parse_number(right["amount_value"])
        comparable = (
            left_amount is not None and right_amount not in {None, 0}
            and left["price_basis"] == right["price_basis"]
            and left["amount_measure"] == right["amount_measure"]
        )
        queue.append({
            "candidate_id": candidate["candidate_id"],
            "country_iso3": candidate["country_iso3"],
            "year": candidate["year"],
            "similarity": candidate["similarity"],
            "review_hint": hint,
            "suggested_decision": suggested_decision,
            "suggestion_confidence": suggestion_confidence,
            "suggestion_reason": suggestion_reason,
            "left_source": left["source_db"],
            "left_record_id": left["record_id"],
            "left_title": left["project_name"],
            "left_amount_value": left["amount_value"],
            "left_price_basis": left["price_basis"],
            "left_fund_type": left["fund_type"],
            "left_sector": left["sector_harmonized"],
            "right_source": right["source_db"],
            "right_record_id": right["record_id"],
            "right_title": right["project_name"],
            "right_amount_value": right["amount_value"],
            "right_price_basis": right["price_basis"],
            "right_fund_type": right["fund_type"],
            "right_sector": right["sector_harmonized"],
            "amount_ratio_if_comparable": round(left_amount / right_amount, 6) if comparable else "",
            "review_decision": "",
            "review_notes": "",
        })
    queue.sort(key=lambda item: (-float(item["similarity"]), item["candidate_id"]))
    return queue


def reconcile_review_statuses(records: list[dict], candidates: list[dict]) -> None:
    """Close resolved unmatched records without erasing stronger match bases."""
    pending_keys = {
        key
        for candidate in candidates if candidate["status"] == "needs_review"
        for key in (candidate["left_record_key"], candidate["right_record_key"])
    }
    for record in records:
        if record["match_status"] != "needs_review":
            continue
        if record["_record_key"] not in pending_keys:
            record["match_status"] = "reviewed_no_match"
            record["match_confidence"] = 1


def detect_amount_outliers(records: list[dict]) -> list[dict]:
    """Flag candidates using source/measure-specific log-MAD; never delete them."""
    groups: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for record in records:
        amount = parse_number(record["amount_value"])
        if amount is not None and amount > 0:
            key = (record["source_db"], record["price_basis"], record["amount_measure"])
            groups[key].append(amount)

    group_stats = {}
    for key, values in groups.items():
        logs = [math.log10(value) for value in values]
        center = median(logs)
        mad = median(abs(value - center) for value in logs)
        group_stats[key] = {
            "count": len(values), "center": center, "mad": mad,
            "median_amount": median(values),
        }

    outliers = []
    for record in records:
        amount = parse_number(record["amount_value"])
        method = ""
        robust_z: float | str = ""
        stats = group_stats.get((record["source_db"], record["price_basis"], record["amount_measure"]))
        if amount is not None and amount <= 0:
            method = "nonpositive_project_amount"
        elif amount is not None and stats and stats["count"] >= 10 and stats["mad"] > 0:
            robust_z = round(0.6745 * (math.log10(amount) - stats["center"]) / stats["mad"], 4)
            if abs(robust_z) > 3.5:
                method = "source_measure_log_mad_gt_3_5"
        if not method:
            continue
        record["is_outlier"] = True
        outliers.append({
            "outlier_id": stable_id("OL", record["_record_key"], method),
            "record_key": record["_record_key"],
            "source_db": record["source_db"],
            "record_id": record["record_id"],
            "country_iso3": record["country_iso3"],
            "year": record["year"],
            "project_name": record["project_name"],
            "amount_value": record["amount_value"],
            "amount_unit": record["amount_unit"],
            "price_basis": record["price_basis"],
            "amount_measure": record["amount_measure"],
            "detection_method": method,
            "robust_z": robust_z,
            "group_known_count": stats["count"] if stats else 0,
            "group_median_amount": round(stats["median_amount"], 6) if stats else "",
            "review_decision": "",
            "review_notes": "",
        })
    outliers.sort(key=lambda item: (-abs(float(item["robust_z"] or 0)), item["outlier_id"]))
    return outliers


def project_quality_summary(records: list[dict]) -> list[dict]:
    rows = []
    for source in SOURCE_META:
        group = [record for record in records if record["source_db"] == source]
        total = len(group)
        value_field = "metric_value" if source == "cgp" else "amount_value"
        known = sum(parse_number(record[value_field]) is not None for record in group)
        row = {
            "source_db": source,
            "source_label": SOURCE_META[source]["label"],
            "primary_value_field": value_field,
            "total_records": total,
            "panel_eligible_records": sum(bool(record["panel_eligible"]) for record in group),
            "value_known_count": known,
            "value_missing_count": total - known,
            "value_missing_rate": round((total - known) / total, 6) if total else "",
            "country_known_rate": round(sum(bool(record["country_iso3"]) for record in group) / total, 6) if total else "",
            "year_known_rate": round(sum(isinstance(record["year"], int) for record in group) / total, 6) if total else "",
            "title_known_rate": round(sum(bool(record["project_name"]) for record in group) / total, 6) if total else "",
            "sector_classified_rate": round(sum(record["sector_harmonized"] not in {"", "unspecified"} for record in group) / total, 6) if total else "",
            "fund_type_classified_rate": round(sum(record["fund_type"] not in {"", "unspecified"} for record in group) / total, 6) if total else "",
            "estimated_count": sum(bool(record["is_estimated"]) for record in group),
            "regional_count": sum(bool(record["is_regional"]) for record in group),
            "framework_count": sum(bool(record["is_framework"]) for record in group),
            "outlier_candidate_count": sum(bool(record["is_outlier"]) for record in group),
            "needs_match_review_count": sum(record["match_status"] == "needs_review" for record in group),
        }
        rows.append(row)
    return rows


def panel_missingness_summary(wide: list[dict]) -> list[dict]:
    index_columns = {"iso3", "year", "country_name_en", "country_name_zh"}
    measurement_columns = [
        column for column in wide[0]
        if column not in index_columns and not column.endswith("_count")
    ]
    output = []
    for column in measurement_columns:
        observed = [(row, parse_number(row.get(column))) for row in wide]
        known = [(row, value) for row, value in observed if value is not None]
        years = [int(row["year"]) for row, _value in known]
        output.append({
            "variable": column,
            "panel_rows": len(wide),
            "observed_count": len(known),
            "missing_count": len(wide) - len(known),
            "missing_rate": round((len(wide) - len(known)) / len(wide), 6),
            "zero_count": sum(value == 0 for _row, value in known),
            "negative_count": sum(value < 0 for _row, value in known),
            "countries_with_data": len({row["iso3"] for row, _value in known}),
            "years_with_data": len(set(years)),
            "first_observed_year": min(years) if years else "",
            "last_observed_year": max(years) if years else "",
        })
    return output


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def average_ranks(values: list[float]) -> list[float]:
    ranked = sorted(enumerate(values), key=lambda item: item[1])
    output = [0.0] * len(values)
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][1] == ranked[index][1]:
            end += 1
        average = ((index + 1) + end) / 2
        for position in range(index, end):
            output[ranked[position][0]] = average
        index = end
    return output


def pearson_correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator else None


def spearman_correlation(left: list[float], right: list[float]) -> float | None:
    return pearson_correlation(average_ranks(left), average_ranks(right))


def kendall_tau_b(left: list[float], right: list[float]) -> float | None:
    concordant = discordant = tied_left = tied_right = 0
    for first in range(len(left) - 1):
        for second in range(first + 1, len(left)):
            dx = left[first] - left[second]
            dy = right[first] - right[second]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                tied_left += 1
                continue
            if dy == 0:
                tied_right += 1
                continue
            product = dx * dy
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
    comparable_plus_left_ties = concordant + discordant + tied_left
    comparable_plus_right_ties = concordant + discordant + tied_right
    denominator = math.sqrt(comparable_plus_left_ties * comparable_plus_right_ties)
    return (concordant - discordant) / denominator if denominator else None


def rounded(value: float | None) -> float | str:
    return "" if value is None else round(value, 6)


def longest_consecutive_run(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Return the longest annual run so missing years do not masquerade as breaks."""
    if not points:
        return []
    runs: list[list[tuple[int, float]]] = []
    current = [points[0]]
    for point in points[1:]:
        if point[0] == current[-1][0] + 1:
            current.append(point)
        else:
            runs.append(current)
            current = [point]
    runs.append(current)
    return max(runs, key=lambda run: (len(run), -run[0][0]))


def fit_multiple_mean_breaks(
    years: list[int], values: list[float], min_segment_length: int = 4,
    max_breaks: int = 3,
) -> dict | None:
    """BIC-selected dynamic-programming approximation to Bai-Perron mean shifts."""
    n = len(values)
    if n < min_segment_length * 2 or len(years) != n:
        return None
    scale = median([abs(value) for value in values if value != 0]) or 1.0
    transformed = [math.asinh(value / scale) for value in values]
    prefix = [0.0]
    prefix_sq = [0.0]
    for value in transformed:
        prefix.append(prefix[-1] + value)
        prefix_sq.append(prefix_sq[-1] + value * value)

    def segment_sse(start: int, end: int) -> float:
        count = end - start
        total = prefix[end] - prefix[start]
        squares = prefix_sq[end] - prefix_sq[start]
        return max(0.0, squares - total * total / count)

    max_segments = min(max_breaks + 1, n // min_segment_length)
    infinity = float("inf")
    dp = [[infinity] * (n + 1) for _ in range(max_segments + 1)]
    previous = [[-1] * (n + 1) for _ in range(max_segments + 1)]
    dp[0][0] = 0.0
    for segments in range(1, max_segments + 1):
        earliest_end = segments * min_segment_length
        for end in range(earliest_end, n + 1):
            earliest_start = (segments - 1) * min_segment_length
            latest_start = end - min_segment_length
            for start in range(earliest_start, latest_start + 1):
                if dp[segments - 1][start] == infinity:
                    continue
                candidate = dp[segments - 1][start] + segment_sse(start, end)
                if candidate < dp[segments][end]:
                    dp[segments][end] = candidate
                    previous[segments][end] = start

    models = []
    for segments in range(1, max_segments + 1):
        sse = max(dp[segments][n], 1e-12)
        parameter_count = 2 * segments - 1
        bic = n * math.log(sse / n) + parameter_count * math.log(n)
        models.append((bic, segments))
    selected_bic, selected_segments = min(models)
    no_break_bic = models[0][0]
    bounds = [n]
    end = n
    for segments in range(selected_segments, 0, -1):
        end = previous[segments][end]
        bounds.append(end)
    bounds = sorted(bounds)
    return {
        "segments": selected_segments,
        "break_indices": bounds[1:-1],
        "bic": selected_bic,
        "no_break_bic": no_break_bic,
        "bic_improvement": no_break_bic - selected_bic,
        "scale": scale,
    }


def build_structural_break_analysis(annual: list[dict]) -> tuple[list[dict], list[dict]]:
    models: list[dict] = []
    breakpoints: list[dict] = []
    metric_by_id = {metric["id"]: metric for metric in ANALYSIS_METRICS}
    for metric in ANALYSIS_METRICS:
        metric_rows = sorted(
            (row for row in annual if row["metric_id"] == metric["id"]),
            key=lambda row: int(row["year"]),
        )
        for variant, value_column in (("annual_total", "total_value"), ("coverage_normalized_mean", "mean_value")):
            points = [
                (int(row["year"]), value)
                for row in metric_rows
                if (value := parse_number(row.get(value_column))) is not None
            ]
            run = longest_consecutive_run(points)
            if len(run) < 8:
                continue
            years = [year for year, _value in run]
            values = [value for _year, value in run]
            fit = fit_multiple_mean_breaks(years, values)
            if fit is None:
                continue
            break_years = [years[index] for index in fit["break_indices"]]
            model = {
                "metric_id": metric["id"], "metric_label": metric["label"],
                "series_variant": variant, "start_year": years[0], "end_year": years[-1],
                "observations": len(years), "min_segment_length": 4,
                "selected_segments": fit["segments"], "break_count": len(break_years),
                "break_years": "|".join(map(str, break_years)), "bic": rounded(fit["bic"]),
                "no_break_bic": rounded(fit["no_break_bic"]),
                "bic_improvement": rounded(fit["bic_improvement"]), "transform": "asinh_scaled",
                "method": "bai_perron_style_dynamic_programming_bic_mean_shift",
                "interpretation_limit": "Descriptive candidate shifts in the longest consecutive annual run; not causal and not a formal event-date test.",
            }
            models.append(model)
            bounds = [0, *fit["break_indices"], len(years)]
            for number, break_index in enumerate(fit["break_indices"], 1):
                left_start, left_end = bounds[number - 1], break_index
                right_start, right_end = break_index, bounds[number + 1]
                pre_mean = sum(values[left_start:left_end]) / (left_end - left_start)
                post_mean = sum(values[right_start:right_end]) / (right_end - right_start)
                relative = None if pre_mean == 0 else (post_mean - pre_mean) / abs(pre_mean)
                improvement = float(fit["bic_improvement"])
                evidence = "strong" if improvement >= 10 else "moderate" if improvement >= 6 else "limited"
                breakpoints.append({
                    "metric_id": metric["id"], "metric_label": metric["label"],
                    "series_variant": variant, "break_number": number,
                    "break_year": years[break_index], "pre_start_year": years[left_start],
                    "pre_end_year": years[left_end - 1], "post_start_year": years[right_start],
                    "post_end_year": years[right_end - 1], "pre_mean_original": rounded(pre_mean),
                    "post_mean_original": rounded(post_mean), "relative_change": rounded(relative),
                    "bic_improvement": rounded(improvement), "evidence_strength": evidence,
                    "unit": metric_by_id[metric["id"]]["unit"], "price_basis": metric["price_basis"],
                })
    breakpoints.sort(key=lambda row: (-float(row["bic_improvement"]), row["metric_id"], row["break_number"]))
    return models, breakpoints


def lineage_classification(left: str, right: str) -> str:
    pair = {left, right}
    if pair <= {"codf", "cla", "cgef"}:
        return "likely_shared_lineage"
    if pair == {"aiddata", "chapo"}:
        return "documented_cross_reference_overlap"
    return "distinct_source_comparison"


def build_correlation_robustness(baseline: list[dict], robust: list[dict], removed: int) -> list[dict]:
    robust_index = {(row["scope"], row["left_metric"], row["right_metric"]): row for row in robust}
    output = []
    for row in baseline:
        comparison = robust_index.get((row["scope"], row["left_metric"], row["right_metric"]))
        if comparison is None:
            continue
        baseline_rho = parse_number(row["spearman_rho"])
        robust_rho = parse_number(comparison["spearman_rho"])
        baseline_tau = parse_number(row["kendall_tau_b"])
        robust_tau = parse_number(comparison["kendall_tau_b"])
        delta_rho = None if baseline_rho is None or robust_rho is None else robust_rho - baseline_rho
        delta_tau = None if baseline_tau is None or robust_tau is None else robust_tau - baseline_tau
        magnitude = abs(delta_rho or 0)
        stability = "stable" if magnitude <= .05 else "moderate_change" if magnitude <= .15 else "sensitive"
        output.append({
            "scope": row["scope"], "left_metric": row["left_metric"], "right_metric": row["right_metric"],
            "lineage_classification": lineage_classification(row["left_metric"], row["right_metric"]),
            "baseline_n": row["paired_observations"], "robust_n": comparison["paired_observations"],
            "baseline_spearman": rounded(baseline_rho), "robust_spearman": rounded(robust_rho),
            "delta_spearman": rounded(delta_rho), "baseline_kendall": rounded(baseline_tau),
            "robust_kendall": rounded(robust_tau), "delta_kendall": rounded(delta_tau),
            "flagged_outliers_removed": removed, "stability": stability,
            "interpretation_limit": "Sensitivity check excludes flagged project-level outlier candidates only; lineage labels warn against treating related compilations as independent confirmation.",
        })
    output.sort(key=lambda row: (-abs(float(row["baseline_spearman"] or 0)), row["left_metric"], row["right_metric"]))
    return output


def build_empirical_analysis(wide: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:
    descriptive = []
    annual = []
    country_summary = []
    metric_by_id = {metric["id"]: metric for metric in ANALYSIS_METRICS}

    for metric in ANALYSIS_METRICS:
        values = [parse_number(row.get(metric["column"])) for row in wide]
        known = [value for value in values if value is not None]
        known_rows = [row for row, value in zip(wide, values) if value is not None]
        observed_years = sorted({int(row["year"]) for row in known_rows})
        first_observed_year = observed_years[0] if observed_years else None
        last_observed_year = observed_years[-1] if observed_years else None
        mean_value = sum(known) / len(known) if known else None
        std_dev = (
            math.sqrt(sum((value - mean_value) ** 2 for value in known) / (len(known) - 1))
            if mean_value is not None and len(known) > 1 else None
        )
        descriptive.append({
            "metric_id": metric["id"], "metric_label": metric["label"],
            "category": metric["category"], "unit": metric["unit"],
            "price_basis": metric["price_basis"], "amount_measure": metric["measure"],
            "panel_rows": len(wide), "observed_count": len(known),
            "missing_count": len(wide) - len(known),
            "missing_rate": round((len(wide) - len(known)) / len(wide), 6),
            "countries_with_data": len({row["iso3"] for row in known_rows}),
            "years_with_data": len({row["year"] for row in known_rows}),
            "mean": rounded(mean_value), "median": rounded(median(known) if known else None),
            "std_dev": rounded(std_dev), "p25": rounded(percentile(known, .25) if known else None),
            "p75": rounded(percentile(known, .75) if known else None),
            "minimum": rounded(min(known) if known else None),
            "maximum": rounded(max(known) if known else None),
            "zero_count": sum(value == 0 for value in known),
            "negative_count": sum(value < 0 for value in known),
        })

        for year in range(START_YEAR, END_YEAR + 1):
            year_rows = [row for row in wide if int(row["year"]) == year]
            year_values = [parse_number(row.get(metric["column"])) for row in year_rows]
            year_known = [value for value in year_values if value is not None]
            record_count = ""
            if metric["count"]:
                record_count = sum(int(parse_number(row.get(metric["count"])) or 0) for row in year_rows)
            if metric["id"] == "aidexports" and year_known:
                maximum_months = max(
                    int(parse_number(row.get("aidexports_month_count")) or 0)
                    for row in year_rows
                )
                year_complete = maximum_months >= 12
                coverage_status = "observed_full_year" if year_complete else "observed_partial_year"
                coverage_note = f"maximum_{maximum_months}_months_observed_per_country"
            elif year_known:
                year_complete = ""
                coverage_status = "observed"
                coverage_note = "annual_source_completeness_not_separately_reported"
            elif first_observed_year is not None and first_observed_year <= year <= last_observed_year:
                year_complete = False
                coverage_status = "no_observations_within_source_span"
                coverage_note = "no_value_observed_in_loaded_source_extract"
            else:
                year_complete = False
                coverage_status = "outside_source_coverage"
                coverage_note = "year_outside_first_and_last_observed_source_years"
            annual.append({
                "metric_id": metric["id"], "metric_label": metric["label"], "year": year,
                "observed_country_count": len(year_known), "record_count": record_count,
                "total_value": rounded(sum(year_known) if year_known else None),
                "mean_value": rounded(sum(year_known) / len(year_known) if year_known else None),
                "median_value": rounded(median(year_known) if year_known else None),
                "unit": metric["unit"], "price_basis": metric["price_basis"],
                "amount_measure": metric["measure"],
                "source_first_observed_year": first_observed_year or "",
                "source_last_observed_year": last_observed_year or "",
                "year_complete": year_complete,
                "coverage_status": coverage_status,
                "coverage_note": coverage_note,
            })

        per_country = []
        for iso in sorted({row["iso3"] for row in wide}):
            rows_for_country = [row for row in wide if row["iso3"] == iso]
            country_values = [
                (int(row["year"]), parse_number(row.get(metric["column"])))
                for row in rows_for_country
            ]
            country_known = [(year, value) for year, value in country_values if value is not None]
            if not country_known:
                continue
            numeric = [value for _year, value in country_known]
            per_country.append({
                "metric_id": metric["id"], "metric_label": metric["label"], "iso3": iso,
                "country_name_en": rows_for_country[0]["country_name_en"],
                "observed_year_count": len(country_known),
                "first_observed_year": min(year for year, _value in country_known),
                "last_observed_year": max(year for year, _value in country_known),
                "total_value": round(sum(numeric), 6),
                "annual_mean": round(sum(numeric) / len(numeric), 6),
                "annual_median": round(median(numeric), 6),
                "rank_within_metric": 0, "unit": metric["unit"],
                "price_basis": metric["price_basis"],
                "aggregation_caveat": "nominal_values_not_inflation_adjusted" if metric["price_basis"] == "nominal_usd" else "within_source_price_basis_preserved",
            })
        per_country.sort(key=lambda item: (-float(item["total_value"]), item["iso3"]))
        for rank, item in enumerate(per_country, 1):
            item["rank_within_metric"] = rank
        country_summary.extend(per_country)

    correlations = []
    correlation_metrics = [metric for metric in ANALYSIS_METRICS if metric["id"] in CORRELATION_METRICS]
    for left_metric, right_metric in combinations(correlation_metrics, 2):
        paired_rows = []
        for row in wide:
            left_value = parse_number(row.get(left_metric["column"]))
            right_value = parse_number(row.get(right_metric["column"]))
            if left_value is not None and right_value is not None:
                paired_rows.append((row, left_value, right_value))

        scopes = []
        if len(paired_rows) >= 15:
            scopes.append((
                "country_year_overlap",
                [left for _row, left, _right in paired_rows],
                [right for _row, _left, right in paired_rows],
                len(paired_rows),
            ))

        country_pairs = []
        for iso in sorted({row["iso3"] for row in wide}):
            shared = [(left, right) for row, left, right in paired_rows if row["iso3"] == iso]
            if len(shared) >= 2:
                country_pairs.append((sum(left for left, _right in shared), sum(right for _left, right in shared), len(shared)))
        if len(country_pairs) >= 8:
            scopes.append((
                "country_common_year_total",
                [left for left, _right, _years in country_pairs],
                [right for _left, right, _years in country_pairs],
                sum(years for _left, _right, years in country_pairs),
            ))

        for scope, left_values, right_values, shared_country_years in scopes:
            spearman = spearman_correlation(left_values, right_values)
            kendall = kendall_tau_b(left_values, right_values)
            same_basis = left_metric["price_basis"] == right_metric["price_basis"]
            correlations.append({
                "scope": scope, "left_metric": left_metric["id"],
                "left_label": left_metric["label"], "right_metric": right_metric["id"],
                "right_label": right_metric["label"], "paired_observations": len(left_values),
                "shared_country_years": shared_country_years,
                "spearman_rho": rounded(spearman), "kendall_tau_b": rounded(kendall),
                "left_price_basis": left_metric["price_basis"],
                "right_price_basis": right_metric["price_basis"],
                "comparability_tier": "same_basis_rank_comparison" if same_basis else "different_basis_rank_only",
                "interpretation_limit": "Association on pairwise observed ranks; not an agreement of monetary levels and not causal.",
            })

    description_by_metric = {row["metric_id"]: row for row in descriptive}
    sources = []
    for metric in ANALYSIS_METRICS:
        metric_annual = [row for row in annual if row["metric_id"] == metric["id"] and row["total_value"] != ""]
        metric_countries = [row for row in country_summary if row["metric_id"] == metric["id"]]
        peak = max(metric_annual, key=lambda row: float(row["total_value"])) if metric_annual else None
        top_country = min(metric_countries, key=lambda row: int(row["rank_within_metric"])) if metric_countries else None
        description = description_by_metric[metric["id"]]
        sources.append({
            "id": metric["id"], "label": metric["label"], "category": metric["category"],
            "unit": metric["unit"], "priceBasis": metric["price_basis"], "measure": metric["measure"],
            "observedCount": description["observed_count"], "missingRate": description["missing_rate"],
            "countries": description["countries_with_data"], "years": description["years_with_data"],
            "median": description["median"], "peakYear": peak["year"] if peak else None,
            "peakValue": peak["total_value"] if peak else None,
            "topCountry": top_country["country_name_en"] if top_country else None,
            "topCountryIso3": top_country["iso3"] if top_country else None,
            "topCountryValue": top_country["total_value"] if top_country else None,
        })

    ranked_correlations = sorted(
        correlations,
        key=lambda row: (-abs(float(row["spearman_rho"] or 0)), row["left_metric"], row["right_metric"]),
    )
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": {
            "panel": "54 sovereign African countries, 2000-2024",
            "missing": "Pairwise complete observations only; missing values are never replaced with zero.",
            "correlation": "Spearman rho and Kendall tau-b on ranks. Monetary levels with different price bases are not treated as directly comparable.",
            "aggregation": "Totals are computed only within each source. Nominal series are not inflation-adjusted.",
            "causality": "All results are descriptive associations, not causal estimates.",
        },
        "summary": {
            "metricsProfiled": len(descriptive), "annualRows": len(annual),
            "countrySummaryRows": len(country_summary), "correlationRows": len(correlations),
        },
        "sources": sources,
        "correlations": ranked_correlations,
    }
    return descriptive, annual, country_summary, correlations, report


def panel_skeleton(ref: CountryReference) -> list[dict]:
    return [
        {"iso3": iso, "year": year, "country_name_en": ref.by_iso[iso]["name_en"], "country_name_zh": ref.by_iso[iso]["name_zh"]}
        for iso in ref.sovereign for year in range(START_YEAR, END_YEAR + 1)
    ]


def aggregate_project_rows(records: list[dict], skeleton: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    base = {(row["iso3"], row["year"]): dict(row) for row in skeleton}
    for panel in base.values():
        for source in SOURCE_META:
            panel[f"{source}_count"] = 0
            if source in AMOUNT_SOURCES:
                panel[f"{source}_amount_known_count"] = 0
                panel[f"{source}_total_usd"] = ""
        panel["cgp_capacity_mw"] = ""

    amount_sums: dict[tuple[str, int, str], float] = defaultdict(float)
    amount_known: Counter = Counter()
    metric_sums: dict[tuple[str, int, str], float] = defaultdict(float)
    fund_sums: dict[tuple[str, int, str, str], float] = defaultdict(float)
    fund_known: Counter = Counter()

    for record in records:
        if not record["panel_eligible"]:
            continue
        key = (record["country_iso3"], int(record["year"]))
        panel = base[key]
        source = record["source_db"]
        panel[f"{source}_count"] += 1
        amount = parse_number(record["amount_value"])
        if amount is not None:
            amount_sums[(key[0], key[1], source)] += amount
            amount_known[(key[0], key[1], source)] += 1
            fund = record["fund_type"]
            fund_sums[(key[0], key[1], source, fund)] += amount
            fund_known[(key[0], key[1], source, fund)] += 1
        metric = parse_number(record["metric_value"])
        if metric is not None:
            metric_sums[(key[0], key[1], source)] += metric

    fund_columns: set[str] = set()
    for (iso, year, source), value in amount_sums.items():
        panel = base[(iso, year)]
        panel[f"{source}_total_usd"] = round(value, 6)
        panel[f"{source}_amount_known_count"] = amount_known[(iso, year, source)]
    for (iso, year, source), value in metric_sums.items():
        if source == "cgp":
            base[(iso, year)]["cgp_capacity_mw"] = round(value, 6)
    for (iso, year, source, fund), value in fund_sums.items():
        column = f"{source}_{fund}_usd"
        fund_columns.add(column)
        base[(iso, year)][column] = round(value, 6)

    wide = [base[key] for key in sorted(base)]
    for row in wide:
        for column in fund_columns:
            row.setdefault(column, "")

    long_source = []
    for row in wide:
        for source in AMOUNT_SOURCES:
            long_source.append({
                "panel_id": f"{row['iso3']}::{source}", "iso3": row["iso3"],
                "country_name_en": row["country_name_en"], "year": row["year"],
                "source": source, "source_label": SOURCE_META[source]["label"],
                "amount_usd": row[f"{source}_total_usd"],
                "record_count": row[f"{source}_count"],
                "amount_known_count": row[f"{source}_amount_known_count"],
                "price_basis": SOURCE_META[source]["price_basis"],
                "amount_measure": SOURCE_META[source]["measure"],
            })

    long_fund = []
    for (iso, year, source, fund), value in sorted(fund_sums.items()):
        country = base[(iso, year)]
        long_fund.append({
            "panel_id": f"{iso}::{source}::{fund}", "iso3": iso,
            "country_name_en": country["country_name_en"], "year": year,
            "source": source, "fund_type": fund, "amount_usd": round(value, 6),
            "amount_known_count": fund_known[(iso, year, source, fund)],
            "price_basis": SOURCE_META[source]["price_basis"],
        })
    return wide, long_source, long_fund


def add_macro_sources(wide: list[dict], data_dir: Path, ref: CountryReference) -> None:
    by_key = {(row["iso3"], row["year"]): row for row in wide}

    exports = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    for row in read_rows(data_dir / "africa_aid_data_clean.csv"):
        iso, year = resolve_country(ref, row.get("iso3c", ""), "iso3"), parse_year(row.get("yearmonth"))
        if (iso, year) not in by_key:
            continue
        values = [parse_number(row.get("aid_total")), parse_number(row.get("aid_medical")), parse_number(row.get("aid_non_medical"))]
        for index, value in enumerate(values):
            if value is not None:
                exports[(iso, year)][index] += value
        exports[(iso, year)][3] += 1
    for key, values in exports.items():
        row = by_key[key]
        row["aidexports_total_usd"] = round(values[0], 6)
        row["aidexports_medical_usd"] = round(values[1], 6)
        row["aidexports_non_medical_usd"] = round(values[2], 6)
        row["aidexports_month_count"] = values[3]

    for source_row in read_rows(data_dir / "fdi_africa_panel.csv"):
        iso, year = resolve_country(ref, source_row.get("ISO_A3", ""), "iso3"), parse_year(source_row.get("Year"))
        if (iso, year) not in by_key:
            continue
        row = by_key[(iso, year)]
        stock, flow = parse_number(source_row.get("Stock_USD")), parse_number(source_row.get("Flow_USD"))
        row["fdi_stock_usd"] = "" if stock is None else stock
        row["fdi_flow_usd"] = "" if flow is None else flow

    ihme = defaultdict(float)
    ihme_known = Counter()
    for source_row in read_rows(data_dir / "ihme_dah_africa_clean.csv"):
        iso, year = resolve_country(ref, source_row.get("recipient_isocode", ""), "iso3"), parse_year(source_row.get("year"))
        value = parse_number(source_row.get("dah_23_million"))
        if (iso, year) in by_key and value is not None:
            ihme[(iso, year)] += value
            ihme_known[(iso, year)] += 1
    for key, value in ihme.items():
        by_key[key]["ihme_disbursement_2023_usd_million"] = round(value, 6)
        by_key[key]["ihme_observation_count"] = ihme_known[key]

    for source_row in read_rows(data_dir / "china_africa_finance_cleaned.csv"):
        iso, year = resolve_country(ref, source_row.get("CountryCode", ""), "iso3"), parse_year(source_row.get("year"))
        if (iso, year) not in by_key:
            continue
        row = by_key[(iso, year)]
        for output_name, input_name in [
            ("china_eu_dfchina_2017_usd", "DFCHINA"),
            ("china_eu_oda_2017_usd", "ODAChinA"),
            ("china_eu_oof_2017_usd", "OOFChinA"),
        ]:
            value = parse_number(source_row.get(input_name))
            row[output_name] = "" if value is None else value

    macro_columns = [
        "aidexports_total_usd", "aidexports_medical_usd", "aidexports_non_medical_usd", "aidexports_month_count",
        "fdi_stock_usd", "fdi_flow_usd", "ihme_disbursement_2023_usd_million", "ihme_observation_count",
        "china_eu_dfchina_2017_usd", "china_eu_oda_2017_usd", "china_eu_oof_2017_usd",
    ]
    for row in wide:
        for column in macro_columns:
            row.setdefault(column, "")


def data_dictionary(wide_columns: list[str]) -> list[dict]:
    descriptions = {
        "iso3": ("索引", "ISO3 country code", "text"),
        "year": ("索引", "Calendar year, restricted to 2000-2024", "integer"),
        "country_name_en": ("索引", "Standard English country name", "text"),
        "country_name_zh": ("索引", "Standard Chinese country name", "text"),
        "cgp_capacity_mw": ("特殊量纲", "CGP generating-unit capacity assigned to financing year; commissioning year is fallback", "MW"),
        "fdi_stock_usd": ("宏观指标", "Annual FDI stock; nominal USD", "USD"),
        "fdi_flow_usd": ("宏观指标", "Annual FDI flow; nominal USD; negative divestment retained", "USD"),
        "ihme_disbursement_2023_usd_million": ("宏观指标", "IHME annual DAH disbursement, constant 2023 USD", "USD million"),
        "aidexports_total_usd": ("宏观指标", "Annual sum of monthly Chinese aid exports", "nominal USD"),
        "china_eu_dfchina_2017_usd": ("宏观指标", "China development finance from the China-EU comparison dataset", "constant 2017 USD"),
        "china_eu_oda_2017_usd": ("宏观指标", "China ODA-like finance from the China-EU comparison dataset", "constant 2017 USD"),
        "china_eu_oof_2017_usd": ("宏观指标", "China OOF-like finance from the China-EU comparison dataset", "constant 2017 USD"),
    }
    rows = []
    for column in wide_columns:
        if column in descriptions:
            module, description, unit = descriptions[column]
        elif column.endswith("_count"):
            module, description, unit = "记录与质量", f"Record or known-value count for {column.rsplit('_', 1)[0]}", "count"
        elif column.endswith("_total_usd"):
            source = column.removesuffix("_total_usd")
            module, description, unit = "项目库汇总", f"Source-specific annual amount for {source}; never add across sources", "USD"
        elif column.endswith("_usd"):
            module, description, unit = "资金性质", f"Source-specific fund-type amount: {column}", "USD"
        else:
            module, description, unit = "其他", column, "source-specific"
        key_role = "composite_primary_key" if column in {"iso3", "year"} else ""
        missing_rule = "not_missing" if column in {"iso3", "year", "country_name_en", "country_name_zh"} else "blank_when_not_observed; zero_is_observed"
        rows.append({"table": "master_panel_wide", "column": column, "module": module, "description": description, "unit": unit, "key_role": key_role, "missing_rule": missing_rule})
    for column in PROJECT_COLUMNS:
        key_role = "composite_primary_key" if column in {"source_db", "record_id"} else "entity_link" if column == "project_match_id" else ""
        rows.append({"table": "project_level_master", "column": column, "module": "项目级", "description": column.replace("_", " "), "unit": "source-specific", "key_role": key_role, "missing_rule": "source_missing_preserved; zero_is_observed"})
    for table, columns in [
        ("long_source", LONG_SOURCE_COLUMNS),
        ("long_fundtype", LONG_FUNDTYPE_COLUMNS),
        ("match_candidates", MATCH_CANDIDATE_COLUMNS),
        ("match_review_queue", MATCH_REVIEW_COLUMNS),
        ("match_review_decisions_applied", REVIEW_APPLIED_COLUMNS),
        ("confirmed_match_groups", MATCH_GROUP_COLUMNS),
        ("project_entity_index", PROJECT_ENTITY_COLUMNS),
        ("project_quality_summary", QUALITY_COLUMNS),
        ("panel_missingness", MISSINGNESS_COLUMNS),
        ("outlier_candidates", OUTLIER_COLUMNS),
        ("source_descriptive_statistics", DESCRIPTIVE_COLUMNS),
        ("annual_source_trends", ANNUAL_TREND_COLUMNS),
        ("country_source_summary", COUNTRY_SUMMARY_COLUMNS),
        ("cross_source_correlations", CORRELATION_COLUMNS),
        ("structural_break_models", BREAK_MODEL_COLUMNS),
        ("structural_breakpoints", BREAKPOINT_COLUMNS),
        ("correlation_robustness", ROBUSTNESS_COLUMNS),
    ]:
        for column in columns:
            if column.endswith("_rate"):
                unit = "proportion_0_to_1"
            elif column.endswith("_count") or column in {"panel_rows", "countries_with_data", "years_with_data"}:
                unit = "count"
            elif "year" in column:
                unit = "year"
            else:
                unit = "source-specific"
            composite_keys = {
                "long_source": {"iso3", "year", "source"},
                "long_fundtype": {"iso3", "year", "source", "fund_type"},
            }
            primary_keys = {
                "match_candidates": "candidate_id",
                "match_review_queue": "candidate_id",
                "match_review_decisions_applied": "candidate_id",
                "confirmed_match_groups": "project_match_id",
                "project_entity_index": "project_entity_id",
                "outlier_candidates": "outlier_id",
            }
            if column in composite_keys.get(table, set()):
                key_role = "composite_primary_key"
            elif primary_keys.get(table) == column:
                key_role = "primary_key"
            elif column in {"left_record_key", "right_record_key", "member_record_keys"}:
                key_role = "foreign_key"
            elif column == "panel_id":
                key_role = "panel_identifier"
            else:
                key_role = ""
            module = (
                "长面板" if table in {"long_source", "long_fundtype"}
                else "项目匹配" if table in {"match_candidates", "match_review_queue", "match_review_decisions_applied"}
                else "项目实体" if table in {"confirmed_match_groups", "project_entity_index"}
                else "质量诊断"
            )
            rows.append({
                "table": table, "column": column, "module": module,
                "description": column.replace("_", " "), "unit": unit,
                "key_role": key_role,
                "missing_rule": "blank_when_not_observed; zero_is_observed",
            })
    return rows


def build_dashboard_from_panels(wide: list[dict], records: list[dict], ref: CountryReference, output: Path) -> dict:
    source_counts = defaultdict(Counter)
    year_counts = defaultdict(Counter)
    source_metrics = defaultdict(lambda: defaultdict(lambda: {"value": 0.0, "known": 0}))
    for record in records:
        if not record["panel_eligible"]:
            continue
        iso, year = record["country_iso3"], int(record["year"])
        source = "debt" if record["source_db"] in {"cancel", "restruct"} else record["source_db"]
        source_counts[iso][source] += 1
        year_counts[iso][year] += 1
        value = parse_number(record["metric_value"] if source == "cgp" else record["amount_value"])
        if value is not None:
            source_metrics[iso][source]["value"] += value
            source_metrics[iso][source]["known"] += 1

    macro_specs = {
        "exports": ("aidexports_month_count", "aidexports_total_usd", "援助出口价值", "nominal USD"),
        "fdi": (None, "fdi_flow_usd", "直接投资流量", "nominal USD"),
        "ihme": ("ihme_observation_count", "ihme_disbursement_2023_usd_million", "卫生发展援助拨付", "constant 2023 USD million"),
        "china_eu_finance": (None, "china_eu_dfchina_2017_usd", "中国发展融资", "constant 2017 USD"),
    }
    by_iso_rows = defaultdict(list)
    for row in wide:
        by_iso_rows[row["iso3"]].append(row)
        for source, (count_column, metric_column, _label, _unit) in macro_specs.items():
            metric = parse_number(row.get(metric_column))
            count = int(parse_number(row.get(count_column)) or (1 if metric is not None else 0))
            if count:
                source_counts[row["iso3"]][source] += count
                year_counts[row["iso3"]][row["year"]] += count
            if metric is not None:
                source_metrics[row["iso3"]][source]["value"] += metric
                source_metrics[row["iso3"]][source]["known"] += 1

    countries = {}
    for iso in ref.sovereign:
        counts = source_counts[iso]
        metrics = {}
        for source, metric in source_metrics[iso].items():
            if source in macro_specs:
                label, unit = macro_specs[source][2], macro_specs[source][3]
            elif source == "cgp":
                label, unit = "装机容量", "MW"
            elif source == "debt":
                label, unit = "债务减免与重组金额", "USD"
            else:
                label, unit = "来源内金额", "USD"
            metrics[source] = {"value": round(metric["value"], 6), "known": metric["known"], "label": label, "unit": unit}
        active_years = sorted(year_counts[iso])
        countries[iso] = {
            "iso3": iso, "nameEn": ref.by_iso[iso]["name_en"], "nameZh": ref.by_iso[iso]["name_zh"],
            "records": sum(counts.values()), "sourceCount": len([value for value in counts.values() if value > 0]),
            "sourceCounts": dict(counts.most_common()), "yearMin": min(active_years) if active_years else None,
            "yearMax": max(active_years) if active_years else None,
            "yearCounts": {str(year): year_counts[iso][year] for year in active_years}, "metrics": metrics,
        }

    source_rows = []
    display_sources = ["aiddata", "codf", "cla", "debt", "exports", "fdi", "cofi", "cgef", "cgp", "chapo", "ihme", "china_eu_finance"]
    display_labels = {"debt": "Debt relief", "exports": "Aid exports", "fdi": "FDI", "ihme": "IHME DAH", "china_eu_finance": "China–EU finance"}
    for source in display_sources:
        rows = sum(country["sourceCounts"].get(source, 0) for country in countries.values())
        observed_years = [year for iso in countries for year, count in year_counts[iso].items() if count and source in countries[iso]["sourceCounts"]]
        source_rows.append({
            "id": source, "label": SOURCE_META.get(source, {}).get("label", display_labels.get(source, source.replace("_", " ").title())),
            "rows": rows, "mappedRows": rows, "mappedRate": 1, "metricKnownRate": 0,
            "yearMin": min(observed_years) if observed_years else None, "yearMax": max(observed_years) if observed_years else None,
            "columns": [],
        })
    latest_export_months = max(
        (int(parse_number(row.get("aidexports_month_count")) or 0) for row in wide if int(row["year"]) == END_YEAR),
        default=0,
    )
    trend_comparison_year_max = END_YEAR - 1 if 0 < latest_export_months < 12 else END_YEAR
    dashboard = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": "Formal 54-country, 2000-2024 research panel. Source-specific monetary metrics retain their own price basis and are never added across databases.",
        "global": {"sourceCount": 12, "countryCount": 54, "recordCount": sum(country["records"] for country in countries.values()), "yearMin": START_YEAR, "yearMax": END_YEAR, "trendComparisonYearMax": trend_comparison_year_max, "latestYearCoverage": "partial" if trend_comparison_year_max < END_YEAR else "observed"},
        "sources": source_rows, "countries": countries, "unmapped": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dashboard, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return dashboard


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--public-dir", type=Path)
    parser.add_argument("--dashboard-output", type=Path)
    parser.add_argument("--review-decisions", type=Path)
    args = parser.parse_args()

    ref = load_country_reference(args.data_dir)
    records = project_rows(args.data_dir, ref)
    candidates = apply_matching(records)
    applied_review_rows = apply_review_decisions(records, candidates, args.review_decisions)
    review_queue = build_match_review_queue(candidates, records)
    reconcile_review_statuses(records, candidates)
    match_group_rows = build_match_groups(records)
    project_entity_rows = build_project_entity_index(records)
    outlier_rows = detect_amount_outliers(records)
    quality_rows = project_quality_summary(records)
    skeleton = panel_skeleton(ref)
    wide, long_source, long_fund = aggregate_project_rows(records, skeleton)
    add_macro_sources(wide, args.data_dir, ref)
    missingness_rows = panel_missingness_summary(wide)
    descriptive_rows, annual_rows, country_summary_rows, correlation_rows, empirical_report = build_empirical_analysis(wide)
    break_model_rows, breakpoint_rows = build_structural_break_analysis(annual_rows)
    robust_records = [record for record in records if not record["is_outlier"]]
    robust_wide, _robust_long_source, _robust_long_fund = aggregate_project_rows(robust_records, skeleton)
    add_macro_sources(robust_wide, args.data_dir, ref)
    _robust_descriptive, _robust_annual, _robust_country, robust_correlations, _robust_report = build_empirical_analysis(robust_wide)
    robustness_rows = build_correlation_robustness(correlation_rows, robust_correlations, len(outlier_rows))
    empirical_report["summary"].update({
        "breakModels": len(break_model_rows), "breakpoints": len(breakpoint_rows),
        "robustnessRows": len(robustness_rows), "outlierCandidatesExcludedInSensitivity": len(outlier_rows),
    })
    empirical_report["method"].update({
        "structuralBreaks": "Bai-Perron-style dynamic programming selects up to three mean shifts by BIC after an asinh scale transform, using the longest consecutive annual run and minimum four-year segments.",
        "robustness": "The sensitivity panel excludes flagged project-level outlier candidates; the primary panel remains unchanged.",
        "lineage": "CODF, CLA and CGEF comparisons are flagged as likely shared lineage; AidData-CHAPO is flagged for documented cross-reference overlap.",
    })
    empirical_report["breakpoints"] = breakpoint_rows
    empirical_report["robustness"] = robustness_rows

    project_path = args.output_dir / "project_level_master.csv"
    match_path = args.output_dir / "match_candidates.csv"
    skeleton_path = args.output_dir / "panel_skeleton.csv"
    wide_path = args.output_dir / "master_panel_wide.csv"
    source_path = args.output_dir / "long_source.csv"
    fund_path = args.output_dir / "long_fundtype.csv"
    dictionary_path = args.output_dir / "data_dictionary.csv"
    review_path = args.output_dir / "match_review_queue.csv"
    review_json_path = args.output_dir / "match_review_queue.json"
    applied_review_path = args.output_dir / "match_review_decisions_applied.csv"
    match_group_path = args.output_dir / "confirmed_match_groups.csv"
    project_entity_path = args.output_dir / "project_entity_index.csv"
    quality_path = args.output_dir / "project_quality_summary.csv"
    missingness_path = args.output_dir / "panel_missingness.csv"
    outlier_path = args.output_dir / "outlier_candidates.csv"
    descriptive_path = args.output_dir / "source_descriptive_statistics.csv"
    annual_path = args.output_dir / "annual_source_trends.csv"
    country_summary_path = args.output_dir / "country_source_summary.csv"
    correlation_path = args.output_dir / "cross_source_correlations.csv"
    break_model_path = args.output_dir / "structural_break_models.csv"
    breakpoint_path = args.output_dir / "structural_breakpoints.csv"
    robustness_path = args.output_dir / "correlation_robustness.csv"
    empirical_report_path = args.output_dir / "empirical_report.json"

    wide_columns = list(wide[0])
    counts = {
        "project_level_master": write_csv(project_path, records, PROJECT_COLUMNS),
        "match_candidates": write_csv(match_path, candidates, MATCH_CANDIDATE_COLUMNS),
        "panel_skeleton": write_csv(skeleton_path, skeleton, list(skeleton[0])),
        "master_panel_wide": write_csv(wide_path, wide, wide_columns),
        "long_source": write_csv(source_path, long_source, LONG_SOURCE_COLUMNS),
        "long_fundtype": write_csv(fund_path, long_fund, LONG_FUNDTYPE_COLUMNS),
        "data_dictionary": write_csv(dictionary_path, data_dictionary(wide_columns), DATA_DICTIONARY_COLUMNS),
        "match_review_queue": write_csv(review_path, review_queue, MATCH_REVIEW_COLUMNS),
        "match_review_decisions_applied": write_csv(applied_review_path, applied_review_rows, REVIEW_APPLIED_COLUMNS),
        "confirmed_match_groups": write_csv(match_group_path, match_group_rows, MATCH_GROUP_COLUMNS),
        "project_entity_index": write_csv(project_entity_path, project_entity_rows, PROJECT_ENTITY_COLUMNS),
        "project_quality_summary": write_csv(quality_path, quality_rows, QUALITY_COLUMNS),
        "panel_missingness": write_csv(missingness_path, missingness_rows, MISSINGNESS_COLUMNS),
        "outlier_candidates": write_csv(outlier_path, outlier_rows, OUTLIER_COLUMNS),
        "source_descriptive_statistics": write_csv(descriptive_path, descriptive_rows, DESCRIPTIVE_COLUMNS),
        "annual_source_trends": write_csv(annual_path, annual_rows, ANNUAL_TREND_COLUMNS),
        "country_source_summary": write_csv(country_summary_path, country_summary_rows, COUNTRY_SUMMARY_COLUMNS),
        "cross_source_correlations": write_csv(correlation_path, correlation_rows, CORRELATION_COLUMNS),
        "structural_break_models": write_csv(break_model_path, break_model_rows, BREAK_MODEL_COLUMNS),
        "structural_breakpoints": write_csv(breakpoint_path, breakpoint_rows, BREAKPOINT_COLUMNS),
        "correlation_robustness": write_csv(robustness_path, robustness_rows, ROBUSTNESS_COLUMNS),
    }
    applied_review_count = sum(row["application_status"] == "applied" for row in applied_review_rows)
    review_json_path.write_text(json.dumps({
        "rows": review_queue,
        "appliedReviewCount": applied_review_count,
        "appliedSameProjectCount": sum(row["application_status"] == "applied" and row["review_decision"] == "same_project" for row in applied_review_rows),
        "appliedDifferentProjectCount": sum(row["application_status"] == "applied" and row["review_decision"] == "different_project" for row in applied_review_rows),
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    empirical_report_path.write_text(json.dumps(empirical_report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    dashboard = None
    if args.dashboard_output:
        dashboard = build_dashboard_from_panels(wide, records, ref, args.dashboard_output)

    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "parameters": {"startYear": START_YEAR, "endYear": END_YEAR, "sovereignCountries": len(ref.sovereign)},
        "rows": counts,
        "matching": dict(Counter(record["match_status"] for record in records)),
        "quality": {
            "matchReviewQueueRows": len(review_queue),
            "reviewDecisionsApplied": applied_review_count,
            "humanConfirmedSameProject": sum(row["application_status"] == "applied" and row["review_decision"] == "same_project" for row in applied_review_rows),
            "confirmedMatchGroups": len(match_group_rows),
            "projectEntities": len(project_entity_rows),
            "outlierCandidateRows": len(outlier_rows),
            "panelVariablesProfiled": len(missingness_rows),
            "imputationApplied": False,
            "outliersRemoved": False,
        },
        "empirical": empirical_report["summary"],
        "panelChecks": {
            "expectedWideRows": 54 * 25,
            "actualWideRows": len(wide),
            "uniqueCountryYear": len({(row["iso3"], row["year"]) for row in wide}),
            "crossSourceAmountsSummed": False,
            "missingAmountsReplacedWithZero": False,
        },
        "dashboard": dashboard["global"] if dashboard else None,
    }
    report_path = args.output_dir / "build_report.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.public_dir:
        args.public_dir.mkdir(parents=True, exist_ok=True)
        for path in [
            project_path, match_path, wide_path, source_path, fund_path,
            dictionary_path, review_path, quality_path, missingness_path,
            outlier_path, review_json_path, descriptive_path, annual_path,
            country_summary_path, correlation_path, empirical_report_path,
            break_model_path, breakpoint_path, robustness_path,
            applied_review_path, match_group_path,
            project_entity_path,
            report_path,
        ]:
            shutil.copy2(path, args.public_dir / path.name)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
