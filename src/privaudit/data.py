"""Load the UCI Adult census extract and build the count tables a dashboard would publish."""
from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "adult"

COLUMNS = ["age", "workclass", "fnlwgt", "education", "education_num", "marital_status", "occupation",
           "relationship", "race", "sex", "capital_gain", "capital_loss", "hours_per_week", "native_country",
           "income"]

AGE_BANDS = ["17-24", "25-34", "35-44", "45-54", "55-64", "65+"]
HOURS_BANDS = ["<20", "20-34", "35-40", "41-50", "51-60", "60+"]
EDUCATION_ORDER = ["Preschool", "1st-4th", "5th-6th", "7th-8th", "9th", "10th", "11th", "12th", "HS-grad",
                   "Some-college", "Assoc-voc", "Assoc-acdm", "Bachelors", "Masters", "Prof-school", "Doctorate"]

# The attributes a public dashboard might break counts down by, with human-readable labels
ATTRIBUTES = {
    "age_band": "Age band",
    "sex": "Sex",
    "race": "Race",
    "marital_status": "Marital status",
    "relationship": "Relationship",
    "education": "Education",
    "workclass": "Work class",
    "occupation": "Occupation",
    "hours_band": "Hours per week",
    "native_country": "Country of birth",
    "income": "Income",
}


def load_people() -> pd.DataFrame:
    """All 48,842 records (train + test), cleaned. Missing values ('?') become 'Unknown'."""
    frames = []
    for name, skip in (("adult.data", 0), ("adult.test", 1)):
        df = pd.read_csv(RAW / name, header=None, names=COLUMNS, skiprows=skip, skipinitialspace=True)
        frames.append(df.dropna(subset=["income"]))
    df = pd.concat(frames, ignore_index=True)
    for col in df.select_dtypes(exclude="number").columns:   # text columns (object or pandas string dtype)
        df[col] = df[col].astype(str).str.strip().replace("?", "Unknown")
    df["income"] = df["income"].str.rstrip(".").map({"<=50K": "<=50K", ">50K": ">50K"})
    df["age_band"] = pd.cut(df["age"], [16, 24, 34, 44, 54, 64, 200], labels=AGE_BANDS).astype(str)
    df["hours_band"] = pd.cut(df["hours_per_week"], [0, 19, 34, 40, 50, 60, 200], labels=HOURS_BANDS).astype(str)
    return df


def categories(df: pd.DataFrame, attr: str) -> list[str]:
    if attr == "age_band":
        return AGE_BANDS
    if attr == "hours_band":
        return HOURS_BANDS
    if attr == "education":
        return EDUCATION_ORDER
    if attr == "income":
        return ["<=50K", ">50K"]
    # Most common first, so the largest groups lead the table and 'Unknown' sorts by its size
    return df[attr].value_counts().index.tolist()


def crosstab(df: pd.DataFrame, rows: str, cols: str) -> tuple[np.ndarray, list[str], list[str]]:
    r, c = categories(df, rows), categories(df, cols)
    table = pd.crosstab(df[rows], df[cols]).reindex(index=r, columns=c, fill_value=0)
    return table.to_numpy(dtype=np.int64), r, c


def all_pairs() -> list[tuple[str, str]]:
    """Every pair of attributes, each once: the set of two-way tables a dashboard could publish."""
    return list(combinations(ATTRIBUTES, 2))
