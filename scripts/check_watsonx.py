"""Check whether IBM watsonx.ai is actually reachable and answering.

Run this before an evaluation run that is meant to use Granite. The point is to
fail loudly. bridge/llm.py deliberately swallows errors and falls back to the
rule engine, which is right at run time but useless when you are trying to find
out whether watsonx was used at all.

    py scripts/check_watsonx.py

This script never prints your API key, and never writes it anywhere.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge import config  # noqa: E402


def mask(value: str) -> str:
    """Enough to confirm something is set, not enough to use."""
    if not value:
        return "NOT SET"
    if len(value) <= 8:
        return "set, %d characters" % len(value)
    return "set, %d characters, ends %s" % (len(value), value[-4:])


def list_granite_models() -> None:
    """On a model error, show what this region actually serves.

    The model catalogue endpoint needs no authentication, so this still works
    when the model id is the only thing wrong.
    """
    url = (config.WATSONX_URL.rstrip("/")
           + "/ml/v1/foundation_model_specs?version=2024-05-01&limit=200")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as exc:  # noqa: BLE001
        print("\n  Could not list the available models: %s" % exc)
        return
    names = sorted(m.get("model_id", "") for m in data.get("resources", []))
    # Granite 4 dropped the word "instruct" from its model ids, so match on
    # what a model is not: base models complete text rather than follow
    # instructions, and embedding and time series models cannot answer at all.
    skip = ("-base", "embedding", "-ttm-", "rtrvr")
    granite = [n for n in names
               if "granite" in n and not any(k in n for k in skip)]
    if granite:
        print("\n  Granite models this region serves that can answer:")
    else:
        granite = names[:20]
        print("\n  No usable Granite model here. First models served:")
    for name in granite:
        print("    %s" % name)
    print("\n  Pick one and set it, then run this check again:")
    print('    $env:WATSONX_MODEL_ID = "<one id from the list above>"')


def step(n: int, label: str) -> None:
    print("\n[%d] %s" % (n, label))
    print("-" * 62)


def main() -> int:
    print("=" * 62)
    print("IBM watsonx.ai connectivity check")
    print("=" * 62)

    step(1, "Are the three settings present?")
    print("  WATSONX_API_KEY     %s" % mask(config.WATSONX_API_KEY))
    print("  WATSONX_URL         %s" % (config.WATSONX_URL or "NOT SET"))
    print("  WATSONX_PROJECT_ID  %s" % (config.WATSONX_PROJECT_ID or "NOT SET"))
    print("  WATSONX_MODEL_ID    %s" % config.WATSONX_MODEL_ID)

    if not config.watsonx_configured():
        print("\n  RESULT: not configured. The system will use the rule")
        print("  engine. That is a valid choice, but do not claim watsonx.ai")
        print("  ran in your technology statement.")
        return 1

    step(2, "Can we exchange the API key for an IAM token?")
    body = urllib.parse.urlencode({
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": config.WATSONX_API_KEY,
    }).encode()
    req = urllib.request.Request(
        "https://iam.cloud.ibm.com/identity/token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            token = json.loads(resp.read())["access_token"]
        print("  OK, token received (%d characters, not shown)" % len(token))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        print("  FAILED, HTTP %s" % exc.code)
        print("  %s" % detail)
        print("\n  Usual cause: the API key is wrong, or it was revoked.")
        print("  Make a new one at cloud.ibm.com, Manage, Access (IAM),")
        print("  API keys.")
        return 2
    except Exception as exc:  # noqa: BLE001
        print("  FAILED: %s" % exc)
        print("\n  Usual cause: no network, or a proxy blocking")
        print("  iam.cloud.ibm.com.")
        return 2

    step(3, "Does the model answer?")
    url = config.WATSONX_URL.rstrip("/") + "/ml/v1/text/generation?version=2024-05-01"
    payload = {
        "model_id": config.WATSONX_MODEL_ID,
        "project_id": config.WATSONX_PROJECT_ID,
        "input": ("You read short messages from patients recovering at home "
                  "after a hospital stay. Do not give advice. Do not diagnose.\n"
                  "Message: Scale is up four pounds since Monday and the shoes "
                  "are tight.\n"
                  "Answer with one word only, from: none, mild, rising, urgent.\n"
                  "Answer:"),
        "parameters": {"decoding_method": "greedy", "max_new_tokens": 5},
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer %s" % token})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        answer = data["results"][0]["generated_text"].strip()
        print("  OK. Model replied: %r" % answer)
        print("  Endpoint: %s" % config.WATSONX_URL)
        print("  Model:    %s" % config.WATSONX_MODEL_ID)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        print("  FAILED, HTTP %s" % exc.code)
        print("  %s" % detail)
        print("\n  Common causes:")
        print("  404  the model id has been retired, or the WATSONX_URL")
        print("       region is wrong for your account")
        print("  403  the project id is wrong, or the key has no access to it")
        print("  400  the model id is not available in your region or plan")
        if exc.code in (400, 404) or "model_not_supported" in detail:
            list_granite_models()
        return 3
    except Exception as exc:  # noqa: BLE001
        print("  FAILED: %s" % exc)
        return 3

    print("\n" + "=" * 62)
    print("RESULT: watsonx.ai is live. An evaluation run started from this")
    print("same shell will use Granite for reply interpretation.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
