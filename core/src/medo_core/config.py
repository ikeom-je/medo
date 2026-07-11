"""実行時設定。envでバックエンドを切り替える(既定: local)。"""

import os
from pathlib import Path

from medo_core.storage import FirestoreStorage, LocalJsonStorage, Storage


def get_storage() -> Storage:
    backend = os.environ.get("MEDO_BACKEND", "local")
    if backend == "firestore":
        from google.cloud import firestore

        return FirestoreStorage(firestore.Client())
    root = Path(os.environ.get("MEDO_HOME", str(Path.home() / ".medo")))
    return LocalJsonStorage(root)
