"""ドキュメントストア抽象。パスはFirestore互換(document=偶数セグメント)。"""

import json
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def get(self, path: str) -> dict | None: ...
    def put(self, path: str, doc: dict) -> None: ...
    def list(self, prefix: str) -> list[str]: ...


class LocalJsonStorage:
    """1ドキュメント=1 JSONファイル。root配下にパス構造をそのまま展開する。"""

    def __init__(self, root: Path):
        self._root = Path(root)

    def _file(self, path: str) -> Path:
        return self._root / f"{path}.json"

    def get(self, path: str) -> dict | None:
        f = self._file(path)
        if not f.exists():
            return None
        return json.loads(f.read_text(encoding="utf-8"))

    def put(self, path: str, doc: dict) -> None:
        f = self._file(path)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self, prefix: str) -> list[str]:
        d = self._root / prefix
        if not d.is_dir():
            return []
        return sorted(f"{prefix}/{f.stem}" for f in d.glob("*.json"))


class FirestoreStorage:
    """google-cloud-firestore クライアントの薄いラッパー。"""

    def __init__(self, client):
        self._client = client

    def get(self, path: str) -> dict | None:
        snap = self._client.document(path).get()
        return snap.to_dict() if snap.exists else None

    def put(self, path: str, doc: dict) -> None:
        self._client.document(path).set(doc)

    def list(self, prefix: str) -> list[str]:
        refs = self._client.collection(prefix).list_documents()
        return [f"{prefix}/{ref.id}" for ref in refs]
