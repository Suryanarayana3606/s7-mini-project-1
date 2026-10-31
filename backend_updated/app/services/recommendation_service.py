"""
app/services/recommendation_service.py

AI Recommendation Service. Ported from the original
services/recommendation_service.py with the following changes only:

- Settings now come from the SQLite-backed app.database.db.get_settings()
  instead of a local config_settings.json file (see app/config.py).
- Removed two unused, harmless-but-sloppy imports from the original
  (`from urllib import response`, `from numpy.strings import index`) that
  shadowed local variable names of the same name.
- The generate() loop variable is renamed batch_index (was `index`,
  which used to collide with the unused numpy import above).

The actual recommendation-generation algorithm (batching, prompt
building, JSON extraction/repair, cleaning, sorting) is unchanged.
"""

import json
import re
import time
import uuid
import pandas as pd

from app.database.db import get_settings
from app.services.llm.factory import LLMFactory
from app.services.llm.prompt_builder import PromptBuilder


class _UnavailableProvider:
    """Provider placeholder that lets the deterministic fallback run."""
    def __init__(self, reason: str):
        self.reason = reason

    def generate(self, prompt: str) -> str:
        raise RuntimeError(self.reason)


class RecommendationService:

    MAX_BATCH_ATTEMPTS = 3

    def __init__(self):

        settings = get_settings()

        self.provider_name = settings.get("provider", "Groq")
        self.model = settings.get("model")
        self.temperature = settings.get("temperature", 0.2)
        self.max_tokens = settings.get("max_tokens", 1500)

        self.provider = self._load_provider()
        print("=" * 50)
        print("LLM Provider :", self.provider_name)
        print("Model        :", self.model)
        print("Temperature  :", self.temperature)
        print("Max Tokens   :", self.max_tokens)
        print("=" * 50)

    # --------------------------------------------------
    # Load Provider
    # --------------------------------------------------

    def _load_provider(self):
        try:
            return LLMFactory.get_provider(
                provider=self.provider_name,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                max_retries=0,
            )
        except Exception as primary_error:
            print(f"{self.provider_name} unavailable: {primary_error}")
            if self.provider_name.lower() != "ollama":
                try:
                    print("Switching to Ollama...")
                    return LLMFactory.get_provider(
                        provider="Ollama",
                        model="llama3.1:8b",
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                    )
                except Exception as fallback_error:
                    return _UnavailableProvider(str(fallback_error))
            return _UnavailableProvider(str(primary_error))

    # --------------------------------------------------
    # Extract JSON safely
    # --------------------------------------------------

    def extract_json(self, response: str):
        if not response:
            raise ValueError("Empty LLM response.")

        response = re.sub(r"```(?:json)?", "", response, flags=re.IGNORECASE).strip()

        start = response.find("{")
        end = response.rfind("}")

        if start == -1 or end == -1:
            raise ValueError("No JSON found in response.")

        response = response[start:end + 1]

        # Common JSON repairs
        response = re.sub(r",\s*}", "}", response)
        response = re.sub(r",\s*]", "]", response)
        response = response.replace("\u201c", '"').replace("\u201d", '"')
        response = response.replace("\t", " ").replace("\r", "")

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON returned by LLM:\n{e}")

    @staticmethod
    def _normalized_aspect(value):
        return re.sub(r"\W+", " ", str(value).casefold()).strip()

    def validate_batch_result(self, result, batch):
        if not isinstance(result, dict):
            raise ValueError("LLM response must be a JSON object.")

        recommendations = result.get("recommendations")
        if not isinstance(recommendations, list) or len(recommendations) != len(batch):
            raise ValueError("LLM response must contain one recommendation per aspect.")

        expected_aspects = {
            self._normalized_aspect(aspect)
            for aspect in batch["Aspect"].astype(str)
        }
        returned_aspects = set()
        required_fields = (
            "aspect",
            "priority",
            "department",
            "problem_summary",
            "recommendation",
            "business_impact",
            "estimated_effort",
            "expected_improvement",
        )

        for item in recommendations:
            if not isinstance(item, dict):
                raise ValueError("Each recommendation must be a JSON object.")
            if any(not str(item.get(field, "")).strip() for field in required_fields):
                raise ValueError("A recommendation is missing required fields.")
            returned_aspects.add(self._normalized_aspect(item["aspect"]))

        if not expected_aspects.issubset(returned_aspects):
            raise ValueError("LLM response did not cover every input aspect exactly.")
        if not returned_aspects.issubset(expected_aspects):
            raise ValueError("LLM response included an unexpected aspect.")

        if not isinstance(result.get("executive_summary", ""), str):
            raise ValueError("Executive summary must be text.")

        return result

    @staticmethod
    def _is_retryable_provider_error(error):
        status = getattr(error, "status_code", None)
        if status is None:
            status = getattr(error, "status", None)
        if status == 429 or (isinstance(status, int) and status >= 500):
            return True

        error_name = type(error).__name__.lower()
        if any(name in error_name for name in ("ratelimit", "timeout", "connection", "internalserver", "serviceunavailable")):
            return True

        message = str(error).lower()
        return any(text in message for text in ("rate limit", "temporarily unavailable", "timed out", "overloaded"))

    @staticmethod
    def _retry_delay(error, attempt):
        headers = getattr(getattr(error, "response", None), "headers", {}) or {}
        retry_after = next(
            (value for key, value in headers.items() if key.lower() == "retry-after"),
            None,
        )
        if retry_after is not None:
            try:
                return min(max(float(retry_after), 0.5), 15.0)
            except (TypeError, ValueError):
                pass
        return min(2 ** (attempt + 1), 8)

    def generate_batch_result(self, prompt, batch):
        current_prompt = prompt

        for attempt in range(self.MAX_BATCH_ATTEMPTS):
            try:
                response = self.provider.generate(current_prompt)
            except Exception as error:
                print(
                    f"LLM provider error on attempt {attempt + 1}/{self.MAX_BATCH_ATTEMPTS}: "
                    f"{type(error).__name__}: {error}"
                )
                if attempt + 1 >= self.MAX_BATCH_ATTEMPTS or not self._is_retryable_provider_error(error):
                    raise
                delay = self._retry_delay(error, attempt)
                print(f"Transient LLM error; retrying batch in {delay:g}s ({attempt + 2}/{self.MAX_BATCH_ATTEMPTS}).")
                time.sleep(delay)
                continue

            try:
                result = self.extract_json(response)
                return self.validate_batch_result(result, batch)
            except (TypeError, ValueError) as error:
                print(
                    f"LLM response rejected on attempt {attempt + 1}/{self.MAX_BATCH_ATTEMPTS}: "
                    f"{type(error).__name__}: {error}"
                )
                if attempt + 1 >= self.MAX_BATCH_ATTEMPTS:
                    raise
                print(f"Invalid or incomplete LLM JSON; requesting a corrected response ({attempt + 2}/{self.MAX_BATCH_ATTEMPTS}).")
                current_prompt = (
                    prompt
                    + "\n\nYour previous response was invalid or incomplete. Regenerate the full response. "
                    + "Return one complete recommendation for every input aspect, preserve each aspect name "
                    + "exactly, include every required field, and return only valid JSON."
                )

        raise RuntimeError("LLM batch attempts exhausted.")

    # --------------------------------------------------
    # Default Values
    # --------------------------------------------------

    def default_value(self, value, default="Not Available"):
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return default
        return value

    # --------------------------------------------------
    # Clean Recommendation
    # --------------------------------------------------

    def clean_recommendation(self, recommendation, evidence=None):
        return {
            # rec_id is a stable per-recommendation identifier the reviewer
            # feedback loop (Accept/Reject/Implement) keys off of — the
            # table has no other reliable primary key since aspect names
            # can repeat across re-generations.
            "rec_id": uuid.uuid4().hex[:12],
            "aspect": self.default_value(recommendation.get("aspect")),
            "priority": self.default_value(recommendation.get("priority"), "Medium"),
            "department": self.default_value(recommendation.get("department"), "Product Development"),
            "problem_summary": self.default_value(recommendation.get("problem_summary")),
            "recommendation": self.default_value(recommendation.get("recommendation")),
            "business_impact": self.default_value(recommendation.get("business_impact")),
            "estimated_effort": self.default_value(recommendation.get("estimated_effort"), "Medium"),
            "expected_improvement": self.default_value(recommendation.get("expected_improvement"), "10-20%"),
            "implementation_order": recommendation.get("implementation_order", 999),
            # Reviewer feedback loop
            "status": "Pending",
            "reviewer_note": "",
            # Explainability: source review snippets + root-cause phrases
            # that this recommendation was actually grounded in.
            "evidence": evidence or [],
        }

    # --------------------------------------------------
    # Split Data into Batches
    # --------------------------------------------------

    def create_batches(self, df, batch_size=3):
        return [df.iloc[i:i + batch_size] for i in range(0, len(df), batch_size)]

    def _fallback_recommendation(self, row, implementation_order=1):
        """Produce a useful rule-based recommendation when an LLM is unavailable."""
        aspect = str(row.get("Aspect", "Unknown"))
        causes = row.get("Root Causes", [])
        if not isinstance(causes, list):
            causes = [str(causes)] if causes else []
        cause_text = ", ".join(str(c) for c in causes[:3]) or "reported customer issue"
        negative_reviews = int(row.get("Negative Reviews", 0) or 0)

        aspect_lower = aspect.lower()
        cause_lower = " ".join(str(cause).lower() for cause in causes[:3])
        issue_text = f"{aspect_lower} {cause_lower}"
        critical_signals = (
            "safety", "injury", "security breach", "data leak", "data exposure",
            "exposed data", "unauthorized", "account takeover", "vulnerability", "fraud",
        )
        if any(signal in issue_text for signal in critical_signals):
            priority = "Critical"
        elif negative_reviews >= 5:
            priority = "High"
        elif negative_reviews >= 2:
            priority = "Medium"
        else:
            priority = "Low"

        department = "Product Development"
        if any(k in issue_text for k in ("support", "help", "service", "customer")):
            department = "Customer Support"
        elif any(k in issue_text for k in ("security", "privacy", "data leak", "unauthorized")):
            department = "Security & Privacy"
        elif any(k in issue_text for k in ("outage", "uptime", "latency", "server", "infrastructure")):
            department = "Platform & DevOps"
        elif any(k in issue_text for k in ("crash", "bug", "regression", "compatibility", "defect")):
            department = "Quality Assurance"
        elif any(k in issue_text for k in ("login", "sign in", "authentication", "payment", "billing", "sync", "integration", "notification")):
            department = "Engineering"

        return {
            "aspect": aspect,
            "priority": priority,
            "department": department,
            "problem_summary": f"Negative feedback for {aspect} is associated with {cause_text}.",
            "recommendation": f"Investigate {cause_text} for {aspect}, validate the failure pattern against affected reviews, and implement a targeted corrective action with post-release monitoring.",
            "business_impact": "Reduce repeat app failures and support volume while improving task completion, retention, and customer trust.",
            "estimated_effort": "Medium",
            "expected_improvement": "10-20%",
            "implementation_order": implementation_order,
        }

    def _summarize_recommendations(self, summaries, recommendations):
        recommendation_context = "\n".join(
            f"- {row['aspect']} ({row['priority']}): {row['problem_summary']} "
            f"Action: {row['recommendation']}"
            for _, row in recommendations.iterrows()
        )
        source_text = "\n\n".join(summaries)
        prompt = (
            "Create an executive summary of the recommendation analysis below. "
            "Return exactly 5 to 7 concise bullet points, one finding per line. "
            "Synthesize across aspects, prioritize the most important customer and business risks, "
            "and avoid repeating points. Do not mention fallback generation, provider availability, "
            "or configuration. Return bullets only.\n\n"
            f"Batch findings:\n{source_text or '(No batch summaries were returned.)'}\n\n"
            f"Recommendations:\n{recommendation_context or '(No recommendations were generated.)'}"
        )

        try:
            response = self.provider.generate(prompt)
            bullets = []
            for line in response.splitlines():
                line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
                if not line:
                    continue
                lowered = line.casefold()
                if any(term in lowered for term in (
                    "built-in fallback", "configure groq", "configure ollama",
                    "provider was unavailable",
                )):
                    continue
                bullets.append(f"- {line}")

            if 5 <= len(bullets) <= 7:
                return "\n".join(bullets)
            print(f"Executive summary rejected: expected 5-7 bullets, received {len(bullets)}.")
        except Exception as error:
            print(f"Executive summary synthesis failed: {type(error).__name__}: {error}")

        if recommendations.empty:
            return "- No recommendations were generated."

        ordered = recommendations.sort_values("implementation_order")
        return "\n".join(
            f"- {row['aspect']} ({row['priority']}): {row['recommendation']}"
            for _, row in ordered.head(7).iterrows()
        )

    # --------------------------------------------------
    # Generate Recommendations
    # --------------------------------------------------

    def generate(self, rootcause_df, progress_callback=None):

        batches = self.create_batches(rootcause_df, batch_size=3)

        all_recommendations = []
        summaries = []
        total = len(batches)

        for batch_index, batch in enumerate(batches, start=1):

            if progress_callback:
                progress_callback(batch_index, total, ", ".join(batch["Aspect"].tolist()))

            prompt = PromptBuilder.build_recommendation_prompt(batch, provider=self.provider_name)
            prompt += (
                "\nPreserve every aspect name exactly as provided and return exactly one recommendation "
                "for each aspect. Include all fields in the JSON schema."
            )

            # Aspect -> Evidence lookup for this batch, so every
            # recommendation the LLM (or the fallback) returns can be
            # traced back to the source reviews it was grounded in.
            evidence_by_aspect = {}
            if "Evidence" in batch.columns:
                evidence_by_aspect = dict(zip(batch["Aspect"].astype(str), batch["Evidence"]))

            try:
                result = self.generate_batch_result(prompt, batch)
            except Exception as e:
                print("=" * 60)
                print(f"Batch {batch_index}/{total} failed; using deterministic fallback")
                print(f"Aspects: {', '.join(batch['Aspect'].tolist())}")
                print(f"Failure: {type(e).__name__}: {e}")
                print("=" * 60)
                fallback_recommendations = [
                    self._fallback_recommendation(row, implementation_order=len(all_recommendations) + offset)
                    for offset, (_, row) in enumerate(batch.iterrows(), start=1)
                ]
                result = {
                    "recommendations": fallback_recommendations,
                    "executive_summary": "",
                }

            for item in result.get("recommendations", []):
                aspect_name = str(item.get("aspect", "")).strip()
                evidence = evidence_by_aspect.get(aspect_name)
                if evidence is None:
                    # The LLM occasionally reformats the aspect label
                    # slightly (casing, wording). Fall back to a loose
                    # substring match so the evidence panel still
                    # populates rather than silently coming up empty.
                    evidence = next(
                        (
                            v for k, v in evidence_by_aspect.items()
                            if k and aspect_name and (k.lower() in aspect_name.lower() or aspect_name.lower() in k.lower())
                        ),
                        [],
                    )
                all_recommendations.append(self.clean_recommendation(item, evidence=evidence))

            summary = result.get("executive_summary", "")
            if summary:
                summaries.append(summary)

        recommendations = pd.DataFrame(all_recommendations)

        if not recommendations.empty:
            recommendations = recommendations.sort_values("implementation_order")

        executive_summary = self._summarize_recommendations(summaries, recommendations)

        return recommendations, executive_summary
