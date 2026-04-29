"""Tiny Supabase REST client — POST /rest/v1/runs only.

The default URL + key below are SAFE TO COMMIT — `sb_publishable_*` keys
are Supabase's documented "embed in client code" key and the project URL
is public. RLS on the server gates writes. Override via env vars if you
self-host.
"""
from __future__ import annotations

import json
import os
import urllib.request


DEFAULT_SUPABASE_URL = "https://cbqzjwdviifvwlpwsjdm.supabase.co"
DEFAULT_SUPABASE_ANON_KEY = "sb_publishable_k6C9lKKuF0097AHDvGYnPw_E7QWv2mW"


def submit_run(payload: dict, *, supabase_url: str | None = None, anon_key: str | None = None) -> dict:
    """POST a run to the Supabase `runs` table. Returns the inserted row dict."""
    supabase_url = (
        supabase_url
        or os.environ.get("SUPABASE_URL")
        or DEFAULT_SUPABASE_URL
    )
    anon_key = (
        anon_key
        or os.environ.get("SUPABASE_ANON_KEY")
        or DEFAULT_SUPABASE_ANON_KEY
    )

    url = f"{supabase_url.rstrip('/')}/rest/v1/runs"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Prefer": "return=representation",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        rows = json.loads(r.read())
    return rows[0] if isinstance(rows, list) and rows else {}
