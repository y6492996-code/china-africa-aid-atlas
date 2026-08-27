#!/usr/bin/env python3
"""Build compact, auditable dashboard data from the cleaned CSV collection.

The script aggregates record counts across sources, but never adds monetary
values from different databases together. Source-specific metrics retain their
original units and labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SOURCE_SPECS = [
    {
        "id": "aiddata", "label": "AidData", "file": "aiddata_africa_clean.csv",
        "country": "Country_of_Activity", "country_kind": "name", "year": "Commitment_Year",
        "metric": "Clean_Amount_USD", "metric_label": "项目承诺金额", "unit": "USD",
    },
    {
        "id": "codf", "label": "CODF", "file": "bu_codf_africa_clean.csv",
        "country": "国家", "country_kind": "name", "year": "年份",
        "metric": "Clean_Amount_USD", "metric_label": "贷款金额", "unit": "USD",
    },
    {
        "id": "cla", "label": "CLA", "file": "cla_africa_clean.csv",
        "country": "country_en_standard", "country_kind": "name", "year": "Year",
        "metric": "Loan_USD_M", "metric_label": "贷款金额", "unit": "USD million",
    },
    {
        "id": "debt", "label": "Debt relief", "file": "cancellation_africa_clean.csv",
        "country": "ISO_A3", "country_kind": "iso", "year": "Year",
        "metric": "Cancel_Amount_USD_Mn", "metric_label": "债务取消金额", "unit": "USD million",
    },
    {
        "id": "debt", "label": "Debt relief", "file": "restructuring_africa_clean.csv",
        "country": "ISO_A3", "country_kind": "iso", "year": "Year_Numeric",
        "metric": "Restructure_Amount_USD_Mn", "metric_label": "债务重组金额", "unit": "USD million",
    },
    {
        "id": "exports", "label": "Aid exports", "file": "africa_aid_data_clean.csv",
        "country": "iso3c", "country_kind": "iso", "year": "yearmonth",
        "metric": "aid_total", "metric_label": "援助出口价值", "unit": "source unit",
    },
    {
        "id": "fdi", "label": "FDI", "file": "fdi_africa_panel.csv",
        "country": "ISO_A3", "country_kind": "iso", "year": "Year",
        "metric": "Flow_USD", "metric_label": "直接投资流量", "unit": "USD",
    },
    {
        "id": "cofi", "label": "COFI", "file": "cofi_africa_clean.csv",
        "country": "country_iso3c", "country_kind": "iso", "year": "commissioning_year",
        "metric": "total_investment_amount_USD", "metric_label": "总投资额", "unit": "USD",
    },
    {
        "id": "cgef", "label": "CGEF", "file": "CGEF_Africa_2024_Cleaned.csv",
        "country": "国家", "country_kind": "name", "year": "年份",
        "metric": "贷款金额（百万美元）", "metric_label": "能源贷款金额", "unit": "USD million",
    },
    {
        "id": "cgp", "label": "CGP", "file": "CGP_Africa_2025_Cleaned.csv",
        "country": "国家", "country_kind": "name", "year": "投产年份",
        "metric": "产能 （兆瓦）", "metric_label": "装机容量", "unit": "MW",
    },
    {
        "id": "chapo", "label": "CHAPO", "file": "chapo_africa_clean.csv",
        "country": "country_iso", "country_kind": "iso", "year": "Commitment_Year",
        "metric": "Amount_USD", "metric_label": "卫生援助金额", "unit": "USD",
    },
    {
        "id": "ihme", "label": "IHME DAH", "file": "ihme_dah_africa_clean.csv",
        "country": "recipient_isocode", "country_kind": "iso", "year": "year",
        "metric": "dah_23_million", "metric_label": "卫生发展援助", "unit": "2023 USD million",
    },
    {
        "id": "china_eu_finance", "label": "China–EU finance", "file": "china_africa_finance_cleaned.csv",
        "country": "CountryCode", "country_kind": "iso", "year": "year",
        "metric": None, "metric_label": None, "unit": None,
    },
]


def norm_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    value = value.replace("&", " and ").replace("’", "'")
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value)


def parse_year(value: str) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", value or "")
    if not match:
        return None
    year = int(match.group(0))
    return year if 1900 <= year <= 2100 else None


def parse_number(value: str) -> float | None:
    text = (value or "").strip().replace(",", "")
    if not text or text.casefold() in {"na", "nan", "none", "."}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        yield from csv.DictReader(handle)


def load_country_reference(data_dir: Path):
    by_iso = {}
    by_name = {}
    path = data_dir / "fdi_africa_metadata.csv"
    for row in read_rows(path):
        iso = (row.get("ISO_A3") or "").strip().upper()
        if not iso:
            continue
        record = {
            "iso3": iso,
            "nameEn": (row.get("Country_EN") or iso).strip(),
            "nameZh": (row.get("Country_CN") or row.get("Country_EN") or iso).strip(),
            "sovereign": (row.get("Is_Sovereign") or "").casefold() == "true",
        }
        by_iso[iso] = record
        for name in (record["nameEn"], record["nameZh"]):
            by_name[norm_name(name)] = iso

    aliases = {
        "central african republic": "CAF", "the gambia": "GMB", "gambia": "GMB",
        "republic of the congo": "COG", "congo republic": "COG", "congo brazzaville": "COG", "congo": "COG",
        "democratic republic of the congo": "COD", "dr congo": "COD", "drc": "COD",
        "ivory coast": "CIV", "côte d'ivoire": "CIV", "cabo verde": "CPV",
        "swaziland": "SWZ", "united republic of tanzania": "TZA",
        "sao tome and principe": "STP", "são tomé and príncipe": "STP",
        "regional africa": "AFR", "regional, africa": "AFR", "regional": "AFR", "区域性": "AFR",
    }
    for name, iso in aliases.items():
        by_name[norm_name(name)] = iso
    return by_iso, by_name


def empty_country(reference: dict):
    return {
        **reference,
        "records": 0,
        "sourceCounts": Counter(),
        "yearCounts": Counter(),
        "yearMin": None,
        "yearMax": None,
        "metrics": {},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--geojson", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--africa-geojson", required=True, type=Path)
    args = parser.parse_args()

    by_iso, by_name = load_country_reference(args.data_dir)
    countries = {iso: empty_country(record) for iso, record in by_iso.items() if iso != "SDN-H"}
    source_audit = {}
    source_defs = {}
    unmapped = Counter()

    for spec in SOURCE_SPECS:
        path = args.data_dir / spec["file"]
        rows = 0
        mapped = 0
        metric_known = 0
        local_years = []
        header = []

        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            for row in reader:
                rows += 1
                raw_country = (row.get(spec["country"]) or "").strip()
                if spec["country_kind"] == "iso":
                    iso = raw_country.upper()
                else:
                    iso = by_name.get(norm_name(raw_country), "")

                if iso == "AFR" or iso not in countries:
                    if raw_country:
                        unmapped[f'{spec["id"]}:{raw_country}'] += 1
                    continue

                mapped += 1
                country = countries[iso]
                country["records"] += 1
                country["sourceCounts"][spec["id"]] += 1

                year = parse_year(row.get(spec["year"]) or "")
                if year is not None:
                    local_years.append(year)
                    country["yearCounts"][year] += 1
                    country["yearMin"] = year if country["yearMin"] is None else min(country["yearMin"], year)
                    country["yearMax"] = year if country["yearMax"] is None else max(country["yearMax"], year)

                if spec["metric"]:
                    value = parse_number(row.get(spec["metric"]) or "")
                    metric = country["metrics"].setdefault(spec["id"], {
                        "value": 0.0, "known": 0, "label": spec["metric_label"], "unit": spec["unit"],
                    })
                    if value is not None:
                        metric["value"] += value
                        metric["known"] += 1
                        metric_known += 1

        source_audit.setdefault(spec["id"], {
            "id": spec["id"], "label": spec["label"], "files": [], "rows": 0,
            "mappedRows": 0, "metricKnown": 0, "yearMin": None, "yearMax": None, "columns": [],
        })
        audit = source_audit[spec["id"]]
        audit["files"].append(spec["file"])
        audit["rows"] += rows
        audit["mappedRows"] += mapped
        audit["metricKnown"] += metric_known
        audit["columns"].append({"file": spec["file"], "fields": header})
        if local_years:
            low, high = min(local_years), max(local_years)
            audit["yearMin"] = low if audit["yearMin"] is None else min(audit["yearMin"], low)
            audit["yearMax"] = high if audit["yearMax"] is None else max(audit["yearMax"], high)
        source_defs[spec["id"]] = {
            "id": spec["id"], "label": spec["label"], "metricLabel": spec["metric_label"], "unit": spec["unit"],
        }

    compact_countries = {}
    for iso, country in countries.items():
        if country["records"] == 0:
            continue
        source_counts = dict(country["sourceCounts"].most_common())
        metrics = {}
        for source_id, metric in country["metrics"].items():
            metrics[source_id] = {**metric, "value": round(metric["value"], 6)}
        compact_countries[iso] = {
            "iso3": iso,
            "nameEn": country["nameEn"],
            "nameZh": country["nameZh"],
            "records": country["records"],
            "sourceCount": len(source_counts),
            "sourceCounts": source_counts,
            "yearMin": country["yearMin"],
            "yearMax": country["yearMax"],
            "yearCounts": {str(year): count for year, count in sorted(country["yearCounts"].items())},
            "metrics": metrics,
        }

    with args.geojson.open("r", encoding="utf-8") as handle:
        world = json.load(handle)
    features = []
    for feature in world.get("features", []):
        props = feature.get("properties") or {}
        if props.get("CONTINENT") != "Africa":
            continue
        iso = props.get("ISO_A3") or props.get("ADM0_A3")
        if iso == "-99":
            iso = props.get("ADM0_A3")
        features.append({
            "type": "Feature",
            "properties": {"iso3": iso, "name": props.get("ADMIN") or props.get("NAME") or iso},
            "geometry": feature.get("geometry"),
        })
    africa = {"type": "FeatureCollection", "features": features}

    sources = []
    for source_id, audit in source_audit.items():
        mapped = audit["mappedRows"]
        audit["mappedRate"] = round(mapped / audit["rows"], 4) if audit["rows"] else 0
        audit["metricKnownRate"] = round(audit["metricKnown"] / mapped, 4) if mapped else 0
        sources.append({**source_defs[source_id], **audit})

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": "Record counts may be compared across sources; source-specific monetary metrics retain original units and are never added across databases.",
        "global": {
            "sourceCount": len(source_audit),
            "countryCount": len(compact_countries),
            "recordCount": sum(country["records"] for country in compact_countries.values()),
            "yearMin": min(country["yearMin"] for country in compact_countries.values() if country["yearMin"] is not None),
            "yearMax": max(country["yearMax"] for country in compact_countries.values() if country["yearMax"] is not None),
        },
        "sources": sources,
        "countries": compact_countries,
        "unmapped": [{"value": key, "rows": value} for key, value in unmapped.most_common()],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.africa_geojson.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    args.africa_geojson.write_text(json.dumps(africa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(json.dumps({
        "global": output["global"],
        "sources": [{"id": s["id"], "rows": s["rows"], "mapped": s["mappedRows"], "fields": sum(len(c["fields"]) for c in s["columns"])} for s in sources],
        "unmappedTop": output["unmapped"][:15],
        "africaFeatures": len(features),
    }, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
