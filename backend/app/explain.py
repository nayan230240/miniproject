# LLM explanation service.
#
# Flow:
#   1. Reuse the drift detector to find this server's outlier row
#      (which categories differ from the majority).
#   2. Send that JSON to an LLM and ask for three plain-language parts:
#        - what changed
#        - why it matters (security / reliability)
#        - what to do next
#   3. If the key is missing or the HTTP call fails, return a fallback
#      that still lists the drifted categories so the UI never goes blank.
#
# The API key is read from LLM_API_KEY (or OPENAI_API_KEY). It is never
# hardcoded and never logged.

from __future__ import annotations

import json
import os

import httpx
from sqlalchemy.orm import Session

from app.drift import detect_drift
from app.models import Server

# Default is OpenAI's Chat Completions URL. Override with LLM_API_URL
# if you use a compatible proxy (Azure, Groq, a local server, ...).
DEFAULT_LLM_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_LLM_MODEL = "gpt-4o-mini"


def api_key() -> str:
    """Prefer LLM_API_KEY, then the common OPENAI_API_KEY name."""
    return (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


def llm_url() -> str:
    return os.getenv("LLM_API_URL", DEFAULT_LLM_URL).strip()


def llm_model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip()


def fallback_explanation(outlier: dict | None, reason: str) -> dict:
    """
    Human-readable backup when we cannot reach the LLM.
    Still mentions the drifted categories so an operator can act.
    """
    if outlier is None:
        what = "This server matches the majority configuration. Nothing drifted."
        why = "No extra security or reliability risk from config drift right now."
        next_step = "No action needed. Keep polling and re-check after the next change."
    else:
        names = [item["category"] for item in outlier.get("differing_categories", [])]
        listed = ", ".join(names) if names else "unknown categories"
        what = (
            f"Server {outlier.get('name')} differs from the majority in: {listed}. "
            "The AI narrator could not be reached, so this is a mechanical summary."
        )
        why = (
            "Config drift can mean an unpatched package, an extra open port, or a "
            "weaker SSH setting — each of those can hurt security or reliability."
        )
        next_step = (
            "Compare the majority_value and server_value for each drifted category, "
            "then either restore the golden config or document the exception."
        )
    return {
        "what_changed": what,
        "why_it_matters": why,
        "what_to_do_next": next_step,
        "source": "fallback",
        "fallback_reason": reason,
    }


def build_prompt(outlier: dict, majority: dict) -> str:
    """Pack the drift JSON into a short prompt. Keep it factual, not fluffy."""
    payload = {
        "server": outlier.get("name"),
        "majority_servers": majority.get("servers"),
        "differing_categories": outlier.get("differing_categories"),
    }
    return (
        "You explain configuration drift to a junior sysadmin.\n"
        "Use ONLY the JSON below. Do not invent extra facts.\n"
        "Reply with a JSON object that has exactly these keys:\n"
        "  what_changed, why_it_matters, what_to_do_next\n"
        "why_it_matters must mention security and/or reliability risk.\n"
        "Keep each value to 2-4 sentences, plain language.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )


def parse_llm_content(content: str) -> dict | None:
    """Try to read the three fields out of the model reply."""
    text = (content or "").strip()
    if text.startswith("```"):
        # Models sometimes wrap JSON in a markdown fence.
        lines = [line for line in text.splitlines() if not line.startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    keys = ("what_changed", "why_it_matters", "what_to_do_next")
    if not all(isinstance(data.get(key), str) and data.get(key).strip() for key in keys):
        return None
    return {key: data[key].strip() for key in keys}


def call_llm(outlier: dict, majority: dict) -> dict:
    """
    POST a chat completion. Returns either the parsed LLM JSON or a fallback.
    Never raises — the API endpoint always gets something to show.
    """
    key = api_key()
    if not key:
        return fallback_explanation(outlier, "missing_api_key")

    body = {
        "model": llm_model(),
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "You are Configo's drift narrator. Reply with JSON only.",
            },
            {"role": "user", "content": build_prompt(outlier, majority)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(llm_url(), headers=headers, json=body, timeout=20.0)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        # Do not include headers or the key in this message.
        print(f"[explain] LLM call failed: {type(exc).__name__}: {exc}")
        return fallback_explanation(outlier, f"llm_call_failed:{type(exc).__name__}")

    parsed = parse_llm_content(content)
    if parsed is None:
        return fallback_explanation(outlier, "llm_response_not_json")

    return {**parsed, "source": "llm", "fallback_reason": None}


def explain_server(db: Session, server_id: int) -> dict:
    """
    Build GET /drift/{server_id}/explanation.
    Raises ValueError if the server id does not exist (route turns that into 404).
    """
    server = db.get(Server, server_id)
    if server is None:
        raise ValueError(f"Server {server_id} not found")

    drift = detect_drift(db)
    outlier = next(
        (item for item in drift["outliers"] if item["server_id"] == server_id),
        None,
    )

    if outlier is None:
        explanation = fallback_explanation(None, "not_an_outlier")
        explanation["source"] = "local"
        explanation["fallback_reason"] = None
    else:
        explanation = call_llm(outlier, drift["majority"])

    return {
        "server_id": server.id,
        "name": server.name,
        "is_outlier": outlier is not None,
        "differing_categories": [] if outlier is None else outlier["differing_categories"],
        "explanation": {
            "what_changed": explanation["what_changed"],
            "why_it_matters": explanation["why_it_matters"],
            "what_to_do_next": explanation["what_to_do_next"],
        },
        "source": explanation["source"],
        "fallback_reason": explanation.get("fallback_reason"),
    }
