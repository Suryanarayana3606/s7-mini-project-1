"""
models/rootcause.py

Root Cause Analysis Model
-------------------------
Connects the Streamlit UI with RootCauseService.
"""

import pandas as pd

from app.services.rootcause_service import (
    RootCauseService
)


class RootCauseAnalyzer:

    def __init__(self):

        self.service = RootCauseService()


    # ---------------------------------------------------------
    # Main Analysis
    # ---------------------------------------------------------

    def analyze(
        self,
        df: pd.DataFrame,
        progress_callback=None
    ):

        if df.empty:

            return pd.DataFrame()


        required = [

            "Aspect",

            "Sentiment",

            "review"

        ]


        missing = [

            column

            for column in required

            if column not in df.columns

        ]


        if missing:

            raise ValueError(

                f"Missing Columns : {missing}"

            )


        return self.service.analyze_dataset(

            df,

            progress_callback=progress_callback

        )


    # ---------------------------------------------------------
    # Dashboard Summary
    # ---------------------------------------------------------

    def summary(
        self,
        rootcause_df
    ):

        if rootcause_df.empty:

            return {

                "total_aspects": 0,

                "negative_reviews": 0,

                "root_causes": 0,

                "top_aspect": "-"

            }


        total_aspects = len(
            rootcause_df
        )


        negative_reviews = int(

            rootcause_df[
                "Negative Reviews"
            ].sum()

        )


        root_causes = int(

            rootcause_df[
                "Root Causes"
            ]

            .apply(len)

            .sum()

        )


        top_aspect = (

            rootcause_df

            .sort_values(

                "Negative Reviews",

                ascending=False

            )

            .iloc[0]["Aspect"]

        )


        return {

            "total_aspects":
                total_aspects,

            "negative_reviews":
                negative_reviews,

            "root_causes":
                root_causes,

            "top_aspect":
                top_aspect

        }


    # ---------------------------------------------------------
    # Bar Chart
    # ---------------------------------------------------------

    def bar_chart_data(
        self,
        rootcause_df
    ):

        if rootcause_df.empty:

            return pd.DataFrame()


        return (

            rootcause_df

            .sort_values(

                "Negative Reviews",

                ascending=False

            )

        )


    # ---------------------------------------------------------
    # Treemap
    # ---------------------------------------------------------

    def treemap_data(
        self,
        rootcause_df
    ):

        rows = []


        if rootcause_df.empty:

            return pd.DataFrame()


        for _, row in rootcause_df.iterrows():

            aspect = row["Aspect"]

            count = row[
                "Negative Reviews"
            ]


            for cause in row[
                "Root Causes"
            ]:

                rows.append(

                    {

                        "Aspect": aspect,

                        "Cause": cause,

                        "Count": count

                    }

                )


        return pd.DataFrame(
            rows
        )


    # ---------------------------------------------------------
    # Top Root Causes
    # ---------------------------------------------------------

    def top_root_causes(
        self,
        rootcause_df,
        top_n=15
    ):

        from collections import Counter


        counter = Counter()


        if rootcause_df.empty:

            return pd.DataFrame()


        for causes in rootcause_df[
            "Root Causes"
        ]:

            if isinstance(
                causes,
                list
            ):

                counter.update(
                    causes
                )


        data = pd.DataFrame(

            counter.most_common(
                top_n
            ),

            columns=[

                "Root Cause",

                "Frequency"

            ]

        )


        return data


    # ---------------------------------------------------------
    # Evidence Lookup (Explainability)
    # ---------------------------------------------------------
    #
    # Maps Aspect -> Evidence (list of {phrase, review, confidence}
    # dicts) so the recommendation stage can attach source-review
    # traceability to each AI-generated recommendation.

    def evidence_by_aspect(
        self,
        rootcause_df
    ):

        if rootcause_df.empty or "Evidence" not in rootcause_df.columns:
            return {}

        return dict(
            zip(
                rootcause_df["Aspect"].astype(str),
                rootcause_df["Evidence"]
            )
        )


    # ---------------------------------------------------------
    # Negative Reviews
    # ---------------------------------------------------------

    def negative_reviews(
        self,
        df
    ):

        if df.empty:

            return []


        if "Sentiment" not in df.columns:

            return []


        if "review" not in df.columns:

            return []


        sentiment = (

            df["Sentiment"]

            .fillna("")

            .astype(str)

            .str.strip()

            .str.lower()

        )


        return (

            df.loc[
                sentiment == "negative",
                "review"
            ]

            .fillna("")

            .astype(str)

            .tolist()

        )


    # ---------------------------------------------------------
    # Export
    # ---------------------------------------------------------

    def export_csv(
        self,
        rootcause_df
    ):

        export_df = (
            rootcause_df.copy()
        )


        if "Root Causes" in export_df.columns:

            export_df["Root Causes"] = (

                export_df[
                    "Root Causes"
                ]

                .apply(

                    lambda x:
                    ", ".join(x)
                    if isinstance(x, list)
                    else str(x)

                )

            )


        return export_df.to_csv(

            index=False

        ).encode(
            "utf-8"
        )