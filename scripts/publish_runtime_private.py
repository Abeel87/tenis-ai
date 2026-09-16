#!/usr/bin/env python3
"""Publish a content-addressed private runtime-data snapshot via GitHub OIDC.

This is a staging/dual-write path. It never changes model output, Superbet authority,
PLAYABLE, Symphony, Neuron, Player DNA, or iNeed$ calculations.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

AUDIENCE = "tenis-ai-runtime-publisher"
PUBLISHER_URL = (
    "https://kplcfqmcsukiqfbgvxcm.supabase.co/functions/v1/runtime-data-publish"
)
FRONTEND = Path("frontend")
DATA = FRONTEND / "data"

# B = data required by an authenticated normal product view.
# Everything else defaults to C (admin/technical) so an unknown file can never
# accidentally become less restricted during the migration.
B_EXACT = {
    "data/delivery/index.json",
    "data/delivery/symphony.json",
    "data/history.json",
    "data/match_detail_history.json",
    "data/player_dna_current_simulation.json",
    "data/superbet_direct_current.json",
}
B_PATTERNS = (
    "data/delivery/matches/*.json",
)


class PublishError(RuntimeError):
    pass


def tier_for(logical_path: str) -> str:
    if logical_path in B_EXACT:
        return "b"
    if any(fnmatch.fnmatch(logical_path, pattern) for pattern in B_PATTERNS):
        return "b"
    return "c"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_files() -> tuple[list[dict[str, Any]], dict[str, Path]]:
    if not DATA.is_dir():
        raise PublishError("frontend/data is missing")

    rows: list[dict[str, Any]] = []
    by_hash: dict[str, Path] = {}
    for source in sorted(DATA.rglob("*.json")):
        if not source.is_file():
            continue
        logical = source.relative_to(FRONTEND).as_posix()
        size = source.stat().st_size
        if size > 104857600:
            raise PublishError(f"{logical} exceeds the 100 MiB private-object limit")
        digest = sha256_file(source)
        rows.append(
            {
                "path": logical,
                "tier": tier_for(logical),
                "sha256": digest,
                "size_bytes": size,
            }
        )
        by_hash.setdefault(digest, source)

    if not rows:
        raise PublishError("No frontend/data JSON files found")
    return rows, by_hash


def _json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: int = 60,
) -> tuple[int, Any]:
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        url,
        data=payload,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return response.status, parsed
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
        raise PublishError("GitHub OIDC environment is unavailable")

    separator = "&" if "?" in request_url else "?"
    url = f"{request_url}{separator}audience={urllib.parse.quote(AUDIENCE)}"
    status, data = _json_request(
        url,
        headers={"Authorization": f"Bearer {request_token}"},
        timeout=30,
    )
    token = data.get("value") if isinstance(data, dict) else None
    if status != 200 or not isinstance(token, str) or not token:
        raise PublishError(f"GitHub OIDC token request failed: HTTP {status}")
    return token


def publisher_call(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    status, data = _json_request(
        PUBLISHER_URL,
        method="POST",
        headers={"Authorization": f"Bearer {oidc_token()}"},
        body=body,
        timeout=60,
    )
    if not isinstance(data, dict):
        data = {"detail": data}
    return status, data


def upload_signed(url: str, source: Path) -> None:
    # createSignedUploadUrl is bearer-less by design; the short-lived token is
    # embedded in the URL. Raw-body PUT matches storage-js uploadToSignedUrl.
    request = urllib.request.Request(
        url,
        data=source.read_bytes(),
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "max-age=3600",
            "x-upsert": "false",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            if response.status not in (200, 201):
                raise PublishError(
                    f"Signed upload returned unexpected HTTP {response.status}"
                )
    except urllib.error.HTTPError as exc:
        # Content-addressed objects are immutable. A 409 only means another
        # concurrent generation already uploaded the exact same SHA object.
        if exc.code != 409:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PublishError(
                f"Signed upload failed for {source}: HTTP {exc.code} {detail[:300]}"
            ) from exc


def publish(layer: str, *, attempts: int = 2) -> dict[str, Any]:
    files, by_hash = snapshot_files()

    for attempt in range(1, attempts + 1):
        status, prepared = publisher_call(
            {"action": "prepare", "layer": layer, "files": files}
        )
        if status != 200:
            raise PublishError(
                f"prepare failed: HTTP {status} {prepared.get('error') or prepared}"
            )

        uploads = prepared.get("uploads") or []
        for item in uploads:
            digest = str(item.get("sha256") or "")
            source = by_hash.get(digest)
            signed_url = item.get("signed_url")
            if source is None or not isinstance(signed_url, str) or not signed_url:
                raise PublishError("publisher returned an invalid upload manifest")
            upload_signed(signed_url, source)

        activation_body = {
            "action": "activate",
            "layer": layer,
            "generation": prepared.get("generation"),
            "expected_generation": prepared.get("expected_generation"),
        }
        status, activated = publisher_call(activation_body)
        if status == 200 and activated.get("ok") is True:
            return {
                "layer": layer,
                "generation": activated.get("generation"),
                "files": len(files),
                "uploaded_objects": len(uploads),
            }

        if status == 409 and attempt < attempts:
            # A same-layer publication won the CAS race. Re-snapshot the current
            # checked-out ref and retry against the new head once.
            time.sleep(1)
            continue

        raise PublishError(
            f"activate failed: HTTP {status} {activated.get('error') or activated}"
        )

    raise PublishError("private runtime publication exhausted retries")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layer",
        required=True,
        choices=("core", "market", "dna", "neuron"),
    )
    args = parser.parse_args()

    try:
        result = publish(args.layer)
    except PublishError as exc:
        print(f"RUNTIME_PRIVATE_PUBLISH_ERROR {exc}", file=sys.stderr)
        return 1

    print("RUNTIME_PRIVATE_PUBLISH_OK " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
