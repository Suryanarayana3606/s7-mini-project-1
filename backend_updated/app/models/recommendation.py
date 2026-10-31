"""
models/recommendation.py

Recommendation Model

Responsibilities
----------------
✔ Generate AI recommendations
✔ KPI Calculation
✔ Priority Distribution
✔ Department Distribution
✔ Top Priority Issues
✔ CSV Export
"""

import pandas as pd
from app.services.recommendation_service import RecommendationService

class RecommendationModel:

    def __init__(self):
        self.service = RecommendationService()

    # --------------------------------------------------
    # Generate Recommendations
    # --------------------------------------------------

    def generate(
        self,
        rootcause_df,
        progress_callback=None
    ):
        """
        Generate AI recommendations from root cause analysis.
        """

        recommendations, summary = self.service.generate(
            rootcause_df,
            progress_callback=progress_callback
        )

        recommendations = self.normalize(recommendations)

        return recommendations, summary

    # --------------------------------------------------
    # Normalize Output
    # --------------------------------------------------

    def normalize(self, df):

        if df.empty:
            return df

        # Standardize priority values
        if "priority" in df.columns:

            df["priority"] = (
                df["priority"]
                .astype(str)
                .str.strip()
                .str.title()
            )

        # Standardize department values
        if "department" in df.columns:

            df["department"] = (
                df["department"]
                .astype(str)
                .str.strip()
            )

        return df

    # --------------------------------------------------
    # KPI Cards
    # --------------------------------------------------

    def get_kpis(self, recommendations):

        if recommendations.empty:

            return {
                "Total": 0,
                "Critical": 0,
                "High": 0,
                "Medium": 0,
                "Low": 0
            }

        return {

            "Total": len(recommendations),

            "Critical": int(
                recommendations["priority"]
                .eq("Critical")
                .sum()
            ),

            "High": int(
                recommendations["priority"]
                .eq("High")
                .sum()
            ),

            "Medium": int(
                recommendations["priority"]
                .eq("Medium")
                .sum()
            ),

            "Low": int(
                recommendations["priority"]
                .eq("Low")
                .sum()
            )

        }

    # --------------------------------------------------
    # Priority Distribution
    # --------------------------------------------------

    def priority_distribution(self, recommendations):

        if recommendations.empty:
            return pd.DataFrame(
                columns=["Priority", "Count"]
            )

        return (
            recommendations["priority"]
            .value_counts()
            .rename_axis("Priority")
            .reset_index(name="Count")
        )

    # --------------------------------------------------
    # Department Distribution
    # --------------------------------------------------

    def department_distribution(self, recommendations):

        if recommendations.empty:
            return pd.DataFrame(
                columns=["Department", "Count"]
            )

        return (
            recommendations["department"]
            .value_counts()
            .rename_axis("Department")
            .reset_index(name="Count")
        )

    # --------------------------------------------------
    # Top Priority Issues
    # --------------------------------------------------

    def top_issues(self, recommendations, n=10):

        if recommendations.empty:
            return recommendations

        priority_order = {

            "Critical": 0,
            "High": 1,
            "Medium": 2,
            "Low": 3

        }

        df = recommendations.copy()

        df["Rank"] = df["priority"].map(priority_order)

        df = (
            df
            .sort_values(["Rank", "aspect"])
            .drop(columns="Rank")
        )

        return df.head(n)

    # --------------------------------------------------
    # Department KPIs
    # --------------------------------------------------

    def department_kpis(self, recommendations):

        if recommendations.empty:
            return {}

        return (
            recommendations["department"]
            .value_counts()
            .to_dict()
        )

    # --------------------------------------------------
    # Priority KPIs
    # --------------------------------------------------

    def priority_kpis(self, recommendations):

        if recommendations.empty:
            return {}

        return (
            recommendations["priority"]
            .value_counts()
            .to_dict()
        )

    # --------------------------------------------------
    # Export CSV
    # --------------------------------------------------

    def export_csv(self, recommendations):

        if recommendations.empty:
            return ""

        return recommendations.to_csv(index=False)