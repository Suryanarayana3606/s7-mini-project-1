"""
services/rootcause_service.py

Fast Root Cause Analysis Service
---------------------------------
Uses:
✔ Negative Aspect Sentiment
✔ Original customer reviews
✔ TF-IDF
✔ Unigrams
✔ Bigrams
✔ Trigrams
✔ Frequency scoring
✔ Phrase ranking
✔ Word Cloud

No KeyBERT
No Transformers
"""

import re
from collections import Counter

import pandas as pd

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from wordcloud import WordCloud

from app.preprocessing.cleaner import CONTRACTION_REPLACEMENTS


class RootCauseService:

    def __init__(self):

        # Domain-specific words that are usually not
        # useful for identifying a root cause.
        self.stop_words = set(ENGLISH_STOP_WORDS) | {
            "the",
            "is",
            "are",
            "was",
            "were",
            "this",
            "that",
            "with",
            "have",
            "has",
            "had",
            "for",
            "and",
            "you",
            "your",
            "our",
            "their",
            "its",
            "it's",
            "it",
            "a",
            "an",
            "to",
            "of",
            "on",
            "in",
            "my",
            "me",
            "i",
            "very",
            "really",
            "product",
            "phone",
            "mobile",
            "app",
            "apps",
            "application",
            "applications",
            "game",
            "games",
        }


    # -------------------------------------------------
    # Clean Reviews
    # -------------------------------------------------

    def clean_reviews(self, reviews):

        cleaned = []

        for review in reviews:

            if pd.isna(review):
                continue

            review = self._normalize_review(review)

            if review:
                cleaned.append(review)

        return cleaned

    def _normalize_review(self, review):
        review = str(review).lower()

        for contraction, replacement in CONTRACTION_REPLACEMENTS.items():
            review = re.sub(
                rf"\b{re.escape(contraction)}\b",
                replacement,
                review,
            )

        # Remove URLs
        review = re.sub(
            r"http\S+|www\S+",
            " ",
            review
        )

        # Remove email addresses
        review = re.sub(
            r"\S+@\S+",
            " ",
            review
        )

        # Keep alphabetic words
        review = re.sub(
            r"[^a-zA-Z ]",
            " ",
            review
        )

        # Remove extra spaces
        return re.sub(
            r"\s+",
            " ",
            review
        ).strip()


    # -------------------------------------------------
    # TF-IDF Phrase Extraction
    # -------------------------------------------------

    def tfidf_phrases(
        self,
        reviews,
        top_n=15
    ):

        if not reviews:
            return []

        # Need at least one non-empty review
        if not any(
            review.strip()
            for review in reviews
        ):
            return []

        try:

            vectorizer = TfidfVectorizer(

                stop_words=sorted(self.stop_words),

                ngram_range=(1, 3),

                max_features=500

            )

            matrix = vectorizer.fit_transform(
                reviews
            )

        except ValueError:

            return []

        scores = matrix.sum(
            axis=0
        ).A1

        words = (
            vectorizer
            .get_feature_names_out()
        )

        ranking = sorted(

            zip(
                words,
                scores
            ),

            key=lambda x: x[1],

            reverse=True

        )

        return ranking[:top_n]


    # -------------------------------------------------
    # Frequency Score
    # -------------------------------------------------

    def frequency_score(
        self,
        reviews
    ):

        counter = Counter()

        for review in reviews:

            tokens = review.split()

            # Remove domain-specific common words
            tokens = [
                token
                for token in tokens
                if token not in self.stop_words
            ]

            counter.update(tokens)

        return counter


    # -------------------------------------------------
    # Phrase Frequency
    # -------------------------------------------------

    def phrase_frequency(
        self,
        phrase,
        reviews
    ):

        phrase = phrase.lower()

        count = 0

        for review in reviews:

            count += review.count(
                phrase
            )

        return count


    # -------------------------------------------------
    # Severity-Weighted Phrase Frequency
    # -------------------------------------------------
    #
    # A root cause mentioned only in reviews the ABSA sentiment model was
    # barely confident were negative (e.g. 52% confidence) is weaker
    # evidence than one mentioned in reviews it was 98% confident were
    # negative. Plain occurrence counting treats both identically. This
    # weights each occurrence by the review's sentiment confidence, so
    # root causes backed by high-confidence negative sentiment surface
    # above ones backed by borderline predictions.

    def weighted_phrase_frequency(
        self,
        phrase,
        reviews,
        confidences
    ):

        phrase = phrase.lower()

        weighted_hits = 0.0
        raw_hits = 0

        for review, confidence in zip(reviews, confidences):

            count = review.count(phrase)

            if count:

                raw_hits += count

                # Confidence is 0-100. Map it to a 0.5-1.5 multiplier so
                # a low-confidence hit still counts (doesn't zero it
                # out) but a high-confidence hit counts noticeably more.
                severity_multiplier = 0.5 + (
                    max(0.0, min(confidence, 100.0)) / 100.0
                )

                weighted_hits += count * severity_multiplier

        return weighted_hits, raw_hits


    # -------------------------------------------------
    # Score Keywords
    # -------------------------------------------------

    def score_keywords(
        self,
        tfidf_keywords,
        frequency,
        reviews,
        confidences=None
    ):

        ranked = []
        max_tfidf = max(
            (score for _phrase, score in tfidf_keywords),
            default=0,
        ) or 1

        use_severity = (
            confidences is not None
            and len(confidences) == len(reviews)
        )

        for phrase, tfidf_score in tfidf_keywords:

            tokens = phrase.split()

            # Frequency of individual words
            word_frequency = sum(

                frequency.get(
                    word,
                    0
                )

                for word in tokens

            )

            # Frequency of complete phrase — severity-weighted by
            # sentiment confidence when available, otherwise a plain count.
            if use_severity:

                weighted_hits, _raw_hits = self.weighted_phrase_frequency(
                    phrase,
                    reviews,
                    confidences
                )

                exact_frequency = weighted_hits

            else:

                exact_frequency = self.phrase_frequency(
                    phrase,
                    reviews
                )

            normalized_tfidf = tfidf_score / max_tfidf
            normalized_word_frequency = min(word_frequency / 20, 1.0)
            normalized_phrase_frequency = min(exact_frequency / 10, 1.0)

            final_score = (
                normalized_tfidf * 0.70
                + normalized_phrase_frequency * 0.20
                + normalized_word_frequency * 0.10
            )

            ranked.append(

                (
                    phrase,
                    final_score
                )

            )

        ranked.sort(

            key=lambda x: x[1],

            reverse=True

        )

        return ranked


    # -------------------------------------------------
    # Remove Duplicate / Overlapping Phrases
    # -------------------------------------------------

    def remove_duplicates(
        self,
        ranked
    ):

        seen = set()

        output = []

        for phrase, score in ranked:

            key = phrase.lower().strip()

            if not key:
                continue

            if key in seen:
                continue

            # Avoid phrases that are simply contained
            # inside a stronger phrase already selected.
            words = set(key.split())

            overlap = False

            for existing in seen:

                existing_words = set(
                    existing.split()
                )

                if (
                    len(words) <= len(existing_words)
                    and words.issubset(existing_words)
                    and len(words) > 1
                ):

                    overlap = True

                    break

            if overlap:
                continue

            seen.add(key)

            output.append(

                (
                    phrase.title(),
                    round(score, 2)
                )

            )

        return output


    # -------------------------------------------------
    # Clean Reviews While Keeping Confidence + Original
    # Text Aligned (needed for severity weighting and
    # for evidence snippets, since clean_reviews() alone
    # drops empty rows and loses that alignment)
    # -------------------------------------------------

    def _clean_reviews_with_meta(
        self,
        reviews,
        confidences
    ):

        cleaned = []
        cleaned_confidences = []
        originals = []

        for review, confidence in zip(reviews, confidences):

            if pd.isna(review):
                continue

            original = str(review).strip()

            text = self._normalize_review(original)

            if text:

                cleaned.append(text)

                cleaned_confidences.append(

                    float(confidence)
                    if confidence is not None and not pd.isna(confidence)
                    else 50.0

                )

                originals.append(original)

        return cleaned, cleaned_confidences, originals


    # -------------------------------------------------
    # Build Evidence (Explainability)
    # -------------------------------------------------
    #
    # For each surfaced root cause phrase, find the original (unmodified)
    # customer review that best demonstrates it — preferring the review
    # the sentiment model was most confident was negative. This is what
    # powers the "why was this recommendation made" panel: every root
    # cause, and therefore every downstream AI recommendation, can be
    # traced back to a real customer quote instead of being a black box.

    def _build_evidence(
        self,
        top_causes,
        cleaned_reviews,
        original_reviews,
        confidences,
        max_causes=5,
        max_len=220
    ):

        evidence = []
        used_indices = set()

        for phrase, _score in top_causes[:max_causes]:
            pattern = self._phrase_pattern(phrase)
            if pattern is None:
                continue
            matcher = re.compile(pattern, flags=re.IGNORECASE)

            best_idx = None
            best_confidence = -1.0

            for i, review in enumerate(cleaned_reviews):

                if (
                    i not in used_indices
                    and matcher.search(review)
                    and confidences[i] > best_confidence
                ):

                    best_confidence = confidences[i]
                    best_idx = i

            if best_idx is None:
                for i, review in enumerate(cleaned_reviews):
                    if matcher.search(review) and confidences[i] > best_confidence:
                        best_confidence = confidences[i]
                        best_idx = i

            if best_idx is None:
                continue

            used_indices.add(best_idx)

            snippet = self._evidence_snippet(
                original_reviews[best_idx], phrase, max_len
            )
            if not snippet:
                continue

            evidence.append({
                "phrase": phrase,
                "review": snippet,
                "confidence": (
                    round(best_confidence, 1)
                    if best_confidence >= 0
                    else None
                )
            })

        return evidence

    @staticmethod
    def _phrase_pattern(phrase):
        words = str(phrase).split()
        if not words:
            return None
        return r"\b" + r"[\s\W_]+".join(re.escape(word) for word in words) + r"\b"

    def _evidence_snippet(self, review, phrase, max_len):
        pattern = self._phrase_pattern(phrase)
        if pattern is None:
            return ""
        match = re.search(pattern, review, flags=re.IGNORECASE)
        if match is None:
            return ""

        sentence_start = max(
            review.rfind(".", 0, match.start()),
            review.rfind("!", 0, match.start()),
            review.rfind("?", 0, match.start()),
            review.rfind(",", 0, match.start()),
            review.rfind(";", 0, match.start()),
        ) + 1
        sentence_endings = [
            end for end in (
                review.find(".", match.end()),
                review.find("!", match.end()),
                review.find("?", match.end()),
                review.find(",", match.end()),
                review.find(";", match.end()),
            ) if end >= 0
        ]
        sentence_end = min(sentence_endings, default=len(review))
        snippet = review[sentence_start:sentence_end].strip()

        if len(snippet) <= max_len:
            return snippet

        window_start = max(0, match.start() - max_len // 3)
        window_end = min(len(review), window_start + max_len)
        snippet = review[window_start:window_end].strip()
        if window_start > 0:
            snippet = "…" + snippet
        if window_end < len(review):
            snippet = snippet.rstrip() + "…"
        return snippet


    # -------------------------------------------------
    # Analyze One Aspect
    # -------------------------------------------------

    def analyze_aspect(
        self,
        reviews,
        confidences=None
    ):

        if confidences is not None and len(confidences) == len(reviews):

            cleaned, cleaned_confidences, originals = (
                self._clean_reviews_with_meta(reviews, confidences)
            )

        else:

            cleaned = self.clean_reviews(reviews)
            cleaned_confidences = [50.0] * len(cleaned)
            originals = list(cleaned)

        if not cleaned:
            return [], []

        tfidf = self.tfidf_phrases(
            cleaned
        )

        if not tfidf:
            return [], []

        frequency = self.frequency_score(
            cleaned
        )

        ranked = self.score_keywords(

            tfidf,

            frequency,

            cleaned,

            cleaned_confidences

        )

        top = self.remove_duplicates(
            ranked
        )[:10]

        evidence = self._build_evidence(
            top,
            cleaned,
            originals,
            cleaned_confidences
        )

        return top, evidence


    # -------------------------------------------------
    # Analyze Complete Dataset
    # -------------------------------------------------

    def analyze_dataset(
        self,
        df,
        progress_callback=None
    ):

        results = []

        # ---------------------------------------------
        # Validate columns
        # ---------------------------------------------

        required_columns = [
            "Aspect",
            "Sentiment",
            "review"
        ]

        missing = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing:

            raise ValueError(
                f"Missing columns: {missing}"
            )


        # ---------------------------------------------
        # Normalize sentiment
        # ---------------------------------------------

        working_df = df.copy()

        working_df["Sentiment"] = (

            working_df["Sentiment"]

            .fillna("")

            .astype(str)

            .str.strip()

            .str.lower()

        )

        # Aspect-level sentiment confidence (from the ABSA model, added
        # during the Aspect Sentiment stage) drives severity weighting
        # below. Older datasets analyzed before this feature existed
        # won't have it — analyze_aspect() falls back to unweighted
        # scoring in that case, so this stays backward compatible.
        has_confidence = "Confidence" in working_df.columns


        # ---------------------------------------------
        # Get aspects
        # ---------------------------------------------

        aspects = sorted(

            working_df["Aspect"]

            .dropna()

            .astype(str)

            .unique()

        )


        total = len(aspects)


        # ---------------------------------------------
        # Process each aspect
        # ---------------------------------------------

        for idx, aspect in enumerate(
            aspects
        ):

            # Progress callback
            if progress_callback:

                progress_callback(

                    idx + 1,

                    total,

                    aspect

                )


            # -----------------------------------------
            # ONLY NEGATIVE ASPECT SENTIMENT
            # -----------------------------------------

            subset = working_df[

                (
                    working_df["Aspect"]
                    .astype(str)
                    == str(aspect)
                )

                &

                (
                    working_df["Sentiment"]
                    == "negative"
                )

            ]


            if subset.empty:

                continue


            # -----------------------------------------
            # ORIGINAL REVIEW TEXT
            # -----------------------------------------

            reviews = (

                subset["review"]

                .fillna("")

                .astype(str)

                .tolist()

            )

            confidences = (

                subset["Confidence"]

                .fillna(50.0)

                .astype(float)

                .tolist()

                if has_confidence

                else None

            )


            # -----------------------------------------
            # Extract Root Causes
            # -----------------------------------------

            keywords, evidence = self.analyze_aspect(
                reviews,
                confidences=confidences
            )


            if not keywords:

                continue


            avg_severity = (

                round(sum(confidences) / len(confidences), 1)

                if confidences

                else None

            )


            results.append(

                {

                    "Aspect": aspect,

                    "Negative Reviews": len(
                        subset
                    ),

                    "Root Causes": [
                        keyword[0]
                        for keyword in keywords
                    ],

                    "Evidence": evidence,

                    "Avg Severity": avg_severity

                }

            )


        return pd.DataFrame(
            results
        )


    # -------------------------------------------------
    # Word Cloud
    # -------------------------------------------------

    def create_wordcloud(
        self,
        reviews
    ):

        reviews = self.clean_reviews(
            reviews
        )

        text = " ".join(
            reviews
        )

        if not text.strip():

            return WordCloud(
                width=1200,
                height=600,
                background_color="white"
            ).generate(
                "No negative reviews"
            )


        return WordCloud(

            width=1200,

            height=600,

            background_color="white",

            stopwords=self.stop_words,

            collocations=True

        ).generate(
            text
        )