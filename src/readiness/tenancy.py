"""Per-tenant export and purge (tracker MIG-05).

Every artefact the tool stores for a client lives under a `<tenant_id>/` prefix: the pipeline workspace
(`<workspace>/<tenant>/<run>/...`), the reports store (`<tenant>/<run>/report.*`) and, by convention,
the uploads store. That makes "give the client their data back" and "delete everything about this
client" a prefix listing. Audit lines contain no document content and are not part of the purge."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from readiness.ports import BlobStore

_TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_tenant_id(tenant_id: str) -> str:
    tenant_id = tenant_id.strip().strip("/")
    if not _TENANT_RE.match(tenant_id) or ".." in tenant_id:
        raise ValueError("tenant id must be 1-64 chars of letters, digits, '.', '_' or '-' and contain no '/'")
    return tenant_id


def tenant_keys(store: BlobStore, tenant_id: str) -> list[str]:
    prefix = validate_tenant_id(tenant_id) + "/"
    return sorted(k for k in store.list(prefix) if k.startswith(prefix))


def export_tenant(stores: dict[str, BlobStore], tenant_id: str, out_zip: Path) -> dict[str, Any]:
    """Write every object of the tenant from each named store into one zip (+ manifest.json inside and beside it).

    `stores` maps a label (e.g. "workspace", "reports") to a store; the label becomes the top-level folder in the
    zip so keys from different stores never collide."""
    tenant_id = validate_tenant_id(tenant_id)
    files: list[dict[str, Any]] = []
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for label, store in stores.items():
            for key in tenant_keys(store, tenant_id):
                data = store.get(key)
                arc = f"{label}/{key}"
                zf.writestr(arc, data)
                files.append(
                    {"store": label, "key": key, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                )
        manifest = {
            "tenant_id": tenant_id,
            "exported_at": datetime.now(UTC).isoformat(),
            "stores": list(stores),
            "file_count": len(files),
            "total_bytes": sum(f["size"] for f in files),
            "files": files,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=1))
    out_zip.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def purge_tenant(stores: dict[str, BlobStore], tenant_id: str, dry_run: bool = True) -> dict[str, list[str]]:
    """Delete (or with dry_run just list) every object of the tenant in each store. Returns keys per store label."""
    tenant_id = validate_tenant_id(tenant_id)
    result: dict[str, list[str]] = {}
    for label, store in stores.items():
        keys = tenant_keys(store, tenant_id)
        if not dry_run:
            for key in keys:
                store.delete(key)
        result[label] = keys
    return result


def read_manifest(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as zf:
        return json.loads(io.TextIOWrapper(zf.open("manifest.json"), encoding="utf-8").read())
