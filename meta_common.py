import os
import requests

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
TIMEOUT = 40


class MetaAPIError(RuntimeError):
    pass


def _check(response):
    try:
        payload = response.json()
    except ValueError:
        raise MetaAPIError(f"Meta returned non-JSON response: HTTP {response.status_code}")

    if not response.ok or "error" in payload:
        err = payload.get("error", {})
        message = err.get("message", response.text[:500])
        code = err.get("code", "unknown")
        raise MetaAPIError(f"Meta API error {code}: {message}")
    return payload


def graph_get(path, token, params=None):
    params = dict(params or {})
    params["access_token"] = token
    response = requests.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=TIMEOUT)
    return _check(response)


def graph_post(path, token, data=None):
    data = dict(data or {})
    data["access_token"] = token
    response = requests.post(f"{BASE}/{path.lstrip('/')}", data=data, timeout=TIMEOUT)
    return _check(response)


def required_env(*names):
    missing = [name for name in names if not os.getenv(name, "").strip()]
    if missing:
        raise MetaAPIError("Missing environment variables: " + ", ".join(missing))
