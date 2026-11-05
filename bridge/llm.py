"""Optional IBM watsonx.ai inference.

The prototype runs fully on its deterministic rule engine so that the demo is
reproducible and costs nothing to replay. When watsonx credentials are present
in the environment, the interpretation and reason writing steps call Granite
instead and fall back to the rule engine on any error.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from . import config

_token_cache = {"token": None}


def _iam_token() -> Optional[str]:
    if _token_cache["token"]:
        return _token_cache["token"]
    if not config.WATSONX_API_KEY:
        return None
    body = urllib.parse.urlencode({
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": config.WATSONX_API_KEY,
    }).encode()
    req = urllib.request.Request(
        "https://iam.cloud.ibm.com/identity/token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            _token_cache["token"] = json.loads(resp.read())["access_token"]
            return _token_cache["token"]
    except Exception:
        return None


def generate(prompt: str, max_tokens: int = 240) -> Optional[str]:
    """Return model text, or None when watsonx is not configured or fails."""
    if not config.watsonx_configured():
        return None
    token = _iam_token()
    if not token:
        return None
    url = config.WATSONX_URL.rstrip("/") + \
        "/ml/v1/text/generation?version=2024-05-01"
    payload = {
        "model_id": config.WATSONX_MODEL_ID,
        "project_id": config.WATSONX_PROJECT_ID,
        "input": prompt,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": max_tokens,
            "repetition_penalty": 1.05,
        },
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer %s" % token})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read())
        return data["results"][0]["generated_text"].strip()
    except Exception:
        return None


def available() -> bool:
    return config.watsonx_configured()
