"""Run the Phase 3 analytics engine against the configured MySQL database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.cleaning import copy_for_analysis
from analytics.comparisons import comparison_metrics
from analytics.database import connection_info
from analytics.grouping import grouped_analytics
from analytics.loader import dataframe_shape, load_placement_data
from analytics.metrics import basic_metrics
from analytics.placement import placement_metrics
from analytics.validation import validate_data


def main() -> int:
    try:
        dataframe = copy_for_analysis(load_placement_data())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    validation = validate_data(dataframe)
    results = {
        "connection": connection_info(),
        "dataset": dataframe_shape(dataframe),
        "validation": validation,
        "basic_metrics": basic_metrics(dataframe),
        "placement_metrics": placement_metrics(dataframe),
        "grouped_analytics": grouped_analytics(dataframe),
        "comparison_metrics": comparison_metrics(dataframe),
    }

    print("=== DATASET SUMMARY ===")
    print(f"Rows: {results['dataset']['row_count']}")
    print(f"Columns: {results['dataset']['column_count']}")
    print(f"Total Students: {results['basic_metrics']['total_students']}")
    print(f"Placed Students: {results['basic_metrics']['placed_students']}")
    print(f"Placement Rate: {results['basic_metrics']['placement_rate']:.2f}%")
    print("\n=== INTERNSHIP ANALYSIS ===")
    print(f"Internship Placement Rate: {results['placement_metrics']['internship_placement_rate']:.2f}%")
    print(f"Non-Internship Placement Rate: {results['placement_metrics']['non_internship_placement_rate']:.2f}%")
    print("\n=== ACADEMIC ANALYSIS ===")
    print(f"Average CGPA - Placed: {results['placement_metrics']['average_cgpa_placed']:.2f}")
    print(f"Average CGPA - Not Placed: {results['placement_metrics']['average_cgpa_not_placed']:.2f}")
    print("\n=== VALIDATION ===")
    print(f"Missing Values: {results['validation']['missing_values'] or 'None'}")
    print(f"Duplicate IDs: {results['validation']['duplicate_ids']}")
    print(f"Warnings: {results['validation']['warnings'] or 'None'}")

    output_path = ROOT / "analytics" / "results" / "placement_analytics.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nStructured results saved to: {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())