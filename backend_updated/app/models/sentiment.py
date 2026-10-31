"""
app/models/sentiment.py

Aspect-Based Sentiment Analyzer. Ported from the original
models/sentiment.py with one change: the original called st.progress()/
st.empty() directly inside analyze_dataframe(), which only works inside
a running Streamlit script. That's replaced here with an optional
progress_callback(current, total) parameter — the same pattern already
used by RootCauseAnalyzer.analyze() and RecommendationService.generate()
in this codebase, just extended to sentiment analysis for consistency.
The router turns that callback into job-progress updates that the React
frontend polls (see app/jobs.py).

The actual inference logic (batching, calling SentimentService) is
unchanged.
"""

from typing import Optional, Callable

import pandas as pd

from app.services.sentiment_service import SentimentService


class SentimentAnalyzer:

    def __init__(self):
        self.service = SentimentService()

    # ---------------------------------------------------
    # Analyze DataFrame
    # ---------------------------------------------------

    def analyze_dataframe(
        self,
        df: pd.DataFrame,
        text_column: str = "review",
        aspect_column: str = "Aspect",
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> pd.DataFrame:

        if df.empty:
            return df

        batch_size = batch_size or self.service.default_batch_size

        if text_column not in df.columns:
            raise ValueError(f"Column '{text_column}' not found.")

        if aspect_column not in df.columns:
            if "Topic" in df.columns:
                aspect_column = "Topic"
            else:
                raise ValueError("Aspect column not found. Run Aspect Discovery first.")

        working_df = df.copy()

        reviews = working_df[text_column].fillna("").astype(str).tolist()
        aspects = working_df[aspect_column].fillna("").astype(str).tolist()

        total = len(reviews)
        sentiments = []
        confidence_scores = []

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            review_batch = reviews[start:end]
            aspect_batch = aspects[start:end]

            predictions = self.service.predict_aspects_batch(review_batch, aspect_batch, batch_size=batch_size)

            for prediction in predictions:
                sentiments.append(prediction["label"])
                confidence_scores.append(prediction["confidence"])

            if progress_callback:
                progress_callback(end, total)

        working_df["Sentiment"] = sentiments
        working_df["Confidence"] = confidence_scores

        return working_df

    # ---------------------------------------------------
    # Sentiment Summary
    # ---------------------------------------------------

    def sentiment_summary(self, df: pd.DataFrame) -> dict:
        if "Sentiment" not in df.columns:
            return {}
        return {
            "positive": int((df["Sentiment"] == "positive").sum()),
            "neutral": int((df["Sentiment"] == "neutral").sum()),
            "negative": int((df["Sentiment"] == "negative").sum()),
        }

    # ---------------------------------------------------
    # Average Confidence
    # ---------------------------------------------------

    def average_confidence(self, df: pd.DataFrame) -> Optional[float]:
        if "Confidence" not in df.columns:
            return None
        if df.empty:
            return 0.0
        return round(float(df["Confidence"].mean()), 2)
