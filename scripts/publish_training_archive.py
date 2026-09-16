#!/usr/bin/env python3
"""Publish raw training inputs to the durable private archive via GitHub OIDC.

This only archives already-produced cache inputs. It does not change model math,
training, Player DNA, Surface Elo, Symphony, Neuron, PLAYABLE, settlement,
SHADOW/PROD or iNeed$ calculations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

AUDIENCE = "tenis-ai-training-archive-publisher"
PUBLISHER_URL = "https://kplcfqmcsukiqfbgvxcm.supabase.co/functions/v1/training-archive-publish"
DEFAULT_CACHE_ROOT = Path("data/cache")
DEFAULT_INVENTORY = Path("artifacts/training_archive_inventory.json")
MAX_OBJECT_BYTES = 45 * 1024 * 1024
BATCH_SIZE = 200


class ArchivePublishError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_type(path: Path) -> str:
    return "application/gzip" if path.name.endswith(".gz") else "application/json"


def batches(rows: list[dict[str, Any]], size: int = BATCH_SIZE) -> Iterable[list[dict[str, Any]]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def prepare_candidates(inventory: dict[str, Any], cache_root: Path) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    summary = inventory.get("summary") or {}
    raw_rows = inventory.get("archive_candidates") or []
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ArchivePublishError("inventory has no archive candidates")
    if int(summary.get("archive_candidate_files") or 0) != len(raw_rows):
        raise ArchivePublishError("inventory candidate count does not match summary")

    root = cache_root.resolve()
    rows: list[dict[str, Any]] = []
    by_sha: dict[str, Path] = {}
    seen_paths: set[str] = set()
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ArchivePublishError("inventory candidate is not an object")
        logical = str(raw.get("logical_path") or "").replace("\\", "/").lstrip("./")
        if not logical or ".." in logical:
            raise ArchivePublishError(f"unsafe logical path: {logical}")
        source = (cache_root / logical).resolve()
        if root not in source.parents:
            raise ArchivePublishError(f"candidate escapes cache root: {logical}")
        if not source.is_file():
            raise ArchivePublishError(f"archive source is missing: {logical}")
        if logical in seen_paths:
            raise ArchivePublishError(f"duplicate logical path: {logical}")
        seen_paths.add(logical)

        expected_size = int(raw.get("size_bytes") or 0)
        actual_size = source.stat().st_size
        if actual_size != expected_size:
            raise ArchivePublishError(f"size changed after inventory: {logical}")
        if actual_size > MAX_OBJECT_BYTES:
            raise ArchivePublishError(f"archive object exceeds 45 MiB: {logical}")

        expected_sha = str(raw.get("sha256") or "").lower()
        actual_sha = sha256_file(source)
        if actual_sha != expected_sha:
            raise ArchivePublishError(f"sha256 changed after inventory: {logical}")

        row = {
            "path": logical,
            "class": str(raw.get("class") or ""),
            "provider": str(raw.get("provider") or ""),
            "sha256": actual_sha,
            "size_bytes": actual_size,
        }
        rows.append(row)
        by_sha.setdefault(actual_sha, source)

    return rows, by_sha


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
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
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
        raise ArchivePublishError("GitHub OIDC environment is unavailable")
    separator = "&" if "?" in request_url else "?"
    url = f"{request_url}{separator}audience={urllib.parse.quote(AUDIENCE)}"
    status, data = _json_request(url, headers={"Authorization": f"Bearer {request_token}"}, timeout=30)
    token = data.get("value") if isinstance(data, dict) else None
    if status != 200 or not isinstance(token, str) or not token:
        raise ArchivePublishError(f"GitHub OIDC token request failed: HTTP {status}")
    return token


def publisher_call(body: dict[str, Any]) -> dict[str, Any]:
    status, data = _json_request(
        PUBLISHER_URL,
        method="POST",
        headers={"Authorization": f"Bearer {oidc_token()}"},
        body=body,
        timeout=90,
    )
    if not isinstance(data, dict):
        data = {"detail": data}
    if status != 200:
        raise ArchivePublishError(f"publisher {body.get('action')} failed: HTTP {status} {data.get('error') or data}")
    return data


def upload_signed(url: str, source: Path) -> None:
    request = urllib.request.Request(
        url,
        data=source.read_bytes(),
        headers={
            "Content-Type": content_type(source),
            "Cache-Control": "max-age=31536000, immutable",
            "x-upsert": "false",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            if response.status not in (200, 201):
                raise ArchivePublishError(f"signed upload returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        # Immutable content addressing makes an existing object safe to reuse.
        if exc.code != 409:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ArchivePublishError(f"signed upload failed: HTTP {exc.code} {detail[:300]}") from exc


def _optional_positive_env(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    value = int(raw)
    if value <= 0:
        raise ArchivePublishError(f"{name} must be positive")
    return value


def publish(inventory_path: Path, cache_root: Path) -> dict[str, Any]:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    rows, by_sha = prepare_candidates(inventory, cache_root)
    summary = inventory["summary"]

    started = publisher_call(
        {
            "action": "start",
            "inventory_schema_version": int(inventory.get("schema_version") or 0),
            "expected_files": int(summary["archive_candidate_files"]),
            "expected_bytes": int(summary["archive_candidate_bytes"]),
            "expected_unique_objects": int(summary["unique_archive_objects"]),
            "expected_unique_bytes": int(summary["unique_archive_bytes"]),
            "source_cache_key": os.environ.get("TRAINING_ARCHIVE_SOURCE_CACHE_KEY") or None,
            "producer_run_id": _optional_positive_env("TRAINING_ARCHIVE_PRODUCER_RUN_ID"),
            "producer_head_sha": os.environ.get("TRAINING_ARCHIVE_PRODUCER_HEAD_SHA") or None,
        }
    )
    manifest_id = str(started.get("manifest_id") or "")
    if not manifest_id:
        raise ArchivePublishError("publisher did not return manifest_id")
    if started.get("status") == "complete":
        return {"manifest_id": manifest_id, "files": len(rows), "uploaded_objects": 0, "reused": True}

    uploaded = 0
    for batch in batches(rows):
        prepared = publisher_call({"action": "prepare_batch", "manifest_id": manifest_id, "files": batch})
        uploads = prepared.get("uploads") or []
        for item in uploads:
            sha = str(item.get("sha256") or "")
            source = by_sha.get(sha)
            signed_url = item.get("signed_url")
            if source is None or not isinstance(signed_url, str) or not signed_url:
                raise ArchivePublishError("publisher returned an invalid upload manifest")
            upload_signed(signed_url, source)
            uploaded += 1

        unique_shas = list(dict.fromkeys(str(row["sha256"]) for row in batch))
        publisher_call({"action": "confirm_batch", "manifest_id": manifest_id, "sha256": unique_shas})

    completed = publisher_call({"action": "complete", "manifest_id": manifest_id})
    if completed.get("ok") is not True:
        raise ArchivePublishError("archive manifest did not complete")
    return {"manifest_id": manifest_id, "files": len(rows), "uploaded_objects": uploaded, "reused": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish durable training archive inputs")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    args = parser.parse_args()
    try:
        result = publish(args.inventory, args.cache_root)
    except (ArchivePublishError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"TRAINING_ARCHIVE_PUBLISH_ERROR {exc}", file=sys.stderr)
        return 1
    print("TRAINING_ARCHIVE_PUBLISH_OK " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
