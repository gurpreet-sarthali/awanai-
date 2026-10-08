"""Generate Phase 4 charts from Phase 3 results and the verified dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visualization.chart_engine import create_chart
from visualization.chart_selector import select_chart


def _rows(items: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(items)


def _job(name: str, analysis: dict[str, object], dataframe: pd.DataFrame, filename: str) -> dict[str, object]:
    selection = select_chart(analysis)
    if not selection["valid"]:
        return {"name": name, "success": False, "errors": selection["errors"]}
    specification = {**selection["specification"], "filename": filename}
    chart_data = dataframe
    if "group" in chart_data.columns and "value" in chart_data.columns:
        chart_data = chart_data.rename(columns={"group": str(analysis.get("group_by", "group")), "value": str(analysis.get("metric", "value"))})
    metadata = create_chart(chart_data, specification, ROOT / "visualization" / "results")
    return {"name": name, "specification": specification, **metadata}


def main() -> int:
    phase3_path = ROOT / "analytics" / "results" / "placement_analytics.json"
    raw_path = ROOT / "data" / "raw" / "placement.csv"
    if not phase3_path.is_file():
        print(f"ERROR: Phase 3 results not found: {phase3_path}", file=sys.stderr)
        return 1
    if not raw_path.is_file():
        print(f"ERROR: Dataset not found: {raw_path}", file=sys.stderr)
        return 1

    phase3 = json.loads(phase3_path.read_text(encoding="utf-8"))
    raw = pd.read_csv(raw_path)
    grouped = phase3["grouped_analytics"]
    placement = phase3["placement_metrics"]
    jobs = [
        ("Placement Rate by Internship", {"analysis_type": "grouped_metric", "group_by": "Internship_Experience", "metric": "placement_rate", "value_type": "percentage"}, _rows(grouped["placement_rate_by_internship"]), "placement_rate_by_internship.png"),
        ("Placement Rate by CGPA Group", {"analysis_type": "grouped_metric", "group_by": "CGPA_Group", "metric": "placement_rate", "value_type": "percentage"}, _rows(grouped["placement_rate_by_cgpa_group"]), "placement_rate_by_cgpa_group.png"),
        ("Placement Rate by Project Group", {"analysis_type": "grouped_metric", "group_by": "Project_Group", "metric": "placement_rate", "value_type": "percentage"}, _rows(grouped["placement_rate_by_project_group"]), "placement_rate_by_project_group.png"),
        ("Average CGPA by Placement", {"analysis_type": "grouped_metric", "group_by": "Placement", "metric": "average_cgpa"}, _rows(grouped["average_cgpa_by_placement"]), "average_cgpa_by_placement.png"),
        ("Average Communication by Placement", {"analysis_type": "grouped_metric", "group_by": "Placement", "metric": "average_communication"}, _rows(grouped["average_communication_by_placement"]), "average_communication_by_placement.png"),
        ("Placement Distribution", {"analysis_type": "percentage_distribution", "x": "Placement", "y": "student_count", "metric": "student_count", "category_count": 2, "title": "Placement Distribution"}, _rows([{"group": key, "value": value} for key, value in placement["placement_count_by_status"].items()]).rename(columns={"group": "Placement", "value": "student_count"}), "placement_distribution.png"),
        ("CGPA Distribution", {"analysis_type": "numerical_distribution", "y": "CGPA", "metric": "CGPA", "title": "CGPA Distribution", "x_label": "CGPA"}, raw, "cgpa_distribution.png"),
        ("CGPA vs IQ", {"analysis_type": "numerical_relationship", "x": "CGPA", "y": "IQ", "group_by": "Placement", "title": "CGPA vs IQ by Placement"}, raw, "cgpa_vs_iq.png"),
        ("CGPA by Placement", {"analysis_type": "distribution_comparison", "x": "Placement", "y": "CGPA", "title": "CGPA Distribution by Placement"}, raw, "cgpa_by_placement.png"),
        ("Synthetic Time Series Example", {"analysis_type": "time_series", "x": "period", "y": "value", "title": "Synthetic Time-Series Example", "x_label": "Period", "y_label": "Value"}, pd.DataFrame({"period": ["Q1", "Q2", "Q3", "Q4"], "value": [10, 14, 12, 18]}), "synthetic_time_series.png"),
    ]

    manifest: list[dict[str, object]] = []
    print("=== VISUALIZATION ENGINE ===")
    for index, (name, analysis, dataframe, filename) in enumerate(jobs, start=1):
        result = _job(name, analysis, dataframe, filename)
        manifest.append(result)
        status = "SUCCESS" if result.get("success") else "ERROR"
        print(f"\n{index}. {name}\n   Chart: {result.get('chart_type', 'unselected').title()}\n   Status: {status}")
        if result.get("success"):
            print(f"   File: {result['file_path']}")
        else:
            print(f"   Errors: {result.get('errors', [])}")

    manifest_path = ROOT / "visualization" / "results" / "chart_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    failures = sum(not bool(item.get("success")) for item in manifest)
    print(f"\nManifest: {manifest_path}")
    print(f"Successful charts: {len(manifest) - failures}/{len(manifest)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())