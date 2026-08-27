# 中非援助数据镜鉴

China–Africa Aid Data Atlas is a bilingual, static research platform for comparing multiple databases on China–Africa aid and development finance.

## Website

<https://y6492996-code.github.io/china-africa-aid-atlas/>

## Local development

```powershell
.\start-local.ps1
```

For normal use, double-click `start-site.cmd`. It starts the site in the background, so the launcher window can be closed. Run it again whenever Windows restarts or the local address stops responding.

Then open <http://127.0.0.1:5173>.

The match-review workbench is available at <http://127.0.0.1:5173/#/review>. Decisions are stored in the current browser, can be imported/exported as `match_review_decisions.csv`, and are applied on rebuild when placed at `data/review/match_review_decisions.csv`. The pipeline then produces `match_review_decisions_applied.csv`, `confirmed_match_groups.csv`, and a one-row-per-entity `project_entity_index.csv`. The entity index deliberately contains no cross-source amount.

The conservative review assistant is implemented in `scripts/generate_conservative_review.py`. It writes a full audit file to `data/review/match_review_recommendations.csv`, but only high-confidence decisions enter `match_review_decisions.csv`; ambiguous cases remain explicitly uncertain.

The empirical findings layer is available at <http://127.0.0.1:5173/#/findings>. It profiles 14 source-specific metrics, annual trends and country summaries, then calculates Spearman and Kendall rank correlations on pairwise-complete observations. It also reports BIC-selected, Bai-Perron-style candidate mean shifts and compares baseline correlations with a sensitivity panel that excludes flagged project-level outliers. CODF/CLA/CGEF and AidData/CHAPO comparisons carry lineage warnings. Cross-source monetary levels are never combined, and the primary panel is never altered by the sensitivity check.

The source datasets remain outside the repository. Set `ATLAS_RAW_DATA_DIR` to the local clean-data directory before running the data build introduced in Stage 1.

## Build the research panels

Set `ATLAS_RAW_DATA_DIR` to the local clean-data directory. Rebuild the analytical tables, validation report, website downloads and dashboard with:

```powershell
.\build-data.ps1
```

The formal panel contains 54 sovereign African countries and 25 years (2000–2024). Fuzzy project matches remain auditable in `match_candidates.csv`, while unresolved pairs are isolated in `match_review_queue.csv`. The build also produces source-level completeness, panel missingness and robust outlier-review tables. Missing amounts are not silently converted to zero, and outlier candidates are never automatically removed.

## Data boundary

- Raw CSV, XLSX and DTA files are not committed or copied into `public/`.
- Databases remain statistically independent unless a comparison is explicitly compatible.
- Candidate project matches require human review.
- Missing values are not silently replaced with zero.
