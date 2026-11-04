"""Private Vercel Blob snapshots with origin reads and atomic conditional writes.

The Python Blob SDK currently lacks conditional PUT. The HTTP adapter follows the
official vercel/storage SDK's v13 protocol; see docs/architecture.md for sources.
"""

import os
import re
from typing import Optional

import httpx


class SnapshotConflict(Exception):
    """A concurrent request changed the workspace; no update was committed."""


class BlobSnapshots:
    """Server-only capability storage, with no credentials returned to clients."""

    def __init__(self, transport=None):
        store = os.environ.get("BLOB_STORE_ID", "").removeprefix("store_")
        oidc = os.environ.get("VERCEL_OIDC_TOKEN", "")
        token = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        if oidc and store:
            token = oidc
        elif token:
            match = re.match(r"vercel_blob_rw_([A-Za-z0-9]+)_", token)
            if not match:
                raise ValueError("Invalid storage credential configuration")
            store = match.group(1)
        else:
            raise ValueError("Private Blob storage is not configured")
        if not re.fullmatch(r"[A-Za-z0-9]+", store):
            raise ValueError("Invalid private store identifier")
        self.store = store
        self.headers = {"Authorization": "Bearer " + token, "x-vercel-blob-store-id": store}
        self.transport = transport

    async def read(self, path: str) -> tuple[Optional[bytes], Optional[str]]:
        """Bypass the CDN so the ETag and bytes describe the same origin version."""
        async with httpx.AsyncClient(timeout=25, transport=self.transport) as client:
            response = await client.get(
                f"https://{self.store}.private.blob.vercel-storage.com/{path}",
                params={"cache": "0"},
                headers=self.headers,
            )
        if response.status_code == 404:
            return None, None
        response.raise_for_status()
        if len(response.content) > 64 * 1024 * 1024 or not response.content.startswith(
            b"SQLite format 3\x00"
        ):
            raise ValueError("Invalid workspace snapshot")
        etag = response.headers.get("etag")
        if not etag:
            raise ValueError("Storage omitted the concurrency token")
        return response.content, etag

    async def write(self, path: str, content: bytes, etag: Optional[str]) -> None:
        """Create once or compare-and-swap; a conflict never overwrites history."""
        headers = {
            **self.headers,
            "x-api-version": "13",
            "x-vercel-blob-access": "private",
            "x-content-type": "application/vnd.sqlite3",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1" if etag else "0",
            "x-cache-control-max-age": "0",
        }
        if etag:
            headers["x-if-match"] = etag
        async with httpx.AsyncClient(timeout=25, transport=self.transport) as client:
            response = await client.put(
                "https://vercel.com/api/blob/", params={"pathname": path}, headers=headers, content=content
            )
        if response.status_code in (409, 412):
            raise SnapshotConflict("Workspace changed during this request")
        response.raise_for_status()
