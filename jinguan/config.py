from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class JinguanConfig:
    database_path: Path
    data_root: Path
    cache_root: Path
    require_data_mount: bool = False

    @classmethod
    def from_env(cls) -> "JinguanConfig":
        database_url = os.getenv("JINGUAN_DATABASE_URL")
        database_path = _sqlite_url_to_path(database_url) if database_url else PROJECT_ROOT / "database" / "jinguan.sqlite3"
        return cls(
            database_path=database_path,
            data_root=Path(os.getenv("JINGUAN_DATA_ROOT", PROJECT_ROOT / "data")),
            cache_root=Path(os.getenv("JINGUAN_CACHE_ROOT", PROJECT_ROOT / ".cache")),
            require_data_mount=os.getenv("JINGUAN_REQUIRE_DATA_MOUNT", "false").lower() == "true",
        )


def _sqlite_url_to_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// database URLs are supported by SQLiteRepository")
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path.startswith("/"):
        return Path(raw_path)
    return (PROJECT_ROOT / raw_path).resolve()
