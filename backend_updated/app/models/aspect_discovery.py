import json

from app.database.db import get_settings
from app.services.aspect_label_service import AspectLabelService
from app.services.embedding_service import EmbeddingService
from app.services.topic_service import TopicService
from app.utils.topic_formatter import format_topic_name


def _load_seed_topics() -> list[list[str]] | None:
    """Optional guided-topic-modeling hint. If the operator has configured
    known product aspects (e.g. via a `seed_topics` app_settings entry —
    a JSON list of keyword lists), BERTopic is steered toward those
    categories instead of relying purely on unsupervised clustering.
    Safe to leave unset; falls back to fully unsupervised discovery."""
    raw = get_settings().get("seed_topics")
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, list) and all(isinstance(g, list) for g in parsed):
            return parsed
    except (ValueError, TypeError):
        pass
    return None


class AspectDiscovery:

    def __init__(self):

        self.embedding = EmbeddingService()
        self.topic = None  # constructed in run() once dataset size is known

    def run(self, df, review_column="clean_review"):

        reviews = df[review_column].fillna("").astype(str).str.strip()
        if "review" in df.columns:
            fallback = df["review"].fillna("").astype(str).str.strip()
            reviews = reviews.mask(reviews.eq(""), fallback)
        reviews = reviews.tolist()

        embeddings = self.embedding.generate_embeddings(
            reviews
        )

        # Cluster model choice (HDBSCAN vs MiniBatchKMeans) and its
        # hyperparameters depend on dataset size, so TopicService is
        # constructed here rather than in __init__.
        self.topic = TopicService(n_docs=len(reviews), seed_topic_list=_load_seed_topics())

        topics, probabilities = self.topic.discover_topics(
            reviews,
            embeddings
        )

        topic_info = self.topic.get_topic_info()

        model = self.topic.get_model()

        # -----------------------------
        # Topic -> Name mapping
        # -----------------------------

        topic_map = {}
        raw_topic_map = {}
        label_inputs = []
        for _, row in topic_info.iterrows():
            topic_id = int(row["Topic"])
            raw_aspect = format_topic_name(row["Name"])
            raw_topic_map[topic_id] = raw_aspect
            topic_map[topic_id] = raw_aspect

            if topic_id != -1:
                keywords = self.topic.get_model().get_topic(topic_id) or []
                label_inputs.append({
                    "topic": topic_id,
                    "raw_aspect": raw_aspect,
                    "keywords": [str(word) for word, _weight in keywords[:10]],
                })

        if label_inputs:
            try:
                topic_map.update(AspectLabelService().relabel_topics(label_inputs))
            except Exception as exc:
                print(f"Aspect relabeling unavailable; retaining BERTopic labels ({type(exc).__name__}).")

        topic_info = topic_info.copy()
        topic_info["Raw Aspect"] = topic_info["Topic"].map(raw_topic_map)
        topic_info["Aspect"] = topic_info["Topic"].map(topic_map)

        # -----------------------------
        # Master Dataset
        # -----------------------------

        result_df = df.copy()

        result_df["Topic"] = topics
        result_df["Raw Aspect"] = [
            raw_topic_map.get(t, "Unknown")
            for t in topics
        ]

        result_df["Aspect"] = [
            topic_map.get(t, "Unknown")
            for t in topics
        ]


        return {

            "master_df": result_df,

            "topic_info": topic_info,

            "topics": topics,


            "model": model
        }