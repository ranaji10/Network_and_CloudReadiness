from __future__ import annotations

import re
from collections.abc import Iterable

from readiness.models import DocumentRef

EXPORT_MIME = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}


def parse_folder_id(identifier: str) -> str:
    """Accepts a raw folder id or a Drive URL (…/folders/<id>, ?id=<id>). Mirrors the V1 agent behaviour."""
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", identifier) or re.search(r"[?&]id=([A-Za-z0-9_-]+)", identifier)
    return m.group(1) if m else identifier.strip()


class GoogleDriveSource:
    """Google Drive folder (recursive) as a document source, via Application Default Credentials.

    Requires `readiness[gcp]`. Read-only scope. Google-native docs are exported (Docs/Slides -> PDF,
    Sheets -> XLSX). Not yet exercised against a live Drive: see tracker item ING-04."""

    name = "gdrive"
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    def __init__(self, folder: str, max_bytes: int = 25 * 1024 * 1024):
        import google.auth
        from googleapiclient.discovery import build

        creds, _ = google.auth.default(scopes=self.SCOPES)
        self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.folder_id = parse_folder_id(folder)
        self.max_bytes = max_bytes

    def _walk(self, folder_id: str, path: str = ""):
        page = None
        while True:
            resp = (
                self._svc.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType, size)",
                    pageToken=page,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            for f in resp.get("files", []):
                rel = f"{path}/{f['name']}" if path else f["name"]
                if f["mimeType"] == "application/vnd.google-apps.folder":
                    yield from self._walk(f["id"], rel)
                else:
                    yield f, rel
            page = resp.get("nextPageToken")
            if not page:
                return

    def list(self) -> Iterable[DocumentRef]:
        for f, rel in self._walk(self.folder_id):
            size = int(f.get("size", 0) or 0)
            if size > self.max_bytes:
                continue
            mime = f["mimeType"]
            name = rel + EXPORT_MIME[mime][1] if mime in EXPORT_MIME else rel
            uri = f"gdrive://{f['id']}"
            yield DocumentRef(
                id=DocumentRef.make_id(uri),
                name=name,
                uri=uri,
                source=self.name,
                mime=mime,
                size_bytes=size or None,
            )

    def read(self, ref: DocumentRef) -> bytes:
        file_id = ref.uri.removeprefix("gdrive://")
        if ref.mime in EXPORT_MIME:
            return self._svc.files().export(fileId=file_id, mimeType=EXPORT_MIME[ref.mime][0]).execute()
        return self._svc.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
