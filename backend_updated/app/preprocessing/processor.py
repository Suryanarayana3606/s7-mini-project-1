"""Customer review preprocessing pipeline.

Scaling note
------------
The original implementation called `nlp(text)` once per row in a plain
Python for-loop. spaCy's per-call overhead (tokenizer setup, pipeline
dispatch) dominates at that granularity — at 100k+ rows this took hours
and used a single CPU core. `nlp.pipe(...)` batches documents internally
and, with `n_process > 1`, fans work out across CPU cores. On a typical
4-8 core machine this is roughly a 4-10x wall-clock improvement, with no
change to the actual tokenization/lemmatization behavior — output is
identical, just computed faster and in less memory (bounded by
`batch_size`, not by loading every spaCy Doc into memory at once).
"""

import multiprocessing
import os
import platform

import pandas as pd

from app.preprocessing.cleaner import NEGATION_TOKENS, TextCleaner, get_nlp


def _default_n_process() -> int:
    """Use most available cores, but never more than 4 — spaCy's small
    English model doesn't scale much past that and higher counts just
    add process-spawn overhead. Also respect a manual override via env
    var for constrained environments (e.g. shared college lab machines).

    Multiprocessing (n_process > 1) spawns real OS processes, which this
    job triggers from a background *thread* (see app/jobs.py). That's
    fine on Linux/macOS (fork), but fragile on Windows, where
    multiprocessing needs a `spawn` start method and an
    `if __name__ == "__main__":` guard that a running uvicorn server
    doesn't provide — it can hang or error out. Default to single-process
    on Windows unless explicitly overridden; preprocess_dataframe also
    falls back automatically if multiprocessing fails for any reason.
    """
    override = os.getenv("PREPROCESS_N_PROCESS")
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            pass
    if platform.system() == "Windows":
        return 1
    try:
        cores = multiprocessing.cpu_count()
    except NotImplementedError:
        cores = 1
    return max(1, min(4, cores - 1 or 1))


class ReviewProcessor:
    @staticmethod
    def _preserve_negation(words):
        preserved = []
        index = 0
        while index < len(words):
            word = words[index]
            if word in NEGATION_TOKENS and index + 1 < len(words):
                preserved.append(f"{word}_{words[index + 1]}")
                index += 2
                continue
            preserved.append(word)
            index += 1
        return preserved

    def _clean_tokens(self, doc):
        words = []
        for token in doc:
            token_text = token.text.lower()
            if token.is_punct or token.is_space:
                continue
            if token.is_stop and token_text not in NEGATION_TOKENS:
                continue
            if len(token.text) <= 2 and token_text not in NEGATION_TOKENS:
                continue
            lemma = token.lemma_.strip()
            if lemma:
                words.append(lemma)
        return " ".join(self._preserve_negation(words))

    def preprocess_dataframe(
        self,
        df: pd.DataFrame,
        text_column="review",
        batch_size: int = 1000,
        n_process: int | None = None,
        progress_callback=None,
    ):
        df = df.copy()
        if text_column not in df.columns:
            raise ValueError(f"Required text column '{text_column}' not found.")

        nlp = get_nlp()
        cleaner = TextCleaner()

        # Regex-based cleaning (emoji/contraction/URL handling) is cheap
        # and doesn't benefit from spaCy's pipe, so it stays a plain
        # vectorized pass over the raw text first.
        cleaned_texts = df[text_column].fillna("").astype(str).map(cleaner.clean).tolist()

        total = len(cleaned_texts)
        n_process = n_process or _default_n_process()
        # Disabling unused pipeline components (parser/ner) speeds up
        # nlp.pipe further since only tokenization + lemmatization + stopword
        # flags are actually used downstream. Lemmatizer must stay enabled.
        disabled = [p for p in ("parser", "ner") if p in nlp.pipe_names]

        processed = [None] * total
        done = 0

        def _run(process_count):
            nonlocal done
            done = 0
            with nlp.select_pipes(disable=disabled):
                for i, doc in enumerate(
                    nlp.pipe(cleaned_texts, batch_size=batch_size, n_process=process_count)
                ):
                    processed[i] = self._clean_tokens(doc)
                    done += 1
                    if progress_callback and (done % batch_size == 0 or done == total):
                        progress_callback(done, total)

        try:
            _run(n_process)
        except Exception:
            # Multiprocessing can fail for environment-specific reasons
            # (sandboxed containers, restrictive Windows lab machines,
            # low file-descriptor limits). Falling back to a single
            # process is slower but always works — never let a scaling
            # optimization break the actual pipeline.
            if n_process > 1:
                _run(1)
            else:
                raise

        df["clean_review"] = processed
        return df
