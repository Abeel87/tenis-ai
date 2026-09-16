#!/usr/bin/env python3
"""Garbage-collect retired private runtime generations via GitHub OIDC."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

AUDIENCE = "tenis-ai-runtime-gc"
GC_URL = "https://kplcfqmcsukiqfbgvxcm.supabase.co/functions/v1/runtime-data-gc"


class GCError(RuntimeError):
    pass


def _json_request(url: str, *, headers=None, body=None, timeout=60):
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=payload, headers=request_headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            parsed = {"detail": raw.decode("utf-8", errors="replace")}
        return exc.code, parsed


def oidc_token() -> str:
    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not request_url or not request_token:
        raise GCError("GitHub OIDC environment is unavailable")
    separator = "&" if "?" in request_url else "?"
    url = f"{request_url}{separator}audience={urllib.parse.quote(AUDIENCE)}"
    status, data = _json_request(url, headers={"Authorization": f"Bearer {request_token}"}, timeout=30)
    token = data.get("value") if isinstance(data, dict) else None
    if status != 200 or not isinstance(token, str) or not token:
        raise GCError(f"GitHub OIDC token request failed: HTTP {status}")
    return token


def collect(*, dry_run: bool) -> dict:
    status, data = _json_request(
        GC_URL,
        headers={"Authorization": f"Bearer {oidc_token()}"},
        body={"action": "collect", "dry_run": dry_run},
        timeout=120,
    )
    if status != 200 or not isinstance(data, dict) or data.get("ok") is not True:
        raise GCError(f"runtime GC failed: HTTP {status} {data}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = collect(dry_run=args.dry_run)
    except GCError as exc:
        print(f"RUNTIME_PRIVATE_GC_ERROR {exc}", file=sys.stderr)
        return 1
    print("RUNTIME_PRIVATE_GC_OK " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
