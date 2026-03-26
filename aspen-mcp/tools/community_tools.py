"""Community sharing tool — post resolved errors to shared Google Sheet."""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

log = logging.getLogger("tools")

# The Apps Script URL configured in error-history.md
_APPS_SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzw1RdzicxmracN0kjIFZPnar0z2gSY95WqtnB-q7bee3UIk2PlNPsqArZB_TY5WEKCHw"
    "/exec"
)


def share_error(
    error_keyword: str,
    block_type: str,
    property_method: str,
    cause: str,
    fix_direction: str,
    fix_path: str,
    tried_failed: str = "",
) -> str:
    """Post a resolved error record to the community Google Sheet."""
    payload = json.dumps({
        "error_keyword": error_keyword,
        "block_type": block_type,
        "property_method": property_method,
        "cause": cause,
        "fix_direction": fix_direction,
        "fix_path": fix_path,
        "tried_failed": tried_failed,
    }).encode("utf-8")

    req = urllib.request.Request(
        _APPS_SCRIPT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            # Apps Script may return JSON or HTML — both indicate success
            # if we got here without an HTTP error
            try:
                result = json.loads(body)
                if result.get("status") == "ok":
                    return "Shared to community Google Sheet successfully."
            except json.JSONDecodeError:
                pass
            return "Shared to community Google Sheet (posted successfully)."
    except urllib.error.HTTPError as exc:
        # Google Apps Script redirects POST; some redirect responses
        # return non-2xx but the data is still written.
        # 200-399 range: treat as success
        if exc.code < 400:
            return "Shared to community Google Sheet (posted successfully)."
        log.error("share_error HTTP %s: %s", exc.code, exc.reason)
        return f"Failed to share: HTTP {exc.code} {exc.reason}"
    except Exception as exc:
        log.error("share_error failed: %s", exc)
        return f"Failed to share: {exc}"
