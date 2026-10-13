import pandas as pd
import pytest

from analytics.filters import apply_filters
from analytics.safe_pandas import UnsafeAnalyticsScript, run_pandas_script
from backend.schemas.ai import AnalyticsFilter


def test_apply_numeric_filter():
    df = pd.DataFrame({"score": [10, 80, 90], "status": ["a", "b", "c"]})
    filtered = apply_filters(df, [AnalyticsFilter(field="score", value="50", op="gte")])
    assert len(filtered) == 2


def test_custom_pandas_script_mean():
    df = pd.DataFrame({"score": [10, 20, 30]})
    out = run_pandas_script(
        df,
        'result = float(pd.to_numeric(df["score"]).mean())',
    )
    assert out["result"] == 20.0


def test_custom_pandas_rejects_import():
    with pytest.raises(UnsafeAnalyticsScript):
        run_pandas_script(pd.DataFrame({"a": [1]}), "import os\nresult = 1")
