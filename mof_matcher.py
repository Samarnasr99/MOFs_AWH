# mof_matcher.py

import requests
import pandas as pd
from io import BytesIO
from typing import Dict, Any, List

# Direct URL to your release asset (this is correct)
DATA_URL = "https://github.com/Samarnasr99/MOFs_AWH/releases/download/v1.0.0/MOFs_UI_Tool1.xlsm"

INPUT_COLS: List[str] = [
    "MOF", "N2", "CO2", "CH4", "Gas Temperature (°C)", "Gas Pressure (bar)",
    "Gas uptake (mmol/g)", "Void Fraction", "MSA (m²/g)", "VSA (m²/cm³)",
    "PLD (Å)", "LCD (Å)"
]

OUTPUT_COLS: List[str] = [
    "MOF", "KH (mmol/bar.g)", "W 0.1 (mmol/g)", "W 0.2 (mmol/g)", "W 0.3 (mmol/g)",
    "W 0.4 (mmol/g)", "W 0.5 (mmol/g)", "W 0.6 (mmol/g)", "W 0.7 (mmol/g)",
    "W 0.8 (mmol/g)", "W 0.9 (mmol/g)",
    "N2", "CO2", "CH4", "Gas Temperature (°C)", "Gas Pressure (bar)",
    "Gas uptake (mmol/g)", "Void Fraction", "MSA (m²/g)", "VSA (m²/cm³)",
    "PLD (Å)", "LCD (Å)"
]


def load_mof_data() -> pd.DataFrame:
    """
    Download the Excel file from GitHub release and load Sheet2 into a DataFrame.
    No local file is required, so no FileNotFoundError from the filesystem.
    """
    resp = requests.get(DATA_URL)
    resp.raise_for_status()

    excel_bytes = BytesIO(resp.content)
    df = pd.read_excel(excel_bytes, sheet_name="Sheet2", engine="openpyxl")
    df.columns = df.columns.str.strip()
    return df


def find_matching_mofs(df: pd.DataFrame, inputs: Dict[str, Any]) -> pd.DataFrame:
    """
    Filter and aggregate MOF rows based on user inputs.

    Behaviour mirrors your original Excel/xlwings script:
      - String input: exact match (case-insensitive, whitespace stripped).
      - Numeric input: match rows where column is within ±2% of the provided value.
      - Rows are grouped by 'MOF'. For MOFs with multiple matching rows, the row
        with highest 'Gas uptake (mmol/g)' provides operating conditions
        (N2, CO2, CH4, Temperature, Pressure, Gas uptake), and the remaining
        descriptor columns are averaged.
    """
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Normalise provided inputs (ignore blanks / None)
    provided: Dict[str, Any] = {}
    for k, v in inputs.items():
        if v is None:
            continue
        if isinstance(v, str):
            if not v.strip():
                continue
            provided[k.strip()] = v
        else:
            provided[k.strip()] = v

    if not provided:
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Ensure all referenced columns exist
    missing_cols = [k for k in provided.keys() if k not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing columns in dataset: {missing_cols}")

    mask = pd.Series(True, index=df.index)

    # Work on a copy for type conversions
    df_work = df.copy()

    for col, val in provided.items():
        if isinstance(val, str):
            df_work[col] = df_work[col].astype(str).str.strip().str.lower()
            mask &= df_work[col] == val.strip().lower()
        else:
            df_work[col] = pd.to_numeric(df_work[col], errors="coerce")
            lower = val * 0.98
            upper = val * 1.02
            mask &= df_work[col].between(lower, upper)

    matched = df_work[mask]

    if matched.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    grouped_rows = []

    for mof_name, group in matched.groupby("MOF"):
        group = group.copy()
        if "Gas uptake (mmol/g)" in group.columns:
            group["Gas uptake (mmol/g)"] = pd.to_numeric(
                group["Gas uptake (mmol/g)"], errors="coerce"
            )

        if len(group) > 1:
            # Identify row with highest Gas uptake
            idx_max = group["Gas uptake (mmol/g)"].idxmax()

            keep_cols = [
                "N2", "CO2", "CH4",
                "Gas Temperature (°C)", "Gas Pressure (bar)",
                "Gas uptake (mmol/g)"
            ]
            top_row = group.loc[idx_max, keep_cols]

            # Columns to average: all OUTPUT_COLS except keep_cols and MOF
            avg_cols = [c for c in OUTPUT_COLS if c not in keep_cols + ["MOF"]]
            avg_cols_existing = [c for c in avg_cols if c in group.columns]

            avg_row = group[avg_cols_existing].mean(numeric_only=True)

            # Preserve MOF name
            avg_row["MOF"] = mof_name

            # Override with top-row operating conditions
            for c in keep_cols:
                if c in top_row.index:
                    avg_row[c] = top_row[c]

            # Align to OUTPUT_COLS
            avg_row = avg_row.reindex(OUTPUT_COLS)
            grouped_rows.append(avg_row)
        else:
            # Single match: take it as-is, mapped into OUTPUT_COLS
            row = group.iloc[0]
            row_dict = {c: (row[c] if c in group.columns else None)
                        for c in OUTPUT_COLS}
            grouped_rows.append(row_dict)

    result_df = pd.DataFrame(grouped_rows, columns=OUTPUT_COLS)
    return result_df
