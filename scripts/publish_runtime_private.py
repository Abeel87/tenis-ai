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
import shutil
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

# Keep a safety margin below the current 50 MB global Storage upload limit on
# the free project. A bucket-specific 100 MiB limit cannot raise that global cap.
MAX_OBJECT_SIZE = 45 * 1024 * 1024
HISTORY_CHUNK_TARGET = 20 * 1024 * 1024

# B = data required by an authenticated normal product view.
# Everything else defaults to C (admin/technical) so an unknown file can never
# accidentally become less restricted during the migration.
B_EXACT = {
    "data/delivery/index.json",
    "data/delivery/symphony.json",
    "data/match_detail_history.json",
    "data/player_dna_current_simulation.json",
    "data/superbet_direct_current.json",
    "data/private/history/manifest.json",
}
B_PATTERNS = (
    "data/delivery/matches/*.json",
    "data/private/history/chunks/*.json",
)

# Provenance scopes. These do not create new model authorities; they only keep
# one producer from republishing unrelated runtime files.
NEURON_EXACT = {
    "data/neuron_current.json",
    "data/neuron_metrics.json",
    "data/neuron_model.json",
}
DNA_PATTERNS = (
    "data/player_dna_*.json",
)
MARKET_EXACT = {
    "data/results.json",
    "data/meta.json",
    "data/player_model_shadow_v89.json",
    "data/ensemble_player_learning_v891.json",
    "data/surface_elo_integration_v893.json",
}
MARKET_PATTERNS = (
    "data/superbet_*.json",
    "data/symphony2_*.json",
    "data/market_lab_*.json",
    "data/shadow_*.json",
)


class PublishError(RuntimeError):
    pass


def tier_for(logical_path: str) -> str:
    if logical_path in B_EXACT:
        return "b"
    if any(fnmatch.fnmatch(logical_path, pattern) for pattern in B_PATTERNS):
        return "b"
    return "c"


def owner_layer(logical_path: str) -> str:
    if logical_path.startswith("data/delivery/"):
        return "core"
    if logical_path in NEURON_EXACT:
        return "neuron"
    if any(fnmatch.fnmatch(logical_path, pattern) for pattern in DNA_PATTERNS):
        return "dna"
    if logical_path in MARKET_EXACT:
        return "market"
    if any(fnmatch.fnmatch(logical_path, pattern) for pattern in MARKET_PATTERNS):
        return "market"
    return "core"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _projection_dir() -> Path:
    base = Path(os.environ.get("RUNNER_TEMP") or ".runtime-private")
    target = base / "tenis-ai-private-projection"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _chunk_history(source: Path, projection: Path) -> list[tuple[str, Path]]:
    try:
        rows = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PublishError(f"Cannot parse {source}: {exc}") from exc
    if not isinstance(rows, list):
        raise PublishError("data/history.json must be a JSON array")

    source_sha = sha256_file(source)
    source_size = source.stat().st_size
    chunks: list[dict[str, Any]] = []
    materialized: list[tuple[str, Path]] = []
    current: list[bytes] = []
    current_size = 2  # []

    def flush() -> None:
        nonlocal current, current_size
        if not current:
            return
        index = len(chunks)
        logical = f"data/private/history/chunks/{index:04d}.json"
        local = projection / f"history-chunk-{index:04d}.json"
        payload = b"[" + b",".join(current) + b"]"
        if len(payload) > MAX_OBJECT_SIZE:
            raise PublishError(f"{logical} exceeds private object limit after chunking")
        _write_bytes(local, payload)
        chunks.append(
            {
                "path": logical,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
                "entries": len(current),
            }
        )
        materialized.append((logical, local))
        current = []
        current_size = 2

    for row in rows:
        encoded = json.dumps(
            row,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) + 2 > HISTORY_CHUNK_TARGET:
            raise PublishError("A single history entry exceeds the chunk target")
        added = len(encoded) + (1 if current else 0)
        if current and current_size + added > HISTORY_CHUNK_TARGET:
            flush()
            added = len(encoded)
        current.append(encoded)
        current_size += added
    flush()

    manifest = {
        "schema": 1,
        "format": "json-array-chunks-v1",
        "source_path": "data/history.json",
        "source_sha256": source_sha,
        "source_size_bytes": source_size,
        "entry_count": len(rows),
        "chunk_target_bytes": HISTORY_CHUNK_TARGET,
        "chunks": chunks,
    }
    manifest_payload = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    manifest_local = projection / "history-manifest.json"
    _write_bytes(manifest_local, manifest_payload)
    materialized.insert(0, ("data/private/history/manifest.json", manifest_local))
    return materialized


def snapshot_files(layer: str) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    if layer not in {"core", "market", "dna", "neuron"}:
        raise PublishError(f"Unknown layer: {layer}")
    if not DATA.is_dir():
        raise PublishError("frontend/data is missing")

    projection = _projection_dir()
    selected: list[tuple[str, Path]] = []
    for source in sorted(DATA.rglob("*.json")):
        if not source.is_file():
            continue
        logical = source.relative_to(FRONTEND).as_posix()
        if logical.startswith("data/private/"):
            continue
        if owner_layer(logical) != layer:
            continue
        if logical == "data/history.json":
            selected.extend(_chunk_history(source, projection))
            continue
        selected.append((logical, source))

    rows: list[dict[str, Any]] = []
    by_hash: dict[str, Path] = {}
    seen_paths: set[str] = set()
    for logical, source in selected:
        if logical in seen_paths:
            raise PublishError(f"Duplicate logical path: {logical}")
        seen_paths.add(logical)
        size = source.stat().st_size
        if size > MAX_OBJECT_SIZE:
            raise PublishError(
                f"{logical} exceeds the {MAX_OBJECT_SIZE} byte private-object limit"
            )
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
        raise PublishError(f"No frontend/data JSON files found for layer {layer}")
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
    files, by_hash = snapshot_files(layer)

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
