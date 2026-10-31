"""
utils/topic_formatter.py
"""

import pandas as pd


def format_topic_name(name: str) -> str:
    """
    Convert BERTopic names into readable aspect names.

    Example:
    --------
    0_battery_charge_power
        ↓
    Battery Charge Power
    """

    if pd.isna(name):
        return "Unknown"

    name = str(name)

    # Remove numeric prefix
    if "_" in name:
        name = "_".join(name.split("_")[1:])

    # Replace underscores
    name = name.replace("_", " ")

    # Title Case
    name = name.title()

    return name.strip()


def clean_topic_names(topic_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean all BERTopic topic names.
    """

    df = topic_df.copy()

    df["Aspect"] = df["Name"].apply(format_topic_name)

    return df