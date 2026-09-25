from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StoredArtifact:
    storage_key: str
    path: Path
    sha256: str | None
    byte_size: int


class LocalArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def physical_path(self, storage_key: str) -> Path:
        self._validate_storage_key(storage_key)
        return self.root / storage_key

    def save_raw_pdf(self, source_path: str | Path) -> StoredArtifact:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(source)
        if source.read_bytes()[:5] != b"%PDF-":
            raise ValueError(f"Not a PDF file: {source}")

        digest = sha256_file(source)
        storage_key = f"raw/pdfs/sha256/{digest[:2]}/{digest}.pdf"
        target = self.physical_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            tmp_target = target.with_suffix(target.suffix + ".partial")
            shutil.copyfile(source, tmp_target)
            tmp_target.replace(target)
        return StoredArtifact(storage_key, target, digest, target.stat().st_size)

    def save_json(self, storage_key: str, payload: Any) -> StoredArtifact:
        target = self.physical_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        target.write_bytes(encoded)
        return StoredArtifact(storage_key, target, sha256_bytes(encoded), len(encoded))

    def save_bytes(self, storage_key: str, payload: bytes) -> StoredArtifact:
        target = self.physical_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return StoredArtifact(storage_key, target, sha256_bytes(payload), len(payload))

    def read_json(self, storage_key: str) -> Any:
        return json.loads(self.physical_path(storage_key).read_text(encoding="utf-8"))

    def exists(self, storage_key: str) -> bool:
        return self.physical_path(storage_key).exists()

    @staticmethod
    def _validate_storage_key(storage_key: str) -> None:
        path = Path(storage_key)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Invalid storage_key: {storage_key}")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
