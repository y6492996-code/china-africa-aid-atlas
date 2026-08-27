#!/usr/bin/env python3
"""Merge human review exports and add only conservative batch decisions.

Human decisions always win.  Automatic rules are deliberately restricted to
relationships that are auditable from the generated review queue and master
panel; unresolved title-only candidates are left out of the decision file.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DECISION_COLUMNS = [
    "candidate_id", "left_source", "left_record_id", "right_source",
    "right_record_id", "review_decision", "review_notes", "reviewed_at",
]

AUDIT_COLUMNS = DECISION_COLUMNS + [
    "decision_origin", "confidence", "rule_id", "rule_evidence",
    "country_iso3", "year", "similarity", "left_title", "right_title",
    "left_fund_type", "right_fund_type", "left_sector", "right_sector",
]

RELATED_FINANCE_CATALOGS = {"cla", "codf", "cgef"}
ASSET_CATALOGS = {"cgp", "cofi", "restruct"}
QUALIFIER_MARKERS = {
    "batch", "team", "tranche", "phase", "part", "lot", "loan", "unit",
    "package", "section", "stage",
}
ORDINALS = {
    "first": "1", "second": "2", "third": "3", "fourth": "4",
    "fifth": "5", "sixth": "6", "seventh": "7", "eighth": "8",
    "ninth": "9", "tenth": "10", "i": "1", "ii": "2", "iii": "3",
    "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8",
    "ix": "9", "x": "10",
}

MONTHS = {
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
}

CURRENCY_AMOUNT_RE = re.compile(
    r"(?P<currency>usd|eur|zar|rmb|cny|\$)\s*"
    r"(?P<value>\d+(?:[.,]\d+)*)\s*"
    r"(?P<scale>billion|million|thousand|bn|mn|m|b)?",
    re.IGNORECASE,
)

PROJECT_NAME_STOPWORDS = {
    "a", "an", "and", "bank", "buyer", "buyers", "china", "chinese",
    "commercial", "concessional", "construction", "contributes", "credit",
    "development", "expansion", "export", "facility", "finance", "financing",
    "for", "government", "in", "infrastructure", "international", "loan",
    "national", "new", "of", "part", "phase", "plant", "programme", "project",
    "provides", "rehabilitation", "record", "refinancing", "reinforcement",
    "stage", "supply", "system", "the", "to", "tranche", "upgrade", "upgrading",
    "with", "works", "linked", "id", "billion", "million", "eximbank",
    "corporation", "company", "chexim", "icbc", "rmb", "usd", "eur",
}

ASSET_FAMILY_PATTERNS = {
    "hydropower": r"\b(?:hydropower|hydroelectric|hydro|dam)\b",
    "thermal_power": r"\b(?:coal|gas|oil|thermal)\b",
    "renewable_power": r"\b(?:solar|wind|geothermal)\b",
    "power_network": r"\b(?:transmission|substation|electrification|power grid|electricity network)\b",
    "railway": r"\b(?:railway|railroad|rolling stock|standard gauge)\b",
    "road_bridge": r"\b(?:road|bridge|highway|expressway)\b",
    "airport": r"\b(?:airport|aviation)\b",
    "port": r"\b(?:port|harbour|harbor)\b",
    "water": r"\b(?:water|sewage|sanitation|wastewater|treatment plant)\b",
    "health": r"\b(?:hospital|medical|health|clinic|pharmaceutical)\b",
    "communications": r"\b(?:telecom|telecommunication|telephony|broadband|fiber|fibre|network|wimax|messaging|collaboration|e government|egovernment)\b",
    "mining": r"\b(?:mine|mining|uranium)\b",
    "housing": r"\b(?:housing|residential|homes)\b",
    "agriculture": r"\b(?:agriculture|irrigation|farm|fishing)\b",
    "public_facility": r"\b(?:stadium|market|slaughterhouse|safe city|surveillance)\b",
}


def read_rows(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def record_key(source: str, record_id: str) -> str:
    return f"{source}:{record_id}"


def normalized_words(value: str) -> list[str]:
    ascii_value = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = ascii_value.encode("ascii", "ignore").decode().casefold()
    ascii_value = re.sub(r"\be[\s-]+government\b", "egovernment", ascii_value)
    return re.findall(r"[a-z0-9]+", ascii_value)


def project_anchor_tokens(value: str) -> set[str]:
    output = set()
    for token in normalized_words(value):
        if token.isdigit() or len(token) < 4 or token in PROJECT_NAME_STOPWORDS:
            continue
        if token.endswith("s") and len(token) > 5:
            token = token[:-1]
        output.add(token)
    return output


def asset_families(value: str) -> set[str]:
    text = " ".join(normalized_words(value))
    return {
        family for family, pattern in ASSET_FAMILY_PATTERNS.items()
        if re.search(pattern, text)
    }


def named_asset_evidence(row: dict) -> str:
    """Return auditable evidence when two catalogs identify the same asset.

    The title matcher deliberately ignores financing boilerplate, but requires
    a distinctive shared name plus compatible sector or asset-family context.
    This avoids treating a shared city name (for example, Malabo) as enough to
    merge unrelated power, water and transport projects.
    """
    left_title = row.get("left_title", "")
    right_title = row.get("right_title", "")
    shared = project_anchor_tokens(left_title) & project_anchor_tokens(right_title)
    strong_anchor = len(shared) >= 2 or any(len(token) >= 4 for token in shared)
    if not strong_anchor:
        return ""

    left_families = asset_families(left_title)
    right_families = asset_families(right_title)
    shared_families = left_families & right_families
    same_sector = (
        bool(row.get("left_sector"))
        and row.get("left_sector") == row.get("right_sector")
    )
    left_qualifiers = qualifiers(left_title)
    right_qualifiers = qualifiers(right_title)
    exact_named_scope = (
        len(shared) >= 2
        and shared == project_anchor_tokens(left_title) == project_anchor_tokens(right_title)
        and left_qualifiers == right_qualifiers
    )
    if exact_named_scope:
        anchors = ", ".join(sorted(shared))
        return f"The financing boilerplate reduces to the same distinctive project name [{anchors}] with matching component qualifiers."

    if left_families and right_families and not shared_families:
        return ""
    family_sector_match = (
        (bool((left_families | right_families) & {"hydropower", "thermal_power", "renewable_power", "power_network"})
         and "energy" in {row.get("left_sector"), row.get("right_sector")})
        or ("communications" in (left_families | right_families)
            and "communications" in {row.get("left_sector"), row.get("right_sector")})
        or ("health" in (left_families | right_families)
            and "health" in {row.get("left_sector"), row.get("right_sector")})
    )
    if not same_sector and not shared_families and not family_sector_match:
        return ""

    anchors = ", ".join(sorted(shared))
    context = (
        f"shared asset family {', '.join(sorted(shared_families))}"
        if shared_families else (
            f"matching sector {row.get('left_sector', '')}"
            if same_sector else "an asset family consistent with the counterpart sector"
        )
    )
    return f"Distinctive name anchor(s) [{anchors}] and {context} identify the same underlying asset."


def normalize_ordinal(value: str) -> str:
    value = value.casefold().strip()
    if value in ORDINALS:
        return ORDINALS[value]
    match = re.fullmatch(r"(\d+)(?:st|nd|rd|th)?", value)
    return match.group(1) if match else value


def qualifiers(title: str) -> dict[str, set[str]]:
    text = re.sub(r"[^a-z0-9]+", " ", str(title or "").casefold()).strip()
    marker_pattern = "|".join(sorted(QUALIFIER_MARKERS))
    ordinal_pattern = (
        r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
        r"\d+(?:st|nd|rd|th)?|i{1,3}|iv|v|vi{0,3}|ix|x"
    )
    output: dict[str, set[str]] = {}
    patterns = [
        rf"\b(?P<value>{ordinal_pattern})\s+(?P<marker>{marker_pattern})\b",
        rf"\b(?P<marker>{marker_pattern})\s*(?P<value>{ordinal_pattern})\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            marker = match.group("marker")
            output.setdefault(marker, set()).add(normalize_ordinal(match.group("value")))
    return output


def qualifier_conflict(left_title: str, right_title: str) -> str:
    left = qualifiers(left_title)
    right = qualifiers(right_title)
    conflicts = []
    for marker in sorted(set(left) & set(right)):
        if left[marker] != right[marker]:
            conflicts.append(f"{marker}: {sorted(left[marker])} vs {sorted(right[marker])}")
    return "; ".join(conflicts)


def normalized_number(value: str, scale: str = "") -> float:
    number = float(value.replace(",", ""))
    multiplier = {
        "billion": 1_000_000_000,
        "bn": 1_000_000_000,
        "b": 1_000_000_000,
        "million": 1_000_000,
        "mn": 1_000_000,
        "m": 1_000_000,
        "thousand": 1_000,
    }.get(scale.casefold(), 1)
    return number * multiplier


def currency_amounts(title: str) -> list[tuple[str, float]]:
    output = []
    for match in CURRENCY_AMOUNT_RE.finditer(str(title or "")):
        currency = match.group("currency").casefold()
        currency = "usd" if currency in {"$", "usd"} else currency
        output.append((currency, normalized_number(match.group("value"), match.group("scale") or "")))
    return output


def explicit_usd_amount_matches(title: str, nominal_value: str) -> bool:
    try:
        nominal = float(nominal_value)
    except (TypeError, ValueError):
        return False
    for currency, value in currency_amounts(title):
        if currency == "usd" and nominal and abs(value - nominal) / nominal <= 0.03:
            return True
    return False


def quantitative_specs(title: str) -> dict[str, set[float]]:
    output: dict[str, set[float]] = {}
    for value, unit in re.findall(r"\b(\d+(?:[.,]\d+)*)\s*(mw|kv|km)\b", str(title or ""), re.IGNORECASE):
        output.setdefault(unit.casefold(), set()).add(float(value.replace(",", "")))
    return output


def matching_quantitative_specs(left_title: str, right_title: str) -> str:
    left = quantitative_specs(left_title)
    right = quantitative_specs(right_title)
    matched = []
    for unit in sorted(set(left) & set(right)):
        overlap = left[unit] & right[unit]
        if overlap:
            matched.append(f"{unit}: {sorted(overlap)}")
    return "; ".join(matched)


def explicit_reference_ids(title: str) -> set[str]:
    text = str(title or "")
    ids: set[str] = set()
    for marker in re.finditer(r"(?:record\s*)?id\s*#?", text, re.IGNORECASE):
        tail = text[marker.end(): marker.end() + 120]
        for value in re.findall(r"#?(\d{2,})", tail):
            ids.add(value)
    if "linked to record" in text.casefold():
        linked_tail = text.casefold().split("linked to record", 1)[1]
        ids.update(re.findall(r"#?(\d{2,})", linked_tail))
    return ids


def month_values(title: str) -> set[str]:
    words = set(re.findall(r"[a-z]+", str(title or "").casefold()))
    return words & MONTHS


def vaccine_doses(title: str) -> set[float]:
    output: set[float] = set()
    pattern = re.compile(
        r"(?<![-\w])(\d+(?:[.,]\d+)*)\s*(million|thousand)?"
        r"(?:\s+[a-z0-9-]+){0,5}\s+doses\b",
        re.IGNORECASE,
    )
    for value, scale in pattern.findall(str(title or "")):
        output.add(normalized_number(value, scale))
    return output


def descriptive_title(source: str, record_id: str, master_by_key: dict[str, dict], fallback: str) -> str:
    """Use the fuller AidData title when a terse CHAPO label hides event details."""
    if source == "chapo":
        counterpart = master_by_key.get(record_key("aiddata", record_id))
        if counterpart and counterpart.get("project_name"):
            return counterpart["project_name"]
    current = master_by_key.get(record_key(source, record_id))
    if current and current.get("project_name"):
        return current["project_name"]
    return fallback


def canonical_event_conflict(left_title: str, right_title: str) -> str:
    left_months, right_months = month_values(left_title), month_values(right_title)
    if left_months and right_months and left_months.isdisjoint(right_months):
        return f"months differ ({sorted(left_months)} vs {sorted(right_months)})"

    left_doses, right_doses = vaccine_doses(left_title), vaccine_doses(right_title)
    if left_doses and right_doses and left_doses.isdisjoint(right_doses):
        return f"vaccine doses differ ({sorted(left_doses)} vs {sorted(right_doses)})"

    left_amounts, right_amounts = currency_amounts(left_title), currency_amounts(right_title)
    if left_amounts and right_amounts:
        left_set = {(currency, round(value, 2)) for currency, value in left_amounts}
        right_set = {(currency, round(value, 2)) for currency, value in right_amounts}
        if left_set.isdisjoint(right_set):
            return f"explicit currencies/amounts differ ({sorted(left_set)} vs {sorted(right_set)})"

    conflict = qualifier_conflict(left_title, right_title)
    if conflict:
        return conflict
    return ""


def comparable_amount_ratio(row: dict) -> float | None:
    try:
        left_amount = float(row.get("left_amount_value", ""))
        right_amount = float(row.get("right_amount_value", ""))
    except (TypeError, ValueError):
        return None
    if not left_amount or not right_amount:
        return None
    return left_amount / right_amount


def catalog_component_alignment(row: dict) -> tuple[str, str] | None:
    """Align CGP numeric subrecords with COFI roman-numbered components."""
    if {row.get("left_source", ""), row.get("right_source", "")} != {"cgp", "cofi"}:
        return None
    if row.get("left_source") == "cgp":
        cgp_id, cgp_title = row.get("left_record_id", ""), row.get("left_title", "")
        cofi_title = row.get("right_title", "")
    else:
        cgp_id, cgp_title = row.get("right_record_id", ""), row.get("right_title", "")
        cofi_title = row.get("left_title", "")
    # The numeric suffix in CGP is not generally a phase number.  The De Aar
    # source pair is the documented exception: its two CGP rows map directly
    # to COFI's DE AAR-I and DE AAR-II components.
    if "de aar" not in " ".join(normalized_words(cgp_title)) or "de aar" not in " ".join(normalized_words(cofi_title)):
        return None
    cgp_match = re.search(r"\.(\d+)$", cgp_id)
    cofi_match = re.search(r"(?:-|\s)([ivx]+|\d+)\s*$", cofi_title, re.IGNORECASE)
    if not cgp_match or not cofi_match:
        return None
    cgp_component = normalize_ordinal(cgp_match.group(1))
    cofi_component = normalize_ordinal(cofi_match.group(1))
    cofi_base = cofi_title[:cofi_match.start()]
    shared_words = set(normalized_words(cgp_title)) & set(normalized_words(cofi_base))
    if len(shared_words) < 2 and not any(len(token) >= 4 for token in shared_words):
        return None
    if cgp_component == cofi_component:
        return "same_project", f"CGP subrecord .{cgp_component} aligns with COFI component {cofi_match.group(1).upper()} for the same named asset."
    return "different_project", f"CGP subrecord .{cgp_component} conflicts with COFI component {cofi_match.group(1).upper()}."


def master_index(master_rows: list[dict]) -> tuple[dict[str, dict], Counter, dict[str, set[str]]]:
    by_key = {
        record_key(row.get("source_db", ""), row.get("record_id", "")): row
        for row in master_rows
    }
    sizes = Counter(row.get("project_match_id", "") for row in master_rows)
    statuses: dict[str, set[str]] = {}
    for row in master_rows:
        statuses.setdefault(row.get("project_match_id", ""), set()).add(row.get("match_status", ""))
    return by_key, sizes, statuses


class UnionFind:
    def __init__(self, keys: list[str]):
        self.parent = {key: key for key in keys}

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


def reviewed_equivalence(master_rows: list[dict], decisions: dict[str, dict]) -> UnionFind:
    """Expand reviewed same-project links only through shared source IDs.

    AidData/CHAPO and CLA/CODF/CGEF reuse identifiers across their paired
    records.  This permits safe reciprocal propagation without treating every
    pre-existing fuzzy-match group as reviewed evidence.
    """
    keys = [record_key(row.get("source_db", ""), row.get("record_id", "")) for row in master_rows]
    uf = UnionFind(keys)
    equivalent: dict[tuple[str, str], list[str]] = {}
    for row in master_rows:
        source = row.get("source_db", "")
        item_id = row.get("record_id", "")
        if source in {"aiddata", "chapo"} and item_id.isdigit():
            group = ("aiddata_chapo_id", item_id)
        elif source in RELATED_FINANCE_CATALOGS and item_id:
            group = ("finance_catalog_id", item_id)
        else:
            continue
        equivalent.setdefault(group, []).append(record_key(source, item_id))
    for members in equivalent.values():
        for member in members[1:]:
            uf.union(members[0], member)
    for item in decisions.values():
        if item.get("review_decision") == "same_project":
            uf.union(
                record_key(item.get("left_source", ""), item.get("left_record_id", "")),
                record_key(item.get("right_source", ""), item.get("right_record_id", "")),
            )
    return uf


def final_entity_equivalence(master_rows: list[dict], decisions: dict[str, dict]) -> UnionFind:
    """Mirror the entity builder for contradiction prevention, not evidence."""
    keys = [record_key(row.get("source_db", ""), row.get("record_id", "")) for row in master_rows]
    uf = UnionFind(keys)
    groups: dict[str, list[str]] = {}
    for row in master_rows:
        groups.setdefault(row.get("project_match_id", ""), []).append(
            record_key(row.get("source_db", ""), row.get("record_id", ""))
        )
    for members in groups.values():
        for member in members[1:]:
            uf.union(members[0], member)
    for item in decisions.values():
        if item.get("review_decision") == "same_project":
            uf.union(
                record_key(item.get("left_source", ""), item.get("left_record_id", "")),
                record_key(item.get("right_source", ""), item.get("right_record_id", "")),
            )
    return uf


def difference_separates_roots(
    graph: UnionFind,
    left_key: str,
    right_key: str,
    reviewed_differences: list[tuple[str, str]],
) -> bool:
    current_roots = frozenset({graph.find(left_key), graph.find(right_key)})
    return any(
        current_roots == frozenset({graph.find(a), graph.find(b)})
        for a, b in reviewed_differences
    )


def strong_difference_recommendation(row: dict, master_by_key: dict[str, dict]) -> dict | None:
    """Classify hard negative evidence before any transitive same-project merge."""
    left_source = row.get("left_source", "")
    right_source = row.get("right_source", "")
    left_id = row.get("left_record_id", "")
    right_id = row.get("right_record_id", "")

    component_alignment = catalog_component_alignment(row)
    if component_alignment and component_alignment[0] == "different_project":
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "conflicting_catalog_component_ordinal",
            "rule_evidence": component_alignment[1],
        }

    if left_source == "aiddata" and right_source == "chapo" and left_id != right_id:
        left_full = descriptive_title(left_source, left_id, master_by_key, row.get("left_title", ""))
        right_full = descriptive_title(right_source, right_id, master_by_key, row.get("right_title", ""))
        event_conflict = canonical_event_conflict(left_full, right_full)
        if event_conflict:
            return {
                "review_decision": "different_project",
                "confidence": "high",
                "rule_id": "conflicting_canonical_event_details",
                "rule_evidence": f"The fuller source descriptions identify different events: {event_conflict}.",
            }

    if (
        left_source in RELATED_FINANCE_CATALOGS
        and right_source in RELATED_FINANCE_CATALOGS
        and left_id and right_id and left_id != right_id
    ):
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "distinct_related_catalog_identifiers",
            "rule_evidence": f"Related finance catalogs use distinct project identifiers ({left_id} vs {right_id}).",
        }

    if (
        row.get("left_fund_type", "")
        and row.get("right_fund_type", "")
        and row["left_fund_type"] != row["right_fund_type"]
    ):
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "conflicting_financing_instruments",
            "rule_evidence": f"Fund types conflict ({row['left_fund_type']} vs {row['right_fund_type']}).",
        }

    conflict = qualifier_conflict(row.get("left_title", ""), row.get("right_title", ""))
    if conflict:
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "conflicting_component_ordinal",
            "rule_evidence": f"Titles identify different components: {conflict}.",
        }
    return None


def recommendation(
    row: dict,
    master_by_key: dict[str, dict],
    group_sizes: Counter,
    group_statuses: dict[str, set[str]],
    reviewed_links: UnionFind,
    entity_links: UnionFind,
    reviewed_differences: list[tuple[str, str]],
) -> dict | None:
    left_source = row.get("left_source", "")
    right_source = row.get("right_source", "")
    left_id = row.get("left_record_id", "")
    right_id = row.get("right_record_id", "")
    left = master_by_key.get(record_key(left_source, left_id))
    right = master_by_key.get(record_key(right_source, right_id))
    left_key = record_key(left_source, left_id)
    right_key = record_key(right_source, right_id)

    if difference_separates_roots(entity_links, left_key, right_key, reviewed_differences):
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "reviewed_difference_final_entity_guard",
            "rule_evidence": "The proposed link would collapse records across an established different-project boundary.",
        }

    component_alignment = catalog_component_alignment(row)
    if component_alignment and component_alignment[0] == "same_project":
        return {
            "review_decision": "same_project",
            "confidence": "high",
            "rule_id": "matching_catalog_component_ordinal",
            "rule_evidence": component_alignment[1],
        }

    if reviewed_links.find(left_key) == reviewed_links.find(right_key):
        return {
            "review_decision": "same_project",
            "confidence": "high",
            "rule_id": "reviewed_same_equivalence_closure",
            "rule_evidence": "The pair is connected by a reviewed same-project decision and equivalent source identifiers.",
        }

    if difference_separates_roots(reviewed_links, left_key, right_key, reviewed_differences):
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "reviewed_difference_equivalence_closure",
            "rule_evidence": "An equivalent reciprocal/source-catalog pair was already reviewed as different-project.",
        }

    if left and right:
        left_group = left.get("project_match_id", "")
        right_group = right.get("project_match_id", "")
        if (
            left_group and left_group == right_group and group_sizes[left_group] > 1
            and group_statuses.get(left_group) == {"direct_reference"}
            and left.get("match_status") == "direct_reference"
            and right.get("match_status") == "direct_reference"
        ):
            return {
                "review_decision": "same_project",
                "confidence": "high",
                "rule_id": "same_established_entity",
                "rule_evidence": f"Both records already resolve to {left_group} through a direct, automatic, or reviewed link.",
            }

    if left_source == "aiddata" and right_source in (RELATED_FINANCE_CATALOGS | {"cofi"}):
        title_conflict = qualifier_conflict(row.get("left_title", ""), row.get("right_title", ""))
        if not title_conflict and explicit_usd_amount_matches(
            row.get("left_title", ""), row.get("right_amount_value", "")
        ):
            return {
                "review_decision": "same_project",
                "confidence": "high",
                "rule_id": "matching_original_usd_commitment",
                "rule_evidence": "The AidData title states the same original USD commitment as the finance-catalog record, with compatible project title and financing type.",
            }
        matched_specs = matching_quantitative_specs(
            row.get("left_title", ""), row.get("right_title", "")
        )
        if not title_conflict and matched_specs:
            return {
                "review_decision": "same_project",
                "confidence": "high",
                "rule_id": "matching_named_project_specs",
                "rule_evidence": f"The named infrastructure project has matching technical specifications ({matched_specs}) and no phase/lot conflict.",
            }

    if left_source == "aiddata" and right_source == "chapo" and left_id != right_id:
        left_full = descriptive_title(left_source, left_id, master_by_key, row.get("left_title", ""))
        right_full = descriptive_title(right_source, right_id, master_by_key, row.get("right_title", ""))
        event_conflict = canonical_event_conflict(left_full, right_full)
        if event_conflict:
            return {
                "review_decision": "different_project",
                "confidence": "high",
                "rule_id": "conflicting_canonical_event_details",
                "rule_evidence": f"The fuller source descriptions identify different events: {event_conflict}.",
            }

        if right_id in explicit_reference_ids(left_full):
            ratio = comparable_amount_ratio(row)
            same_fund_type = (
                bool(row.get("left_fund_type"))
                and row.get("left_fund_type") == row.get("right_fund_type")
            )
            if same_fund_type and (ratio is None or 0.7 <= ratio <= 1.4):
                return {
                    "review_decision": "same_project",
                    "confidence": "high",
                    "rule_id": "explicit_cross_source_record_link",
                    "rule_evidence": (
                        f"The fuller AidData title explicitly links record {right_id}; "
                        + (f"amounts are consistent across price bases (ratio {ratio:.3f})." if ratio is not None else "no amount conflict is present.")
                    ),
                }

    if (
        left_source in RELATED_FINANCE_CATALOGS
        and right_source in RELATED_FINANCE_CATALOGS
        and left_id and right_id and left_id != right_id
    ):
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "distinct_related_catalog_identifiers",
            "rule_evidence": f"Related finance catalogs use distinct project identifiers ({left_id} vs {right_id}).",
        }

    if (
        row.get("left_fund_type", "")
        and row.get("right_fund_type", "")
        and row["left_fund_type"] != row["right_fund_type"]
    ):
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "conflicting_financing_instruments",
            "rule_evidence": f"Fund types conflict ({row['left_fund_type']} vs {row['right_fund_type']}).",
        }

    conflict = qualifier_conflict(row.get("left_title", ""), row.get("right_title", ""))
    if conflict:
        return {
            "review_decision": "different_project",
            "confidence": "high",
            "rule_id": "conflicting_component_ordinal",
            "rule_evidence": f"Titles identify different components: {conflict}.",
        }

    source_pair = {left_source, right_source}
    eligible_catalog_pair = (
        bool(source_pair & ASSET_CATALOGS)
        or (
            source_pair != {"aiddata", "chapo"}
            and bool(source_pair & {"aiddata", "chapo"})
            and bool(source_pair & RELATED_FINANCE_CATALOGS)
        )
    )
    if eligible_catalog_pair:
        left_text = " ".join(normalized_words(row.get("left_title", "")))
        right_id_text = row.get("right_record_id", "").casefold()
        if left_source == "aiddata" and right_source == "cofi":
            if "additional" in left_text:
                return None
            if "equity bridge" in left_text and right_id_text.endswith(":debt"):
                return None
        evidence = named_asset_evidence(row)
        if evidence:
            return {
                "review_decision": "same_project",
                "confidence": "high",
                "rule_id": "distinctive_named_asset_with_compatible_context",
                "rule_evidence": evidence,
            }
    return None


def preserved_origin(row: dict) -> tuple[str, str, str, str]:
    notes = row.get("review_notes", "") or ""
    match = re.match(r"(AUTO_REVIEW|BATCH_REVIEW|ASSISTANT_REVIEW)\s+([^:]+):\s*(.*)", notes)
    if match:
        origin = {
            "AUTO_REVIEW": "auto_prior",
            "BATCH_REVIEW": "batch",
            "ASSISTANT_REVIEW": "assistant",
        }[match.group(1)]
        return origin, "high", match.group(2).strip(), match.group(3).strip()
    if notes.startswith("HUMAN_REVIEW"):
        return "human", "human_confirmed", "imported_human_decision", notes
    return "existing", "reviewed", "preserved_existing_decision", notes or "Preserved from the current project decision file."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--master", required=True, type=Path)
    parser.add_argument("--existing", type=Path)
    parser.add_argument("--assistant-review", type=Path)
    parser.add_argument("--user-export", type=Path)
    parser.add_argument("--prior-audit", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument(
        "--complete", action="store_true",
        help="Resolve every remaining pair conservatively after high-confidence rules finish.",
    )
    args = parser.parse_args()

    queue_rows = read_rows(args.queue)
    master_rows = read_rows(args.master)
    queue_by_id = {row["candidate_id"]: row for row in queue_rows}
    prior_audit_by_id = {
        row.get("candidate_id", ""): row
        for row in read_rows(args.prior_audit)
        if row.get("candidate_id", "")
    }
    master_by_key, group_sizes, group_statuses = master_index(master_rows)
    decisions: dict[str, dict] = {}
    origins: dict[str, tuple[str, str, str, str]] = {}

    for row in read_rows(args.existing):
        candidate_id = row.get("candidate_id", "").strip()
        if candidate_id:
            decisions[candidate_id] = {column: row.get(column, "") for column in DECISION_COLUMNS}
            origins[candidate_id] = preserved_origin(row)

    for row in read_rows(args.assistant_review):
        candidate_id = row.get("candidate_id", "").strip()
        if not candidate_id:
            continue
        item = {column: row.get(column, "") for column in DECISION_COLUMNS}
        if not item["review_notes"]:
            item["review_notes"] = "ASSISTANT_REVIEW high_confidence: Reviewed from full project titles and distinguishing fields."
        decisions[candidate_id] = item
        origins[candidate_id] = preserved_origin(item)

    for row in read_rows(args.user_export):
        candidate_id = row.get("candidate_id", "").strip()
        if not candidate_id:
            continue
        item = {column: row.get(column, "") for column in DECISION_COLUMNS}
        if not item["review_notes"]:
            item["review_notes"] = "HUMAN_REVIEW imported from browser export; this decision takes precedence over automated rules."
        decisions[candidate_id] = item
        origins[candidate_id] = ("human", "human_confirmed", "imported_human_decision", "Imported from the user's browser review export.")

    now = datetime.now(timezone.utc).isoformat()
    added = []
    # Lock explicit negative evidence first.  This makes the result independent
    # of queue ordering and prevents a later asset-level link from bridging
    # distinct tranches, lots, locations or financing instruments.
    for row in queue_rows:
        candidate_id = row["candidate_id"]
        if candidate_id in decisions:
            continue
        result = strong_difference_recommendation(row, master_by_key)
        if result is None:
            continue
        item = {
            "candidate_id": candidate_id,
            "left_source": row["left_source"],
            "left_record_id": row["left_record_id"],
            "right_source": row["right_source"],
            "right_record_id": row["right_record_id"],
            "review_decision": result["review_decision"],
            "review_notes": f"BATCH_REVIEW {result['rule_id']}: {result['rule_evidence']}",
            "reviewed_at": now,
        }
        decisions[candidate_id] = item
        origins[candidate_id] = ("batch", result["confidence"], result["rule_id"], result["rule_evidence"])
        added.append(item)

    reviewed_links = reviewed_equivalence(master_rows, decisions)
    entity_links = final_entity_equivalence(master_rows, decisions)
    reviewed_differences = [
        (
            record_key(item.get("left_source", ""), item.get("left_record_id", "")),
            record_key(item.get("right_source", ""), item.get("right_record_id", "")),
        )
        for item in decisions.values()
        if item.get("review_decision") == "different_project"
    ]
    while True:
        pass_added = 0
        for row in queue_rows:
            candidate_id = row["candidate_id"]
            if candidate_id in decisions:
                continue
            result = recommendation(
                row, master_by_key, group_sizes, group_statuses,
                reviewed_links, entity_links, reviewed_differences,
            )
            if result is None:
                continue
            item = {
                "candidate_id": candidate_id,
                "left_source": row["left_source"],
                "left_record_id": row["left_record_id"],
                "right_source": row["right_source"],
                "right_record_id": row["right_record_id"],
                "review_decision": result["review_decision"],
                "review_notes": f"BATCH_REVIEW {result['rule_id']}: {result['rule_evidence']}",
                "reviewed_at": now,
            }
            decisions[candidate_id] = item
            origins[candidate_id] = ("batch", result["confidence"], result["rule_id"], result["rule_evidence"])
            added.append(item)
            pass_added += 1
            if result["review_decision"] == "same_project":
                left_key = record_key(row["left_source"], row["left_record_id"])
                right_key = record_key(row["right_source"], row["right_record_id"])
                reviewed_links.union(left_key, right_key)
                entity_links.union(left_key, right_key)
        if pass_added == 0:
            break

    if args.complete:
        for row in queue_rows:
            candidate_id = row["candidate_id"]
            if candidate_id in decisions:
                continue
            left_key = record_key(row["left_source"], row["left_record_id"])
            right_key = record_key(row["right_source"], row["right_record_id"])
            if entity_links.find(left_key) == entity_links.find(right_key):
                decision = "same_project"
                confidence = "high"
                rule_id = "final_same_equivalence_closure"
                evidence = "The endpoints resolve to the same reviewed source-identifier or named-asset equivalence class."
            else:
                decision = "different_project"
                confidence = "moderate"
                rule_id = "separate_after_full_evidence_check"
                evidence = (
                    "No shared source identifier, compatible named-asset anchor, matching original commitment, "
                    "technical specification, or explicit cross-source link supports consolidation; the records remain separate."
                )
            item = {
                "candidate_id": candidate_id,
                "left_source": row["left_source"],
                "left_record_id": row["left_record_id"],
                "right_source": row["right_source"],
                "right_record_id": row["right_record_id"],
                "review_decision": decision,
                "review_notes": f"BATCH_REVIEW {rule_id}: {evidence}",
                "reviewed_at": now,
            }
            decisions[candidate_id] = item
            origins[candidate_id] = ("batch_complete", confidence, rule_id, evidence)
            added.append(item)

    ordered = sorted(decisions.values(), key=lambda row: row["candidate_id"])
    write_rows(args.output, ordered, DECISION_COLUMNS)

    audit_rows = []
    for item in ordered:
        candidate_id = item["candidate_id"]
        queue = queue_by_id.get(candidate_id, {})
        prior = prior_audit_by_id.get(candidate_id, {})
        origin, confidence, rule_id, evidence = origins[candidate_id]
        audit_rows.append({
            **item,
            **{
                column: queue.get(column, "") or prior.get(column, "")
                for column in AUDIT_COLUMNS
                if column not in item
                and column not in {"decision_origin", "confidence", "rule_id", "rule_evidence"}
            },
            "decision_origin": origin,
            "confidence": confidence,
            "rule_id": rule_id,
            "rule_evidence": evidence,
        })
    write_rows(args.audit, audit_rows, AUDIT_COLUMNS)

    print({
        "input_queue": len(queue_rows),
        "combined_decisions": len(ordered),
        "new_batch_decisions": len(added),
        "remaining_unreviewed": len(queue_rows) - sum(row["candidate_id"] in decisions for row in queue_rows),
        "decision_counts": dict(Counter(row["review_decision"] for row in ordered)),
        "new_rule_counts": dict(Counter(origins[row["candidate_id"]][2] for row in added)),
    })


if __name__ == "__main__":
    main()
