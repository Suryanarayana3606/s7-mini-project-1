"""
utils/data_validation.py

Dataset validation and cleaning utilities.

The upload module standardizes the customer's feedback column
to "review" before this validation is performed.
"""

import pandas as pd


NULL_REVIEW_VALUES = {
    "",
    "na",
    "n/a",
    "nan",
    "nil",
    "none",
    "null",
    "undefined",
}
QUOTE_CHARACTERS = "\"'`“”‘’"


def has_usable_review(value) -> bool:
    """Return False for missing, null-like, or quote-only review values."""
    if pd.isna(value):
        return False

    text = str(value).strip()
    unquoted = text.strip(QUOTE_CHARACTERS).strip()
    return bool(unquoted) and unquoted.casefold() not in NULL_REVIEW_VALUES


# -------------------------------------------------------
# Required Columns
# -------------------------------------------------------

REQUIRED_COLUMNS = [
    "review"
]


# -------------------------------------------------------
# Validate Dataset
# -------------------------------------------------------

def validate_dataset(df: pd.DataFrame):
    """
    Validate the uploaded customer feedback dataset.

    The review column must already be standardized to
    'review' by the Upload Dataset page.
    """

    errors = []

    # Empty dataset
    if df.empty:

        errors.append(
            "Dataset is empty."
        )

        return errors

    # Check required columns
    missing = [

        col

        for col in REQUIRED_COLUMNS

        if col not in df.columns

    ]

    if missing:

        errors.append(
            "Missing required columns: "
            + ", ".join(missing)
        )

        return errors

    # Check review column
    if "review" in df.columns:

        # Count empty reviews
        empty_reviews = (

            df["review"]
            .isna()
            .sum()

        )

        if empty_reviews == len(df):

            errors.append(
                "The review column does not contain "
                "any usable customer feedback."
            )

    return errors


# -------------------------------------------------------
# Clean Dataset
# -------------------------------------------------------

def clean_dataset(df: pd.DataFrame):
    """
    Clean the customer feedback dataset.

    Operations:
    - Remove duplicate rows
    - Fill missing values
    - Standardize review text
    """

    df = df.copy()

    # ---------------------------------------------------
    # Remove duplicates
    # ---------------------------------------------------

    before = len(df)

    df = df.drop_duplicates()

    duplicates_removed = (
        before - len(df)
    )

    # ---------------------------------------------------
    # Count missing values
    # ---------------------------------------------------

    missing_before = int(
        df.isna().sum().sum()
    )

    # ---------------------------------------------------
    # Fill missing values
    # ---------------------------------------------------

    df = df.fillna("")


    # ---------------------------------------------------
    # Clean Review Column
    # ---------------------------------------------------

    if "review" in df.columns:

        df["review"] = (

            df["review"]

            .astype(str)

            .str.strip()

        )

    return (
        df,
        duplicates_removed,
        missing_before
    )