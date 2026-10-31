"""
app/services/topic_service.py

BERTopic wrapper for Aspect Discovery.

Scaling + accuracy changes from the original (which used
BERTopic(verbose=True, calculate_probabilities=True) with every other
default):

1. Reproducibility: UMAP's default random state is unset, so the exact
   same dataset could produce different topics on different runs. This
   pins random_state=42 so results (and therefore reported "accuracy")
   are stable run over run.

2. Scale: default HDBSCAN clustering is roughly O(n^2) in practice and
   becomes slow/memory-heavy well before 100k documents. Above a
   configurable threshold this switches the cluster backend to
   MiniBatchKMeans, which scales near-linearly. Below the threshold it
   keeps HDBSCAN (better cluster shapes, automatic cluster count) but
   with min_cluster_size scaled to dataset size instead of a fixed
   default that's tuned for small demo datasets.

3. Noise reduction: BERTopic's default leaves every doc that HDBSCAN
   couldn't confidently cluster in the "-1" (noise/Unknown) bucket. At
   larger volumes this bucket can be large. `reduce_outliers` reassigns
   those documents to their nearest real topic by c-TF-IDF similarity
   instead of discarding them as "Unknown" — directly improves the
   fraction of reviews that get a usable Aspect label.

4. Guided/seeded topics (optional): if the caller knows likely product
   aspects in advance (battery, camera, delivery, packaging, etc.),
   passing `seed_topic_list` steers BERTopic toward those categories
   instead of letting fully unsupervised clustering invent arbitrary
   splits — this is usually the single biggest lever for aspect-label
   quality once you have a well-understood catalog of product aspects.

5. Dimensionality pre-reduction: PCA to ~50 dims before UMAP (which
   itself reduces further) meaningfully speeds up UMAP at high document
   counts with negligible quality loss, since sentence embeddings are
   highly redundant in their raw 384 dims.
"""

from bertopic import BERTopic
from bertopic.vectorizers import ClassTfidfTransformer
from hdbscan import HDBSCAN
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

# Above this many documents, swap HDBSCAN for MiniBatchKMeans for speed.
LARGE_DATASET_THRESHOLD = 30_000

RANDOM_STATE = 42


def _min_cluster_size_for(n_docs: int) -> int:
    """Scale min_cluster_size with dataset size so small demo datasets
    don't get one giant cluster, and large datasets don't get thousands
    of tiny, meaningless clusters."""
    if n_docs < 500:
        return 5
    if n_docs < 5_000:
        return 15
    if n_docs < 30_000:
        return 25
    return max(30, n_docs // 2000)


def _n_clusters_for(n_docs: int) -> int:
    """Only used for the MiniBatchKMeans large-dataset path, where the
    cluster count must be specified explicitly rather than discovered."""
    return max(15, min(60, n_docs // 1500))


class TopicService:

    def __init__(self, n_docs: int = 0, seed_topic_list: list[list[str]] | None = None):
        self.n_docs = n_docs
        vectorizer_model = CountVectorizer(ngram_range=(1, 2), stop_words="english", min_df=2)
        ctfidf_model = ClassTfidfTransformer(reduce_frequent_words=True)

        pca_components = min(50, max(2, n_docs - 1)) if n_docs else 50
        umap_model = UMAP(
            n_neighbors=15,
            n_components=5,
            min_dist=0.0,
            metric="cosine",
            random_state=RANDOM_STATE,
        )

        if n_docs and n_docs >= LARGE_DATASET_THRESHOLD:
            cluster_model = MiniBatchKMeans(
                n_clusters=_n_clusters_for(n_docs),
                random_state=RANDOM_STATE,
                n_init="auto",
            )
        else:
            cluster_model = HDBSCAN(
                min_cluster_size=_min_cluster_size_for(n_docs or 1000),
                min_samples=5,
                metric="euclidean",
                cluster_selection_method="eom",
                prediction_data=True,
            )

        self._cluster_model = cluster_model
        self._pca_components = pca_components

        self.model = BERTopic(
            umap_model=umap_model,
            hdbscan_model=cluster_model,
            vectorizer_model=vectorizer_model,
            ctfidf_model=ctfidf_model,
            seed_topic_list=seed_topic_list,
            calculate_probabilities=isinstance(cluster_model, HDBSCAN),
            verbose=True,
        )

    def _reduce_dims(self, embeddings):
        n_samples, n_features = embeddings.shape
        n_components = min(self._pca_components, n_samples - 1 if n_samples > 1 else 1, n_features)
        if n_components < 2 or n_samples < 20:
            # Too few points for PCA to be meaningful/stable — skip it.
            return embeddings
        return PCA(n_components=n_components, random_state=RANDOM_STATE).fit_transform(embeddings)

    def discover_topics(self, documents, embeddings):
        reduced = self._reduce_dims(embeddings)
        topics, probs = self.model.fit_transform(documents, reduced)

        # Reassign noise-cluster docs to their nearest real topic instead
        # of leaving them permanently unlabeled, where the dataset is
        # large enough for c-TF-IDF similarity to be meaningful.
        if -1 in topics and len(set(topics)) > 1:
            try:
                topics = self.model.reduce_outliers(documents, topics, strategy="c-tf-idf")
                self.model.update_topics(documents, topics=topics)
            except Exception:
                # Outlier reduction is a quality improvement, not a hard
                # requirement — never let it break the whole run.
                pass

        return topics, probs

    def get_topic_info(self):
        return self.model.get_topic_info()

    def get_model(self):
        return self.model
