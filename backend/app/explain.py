
# Configo - Gemini AI Explanation Service

from __future__ import annotations

import json
import os
import time

import httpx
from sqlalchemy.orm import Session

from app.drift import detect_drift
from app.models import Server


# --------------------------------------------------
# GEMINI API CONFIGURATION
# --------------------------------------------------

GEMINI_API_BASE = (
    "https://generativelanguage.googleapis.com/v1beta"
)

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

MAX_RETRIES = 3

RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


def api_key() -> str:
    """Read Gemini API key from environment variables."""

    return (
        os.getenv("AI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or ""
    ).strip()


def gemini_model() -> str:
    """Get and normalize Gemini model name."""

    model = os.getenv(
        "GEMINI_MODEL",
        DEFAULT_GEMINI_MODEL
    ).strip()

    if model.startswith("models/"):
        model = model[len("models/"):]

    return model


# --------------------------------------------------
# FALLBACK EXPLANATION
# --------------------------------------------------

def fallback_explanation(
    outlier: dict | None,
    reason: str
) -> dict:
    """Return a backup explanation if Gemini is unavailable."""

    if outlier is None:

        what = (
            "This server matches the majority configuration "
            "and has no detected deviation from the approved baseline."
        )

        why = (
            "No configuration drift was detected for this server. "
            "Continue monitoring to identify future security "
            "or reliability risks."
        )

        next_step = (
            "No immediate correction is required. "
            "Continue regular configuration monitoring."
        )

    else:

        peer_differences = outlier.get(
            "differing_categories", []
        )

        baseline_differences = outlier.get(
            "baseline_differences", []
        )

        majority_names = [
            item["category"]
            for item in peer_differences
        ]

        baseline_names = [
            item["category"]
            for item in baseline_differences
        ]

        what_parts = []

        if majority_names:
            what_parts.append(
                "The server differs from the majority in: "
                + ", ".join(majority_names)
            )

        if baseline_names:
            what_parts.append(
                "It also deviates from the approved baseline in: "
                + ", ".join(baseline_names)
            )

        if not what_parts:
            what_parts.append(
                "No configuration differences were detected."
            )

        what = ". ".join(what_parts) + "."

        why = (
            "Differences in packages, network ports, environment "
            "variables, or SSH settings may create security "
            "and reliability risks. The majority configuration "
            "is a peer reference and is not automatically "
            "considered approved."
        )

        next_step = (
            "Compare the server configuration with both the "
            "majority configuration and the original approved "
            "baseline. Verify whether each deviation is authorized. "
            "Correct unapproved deviations and document approved "
            "exceptions."
        )

    return {
        "what_changed": what,
        "why_it_matters": why,
        "what_to_do_next": next_step,
        "source": "fallback",
        "fallback_reason": reason,
    }


# --------------------------------------------------
# GEMINI PROMPT
# --------------------------------------------------

def build_prompt(
    outlier: dict,
    majority: dict,
    majority_vs_baseline: dict | None = None
) -> str:
    """Prepare majority and baseline comparison for Gemini."""

    payload = {
        "server": outlier.get("name"),
        "server_id": outlier.get("server_id"),

        "majority_servers": majority.get("servers"),

        "majority_configuration": majority.get("config"),

        "server_vs_majority": outlier.get(
            "differing_categories", []
        ),

        "server_vs_approved_baseline": {
            "status": outlier.get(
                "baseline_status",
                "not_configured"
            ),
            "differences": outlier.get(
                "baseline_differences", []
            ),
        },

        "majority_vs_approved_baseline": (
            majority_vs_baseline or {}
        ),
    }

    return (
        "You are Configo, an AI assistant explaining server "
        "configuration drift to a junior system administrator.\n\n"

        "IMPORTANT RULES:\n"
        "1. The original approved baseline is the source of truth.\n"
        "2. The majority configuration is only a peer comparison.\n"
        "3. Never assume that the majority configuration is correct.\n"
        "4. Clearly identify when the majority itself deviates "
        "from the approved baseline.\n"
        "5. Do not invent configuration values or security incidents.\n"
        "6. Do not recommend blindly copying the majority "
        "configuration.\n"
        "7. Recommend checking whether deviations are authorized "
        "before correcting them.\n\n"

        "Explain the following information using ONLY the JSON data.\n\n"

        "Return a valid JSON object containing exactly these keys:\n"
        "what_changed, why_it_matters, what_to_do_next\n\n"

        "WHAT_CHANGED:\n"
        "Explain differences between this server and the majority, "
        "and differences between this server and the approved baseline. "
        "Mention majority baseline deviations when present.\n\n"

        "WHY_IT_MATTERS:\n"
        "Explain relevant security, reliability, and configuration "
        "consistency risks. Do not exaggerate risks.\n\n"

        "WHAT_TO_DO_NEXT:\n"
        "Give practical recommendations. First verify whether "
        "deviations are approved. Recommend correction only for "
        "unapproved deviations. Preserve authorized exceptions.\n\n"

        "Keep each answer to 2-4 sentences in simple language.\n\n"

        f"{json.dumps(payload, indent=2, default=str)}"
    )


# --------------------------------------------------
# PARSE GEMINI RESPONSE
# --------------------------------------------------

def parse_llm_content(content: str) -> dict | None:
    """Parse Gemini's JSON response."""

    text = (content or "").strip()

    if text.startswith("```"):

        lines = [
            line
            for line in text.splitlines()
            if not line.startswith("```")
        ]

        text = "\n".join(lines)

    try:
        data = json.loads(text)

    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    keys = (
        "what_changed",
        "why_it_matters",
        "what_to_do_next",
    )

    if not all(
        isinstance(data.get(key), str)
        and data[key].strip()
        for key in keys
    ):
        return None

    return {
        key: data[key].strip()
        for key in keys
    }


# --------------------------------------------------
# CALL GEMINI API
# --------------------------------------------------

def call_llm(
    outlier: dict,
    majority: dict,
    majority_vs_baseline: dict | None = None
) -> dict:
    """Call Gemini API with automatic retries."""

    key = api_key()

    if not key:
        return fallback_explanation(
            outlier,
            "missing_api_key"
        )

    model = gemini_model()

    url = (
        f"{GEMINI_API_BASE}/models/"
        f"{model}:generateContent"
    )

    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": build_prompt(
                            outlier,
                            majority,
                            majority_vs_baseline
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    headers = {
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    }

    response = None

    print(
        f"[explain] Calling Gemini model: {model}"
    )

    # Retry temporary API and network errors.
    for attempt in range(MAX_RETRIES):

        try:

            response = httpx.post(
                url,
                headers=headers,
                json=body,
                timeout=90.0,
            )

            if response.status_code in RETRYABLE_STATUS_CODES:

                print(
                    f"[explain] Temporary Gemini error: "
                    f"{response.status_code}. "
                    f"Attempt {attempt + 1}/{MAX_RETRIES}"
                )

                if attempt < MAX_RETRIES - 1:

                    delay = 2 ** attempt

                    print(
                        f"[explain] Retrying in {delay} seconds..."
                    )

                    time.sleep(delay)
                    continue

                break

            response.raise_for_status()

            break

        except httpx.RequestError as exc:

            print(
                f"[explain] Network error: "
                f"{type(exc).__name__}. "
                f"Attempt {attempt + 1}/{MAX_RETRIES}"
            )

            if attempt < MAX_RETRIES - 1:

                delay = 2 ** attempt

                print(
                    f"[explain] Retrying in {delay} seconds..."
                )

                time.sleep(delay)
                continue

            return fallback_explanation(
                outlier,
                f"gemini_network_error:{type(exc).__name__}"
            )

        except httpx.HTTPStatusError as exc:

            error_body = exc.response.text[:1000]

            print(
                "[explain] Gemini HTTP error: "
                f"Status={exc.response.status_code}"
            )

            print(
                f"[explain] Gemini error response: {error_body}"
            )

            return fallback_explanation(
                outlier,
                f"gemini_http_error:{exc.response.status_code}"
            )

    # Handle exhausted retries.
    if response is None or response.status_code in RETRYABLE_STATUS_CODES:

        if response is not None:

            print(
                "[explain] Gemini retries exhausted. "
                f"Last HTTP status: {response.status_code}"
            )

            return fallback_explanation(
                outlier,
                f"gemini_http_error:{response.status_code}"
            )

        return fallback_explanation(
            outlier,
            "gemini_request_failed"
        )

    # Read Gemini response.
    try:

        result = response.json()

        content = (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

    except (KeyError, IndexError, TypeError, ValueError):

        print(
            "[explain] Invalid Gemini response."
        )

        return fallback_explanation(
            outlier,
            "invalid_gemini_response"
        )

    parsed = parse_llm_content(content)

    if parsed is None:

        print(
            "[explain] Gemini returned invalid JSON content."
        )

        return fallback_explanation(
            outlier,
            "gemini_response_not_json"
        )

    print(
        "[explain] Gemini explanation generated successfully."
    )

    return {
        **parsed,
        "source": "gemini",
        "fallback_reason": None,
    }


# --------------------------------------------------
# EXPLAIN SERVER
# --------------------------------------------------

def explain_server(
    db: Session,
    server_id: int
) -> dict:
    """Generate explanation for GET /drift/{server_id}/explanation."""

    server = db.get(Server, server_id)

    if server is None:
        raise ValueError(
            f"Server {server_id} not found"
        )

    drift = detect_drift(db)

    comparison = next(
        (
            item
            for item in drift["server_comparisons"]
            if item["server_id"] == server_id
        ),
        None,
    )

    if comparison is None:
        raise ValueError(
            f"No fingerprint available for server {server_id}"
        )

    peer_differences = comparison.get(
        "differing_categories", []
    )

    baseline_differences = comparison.get(
        "baseline_differences", []
    )

    has_peer_drift = bool(peer_differences)

    has_baseline_drift = bool(baseline_differences)

    # A server can match the majority but still violate
    # the approved baseline.
    has_any_deviation = (
        has_peer_drift or has_baseline_drift
    )

    if not has_any_deviation:

        explanation = fallback_explanation(
            None,
            "no_detected_deviation"
        )

        explanation["source"] = "local"
        explanation["fallback_reason"] = None

    else:

        explanation = call_llm(
            comparison,
            drift["majority"],
            drift.get("majority_vs_baseline")
        )

    return {
        "server_id": server.id,
        "name": server.name,

        # Peer comparison status.
        "is_outlier": has_peer_drift,

        # Baseline comparison status.
        "has_baseline_deviation": has_baseline_drift,

        "baseline_status": comparison.get(
            "baseline_status",
            "not_configured"
        ),

        # Majority differences.
        "differing_categories": peer_differences,

        # Approved baseline differences.
        "baseline_differences": baseline_differences,

        # Majority baseline verification.
        "majority_vs_baseline": drift.get(
            "majority_vs_baseline"
        ),

        # Gemini explanation.
        "explanation": {
            "what_changed": explanation["what_changed"],
            "why_it_matters": explanation["why_it_matters"],
            "what_to_do_next": explanation["what_to_do_next"],
        },

        "source": explanation["source"],

        "fallback_reason": explanation.get(
            "fallback_reason"
        ),
    }
