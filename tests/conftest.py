import pandas as pd
import pytest

from flowlab.synthetic import generate


@pytest.fixture(scope="session")
def tiny_df() -> pd.DataFrame:
    return generate(n_normal=800, n_attack=120, seed=42)
