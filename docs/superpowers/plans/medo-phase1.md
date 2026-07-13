# Medo フェーズ1(縦切りMVP)実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 課題ヒアリング→市場ファクト+フェルミ推定→打ち手ミニPRFAQ比較→合意案の完全版PRFAQ(GCPカタログ根拠付き)が Claude Code と agy の両ホストで通る What/Why縦切りMVP(core + 最小ETL + `medo` CLI + Skill 3本)を作る。

**Architecture:** ホスト非依存の `medo_core`(要件・カタログ・生成物・ストレージ)を中心に、`medo` CLI が決定論的な事実と計算を提供し、Skill(ホストLLMが実行する手順書)が生成的な部分を担う。ETLはリリースノートBQ公開データセットとBilling Catalog APIからカタログを更新し、Gemini Flashは構造化専任。

**Tech Stack:** Python 3.12+ / uv workspace / pydantic v2 / typer / pytest / google-cloud-firestore / google-cloud-bigquery / google-cloud-billing / google-genai / PyYAML / Marp(フェーズ2)

## Global Constraints

- Python >= 3.12、パッケージ管理は uv(uv workspace モノレポ)
- pydantic >= 2.7、typer >= 0.12、pytest >= 8
- 数値・ステータス(料金、launch_stage、last_verified)の通り道にLLMを挟まない
- カタログエントリは `sources`(出典URL)必須。出典なしエントリはバリデーションで拒否
- 鮮度契約: `last_verified` が30日超なら `stale: true` を全レスポンスに付与
- ETLはバリデーション通過分のみコミット(壊れた更新で既存カタログを上書きしない)
- CLI失敗時は非ゼロ終了+構造化エラー。推測で補完しない
- ストレージパスは Firestore 互換(document = 偶数セグメント、collection = 奇数セグメント)
- コミットメッセージ末尾に Co-Authored-By: Claude Fable 5 <noreply@anthropic.com> を付ける(セッションのgit規約)
- 日本語UI文言・ドキュメント。コード識別子は英語
- Task 6b以降の着手は PR #11(Task 6 CLI)の dev マージ後
- 契約変更を含むTask(6b: 要件スキーマ、6c/6e: CLI新コマンド、6d: 生成物スキーマ)は git.md の重要度判定により人間レビューを経てマージする
- 実装・テストコード作成はCodex、最終検証(pytest/ruff実行)とコミットはClaude(workflow.md Section 3)
- ファクトは出典必須(market/policy/trend はURL、company は由来表記)。鮮度は180日
- フェルミ計算は ast 制限の四則演算+累乗のみ。LLM・`eval` 不使用

## ファイル構成(フェーズ1で作るもの)

```
medo/
├── pyproject.toml               # uv workspace ルート(pytest/ruff設定)
├── core/
│   ├── pyproject.toml           # medo-core パッケージ
│   ├── src/medo_core/
│   │   ├── __init__.py
│   │   ├── config.py            # バックエンド選択(env: MEDO_BACKEND, MEDO_HOME)
│   │   ├── storage.py           # Storage Protocol + LocalJsonStorage + FirestoreStorage
│   │   ├── requirements.py      # RequirementsDoc + RequirementsStore(バージョン管理・diff)
│   │   ├── catalog.py           # CatalogEntry + CatalogStore(鮮度判定・検索)
│   │   ├── facts.py             # Fact + FactStore(kind別出典検証・180日stale)(Task 6c)
│   │   ├── artifacts.py         # Artifact + ArtifactStore(mini-prfaq/prfaq/fermi、引用ファクト)(Task 6d拡張)
│   │   ├── fermi.py             # フェルミ推定の決定論計算(Task 6e)
│   │   └── status.py            # project_status(): 現在地とnext_stepの決定論導出(Task 6f)
│   └── tests/
│       ├── test_storage.py
│       ├── test_requirements.py
│       ├── test_catalog.py
│       ├── test_facts.py
│       ├── test_artifacts.py
│       ├── test_fermi.py
│       └── test_status.py
├── cli/
│   ├── pyproject.toml           # medo-cli パッケージ(console_script: medo)
│   ├── src/medo_cli/
│   │   ├── __init__.py
│   │   └── main.py              # typer app: requirements / facts / fermi / catalog / artifacts / status / etl
│   └── tests/test_cli.py
├── etl/
│   ├── pyproject.toml           # medo-etl パッケージ
│   ├── services.yaml            # 対象サービスリスト(AI/ML重点)
│   ├── src/medo_etl/
│   │   ├── __init__.py
│   │   ├── release_notes.py     # BQ公開データセットからの取得
│   │   ├── structure.py         # Gemini Flashによる構造化(注入可能なgenerate関数)
│   │   ├── skus.py              # Billing Catalog APIからのSKUスナップショット
│   │   └── pipeline.py          # 取得→構造化→バリデーション→upsert→差分レポート
│   └── tests/
│       ├── test_release_notes.py
│       ├── test_structure.py
│       ├── test_skus.py
│       └── test_pipeline.py
└── skills/
    ├── src/
    │   ├── hearing.md           # 業界・課題・経営思想/方針の構造化(共通md、frontmatter付き)
    │   ├── propose-options.md   # 市場ファクト+フェルミ+カタログ根拠→打ち手ミニPRFAQ候補セット
    │   └── grow-prfaq.md        # 合意案を完全版PRFAQへ育成
    ├── build.py                 # dist/claude/<name>/SKILL.md と dist/agy/<name>.md を生成
    └── tests/test_build.py

(docs/usage.md も Task 6b で作成: 人間用の全体フローとステージ/コマンド対応表)
```

**設計メモ(スペックとの対応):**
- カタログの論理IDは `{service}/{feature}` だが、ストレージ上は `catalog/{service}__{feature}`(2セグメント)に平坦化する。Firestoreのコレクション一覧・ローカルのファイル一覧の両方で `list("catalog")` が単純に動くため。
- SKUスナップショットは `sku_snapshots/{service}` に1サービス1ドキュメントで保存(フェーズ2のpricing計算機が消費)。
- 生成物の実体(markdown)はフェーズ1ではドキュメント内にインライン保存(GCSはフェーズ2)。

---

### Task 1: uv workspace モノレポ土台

**Files:**
- Create: `pyproject.toml`(ルート)
- Create: `core/pyproject.toml`, `core/src/medo_core/__init__.py`
- Create: `cli/pyproject.toml`, `cli/src/medo_cli/__init__.py`
- Create: `etl/pyproject.toml`, `etl/src/medo_etl/__init__.py`
- Create: `.gitignore`
- Test: `core/tests/test_smoke.py`

**Interfaces:**
- Consumes: なし
- Produces: `medo_core` / `medo_cli` / `medo_etl` パッケージがimport可能な uv workspace。以降の全タスクは `uv run pytest` でテストを実行する

- [x] **Step 1: ルート pyproject.toml を作成**

```toml
[project]
name = "medo-workspace"
version = "0.1.0"
description = "Medo(目処) — Google Cloud上流工程Agent"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["core", "cli", "etl"]

[tool.uv.sources]
medo-core = { workspace = true }

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.5"]

[tool.pytest.ini_options]
testpaths = ["core/tests", "cli/tests", "etl/tests", "skills/tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [x] **Step 2: .gitignore を作成**

```gitignore
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
dist/
skills/dist/
.claude/settings.local.json
```

- [x] **Step 3: core パッケージを作成**

`core/pyproject.toml`:

```toml
[project]
name = "medo-core"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.7",
    "pyyaml>=6",
    "google-cloud-firestore>=2.16",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/medo_core"]
```

`core/src/medo_core/__init__.py`:

```python
"""Medo core: 要件・カタログ・生成物のドメインロジック(決定論層)。"""
```

- [x] **Step 4: cli パッケージを作成**

`cli/pyproject.toml`:

```toml
[project]
name = "medo-cli"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "medo-core",
    "typer>=0.12",
]

[project.scripts]
medo = "medo_cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/medo_cli"]
```

`cli/src/medo_cli/__init__.py`:

```python
"""medo CLI: 事実と計算をホストLLMに提供する決定論的インターフェース。"""
```

- [x] **Step 5: etl パッケージを作成**

`etl/pyproject.toml`:

```toml
[project]
name = "medo-etl"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "medo-core",
    "google-cloud-bigquery>=3.25",
    "google-cloud-billing>=1.13",
    "google-genai>=1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/medo_etl"]
```

`etl/src/medo_etl/__init__.py`:

```python
"""Medo ETL: 公式ソースからカタログを更新する。Gemini Flashは構造化専任。"""
```

- [x] **Step 6: スモークテストを書く**

`core/tests/test_smoke.py`:

```python
def test_packages_importable():
    import medo_core  # noqa: F401
```

- [x] **Step 7: 依存解決とテスト実行**

Run: `cd /home/pi/develop/medo && uv sync --all-packages && uv run pytest core/tests/test_smoke.py -v`
Expected: PASS(1 passed)

- [x] **Step 8: コミット**

```bash
git add pyproject.toml .gitignore core/ cli/ etl/ uv.lock
git commit -m "feat: uv workspaceモノレポ土台(core/cli/etl)"
```

---

### Task 2: Storage(Protocol + ローカルJSON + Firestore)

**Files:**
- Create: `core/src/medo_core/storage.py`
- Create: `core/src/medo_core/config.py`
- Test: `core/tests/test_storage.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `Storage`(Protocol): `get(path: str) -> dict | None` / `put(path: str, doc: dict) -> None` / `list(prefix: str) -> list[str]`(prefixはコレクションパス=奇数セグメント。返り値はドキュメントパスのリスト)
  - `LocalJsonStorage(root: Path)`(テスト・ローカル運用用)
  - `FirestoreStorage(client)`(本番用の薄いラッパー)
  - `get_storage() -> Storage`(env `MEDO_BACKEND=local|firestore`、localの既定rootは `~/.medo`、env `MEDO_HOME` で上書き)

- [x] **Step 1: 失敗するテストを書く**

`core/tests/test_storage.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from medo_core.storage import FirestoreStorage, LocalJsonStorage


def test_local_put_get_roundtrip(tmp_path: Path):
    s = LocalJsonStorage(tmp_path)
    s.put("catalog/vertex-ai__context-caching", {"service": "vertex-ai"})
    assert s.get("catalog/vertex-ai__context-caching") == {"service": "vertex-ai"}


def test_local_get_missing_returns_none(tmp_path: Path):
    s = LocalJsonStorage(tmp_path)
    assert s.get("catalog/nothing") is None


def test_local_list_returns_document_paths(tmp_path: Path):
    s = LocalJsonStorage(tmp_path)
    s.put("catalog/a__x", {"v": 1})
    s.put("catalog/b__y", {"v": 2})
    s.put("projects/p1/requirements/v1", {"v": 3})
    assert sorted(s.list("catalog")) == ["catalog/a__x", "catalog/b__y"]
    assert s.list("projects/p1/requirements") == ["projects/p1/requirements/v1"]
    assert s.list("empty") == []


def test_firestore_storage_delegates_to_client():
    client = MagicMock()
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {"service": "vertex-ai"}
    client.document.return_value.get.return_value = snap
    doc_ref = MagicMock()
    doc_ref.id = "a__x"
    client.collection.return_value.list_documents.return_value = [doc_ref]

    s = FirestoreStorage(client)
    assert s.get("catalog/a__x") == {"service": "vertex-ai"}
    s.put("catalog/a__x", {"service": "v"})
    client.document.return_value.set.assert_called_once_with({"service": "v"})
    assert s.list("catalog") == ["catalog/a__x"]


def test_firestore_get_missing_returns_none():
    client = MagicMock()
    snap = MagicMock()
    snap.exists = False
    client.document.return_value.get.return_value = snap
    assert FirestoreStorage(client).get("catalog/none") is None
```

- [x] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_storage.py -v`
Expected: FAIL(ModuleNotFoundError: medo_core.storage)

- [x] **Step 3: 実装**

`core/src/medo_core/storage.py`:

```python
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
```

`core/src/medo_core/config.py`:

```python
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
```

- [x] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_storage.py -v`
Expected: PASS(5 passed)

- [x] **Step 5: コミット**

```bash
git add core/src/medo_core/storage.py core/src/medo_core/config.py core/tests/test_storage.py
git commit -m "feat(core): Storage抽象とLocalJSON/Firestoreバックエンド"
```

---

### Task 3: 要件ドキュメント(RequirementsDoc + RequirementsStore)

**Files:**
- Create: `core/src/medo_core/requirements.py`
- Test: `core/tests/test_requirements.py`

**Interfaces:**
- Consumes: `Storage`(Task 2)
- Produces:
  - `FunctionalRequirement(text: str, confidence: Literal["confirmed","assumed","open"]="open")`
  - `RequirementsDoc(project, version=1, industry="", goal="", functional=[], non_functional={}, open_questions=[], sources=[])`
  - `RequirementsStore(storage)`:
    - `save(project_id: str, doc: RequirementsDoc) -> int`(versionを自動採番=最新+1で保存し、採番したversionを返す)
    - `get(project_id: str, version: int | None = None) -> RequirementsDoc | None`(None=最新)
    - `latest_version(project_id: str) -> int`(なければ0)
    - `diff(project_id: str) -> dict`(最新2バージョンの差分: `{"from": n-1, "to": n, "functional_added": [...], "functional_removed": [...], "open_questions_added": [...], "open_questions_resolved": [...]}`。バージョンが1つ以下なら `{"from": 0, "to": n, ...空リスト}`)

- [x] **Step 1: 失敗するテストを書く**

`core/tests/test_requirements.py`:

```python
from pathlib import Path

import pytest
from medo_core.requirements import FunctionalRequirement, RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage


@pytest.fixture
def store(tmp_path: Path) -> RequirementsStore:
    return RequirementsStore(LocalJsonStorage(tmp_path))


def _doc(**kw) -> RequirementsDoc:
    base = dict(
        project="yoyaku",
        goal="飲食店の予約システム",
        industry="飲食",
        functional=[FunctionalRequirement(text="ネット予約", confidence="confirmed")],
        open_questions=["ピーク時同時予約数は?"],
    )
    base.update(kw)
    return RequirementsDoc(**base)


def test_save_assigns_incrementing_versions(store: RequirementsStore):
    assert store.save("yoyaku", _doc()) == 1
    assert store.save("yoyaku", _doc()) == 2
    assert store.latest_version("yoyaku") == 2


def test_get_latest_and_specific_version(store: RequirementsStore):
    store.save("yoyaku", _doc(goal="v1のゴール"))
    store.save("yoyaku", _doc(goal="v2のゴール"))
    assert store.get("yoyaku").goal == "v2のゴール"
    assert store.get("yoyaku", version=1).goal == "v1のゴール"
    assert store.get("nashi") is None


def test_confidence_defaults_to_open():
    fr = FunctionalRequirement(text="通知機能")
    assert fr.confidence == "open"


def test_diff_between_latest_two_versions(store: RequirementsStore):
    store.save(
        "yoyaku",
        _doc(
            functional=[FunctionalRequirement(text="ネット予約")],
            open_questions=["ピーク時同時予約数は?", "多言語対応は?"],
        ),
    )
    store.save(
        "yoyaku",
        _doc(
            functional=[
                FunctionalRequirement(text="ネット予約"),
                FunctionalRequirement(text="LINE通知"),
            ],
            open_questions=["多言語対応は?"],
        ),
    )
    d = store.diff("yoyaku")
    assert d["from"] == 1 and d["to"] == 2
    assert d["functional_added"] == ["LINE通知"]
    assert d["functional_removed"] == []
    assert d["open_questions_resolved"] == ["ピーク時同時予約数は?"]
    assert d["open_questions_added"] == []


def test_diff_with_single_version(store: RequirementsStore):
    store.save("yoyaku", _doc())
    d = store.diff("yoyaku")
    assert d["from"] == 0 and d["to"] == 1
    assert d["functional_added"] == []
```

- [x] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_requirements.py -v`
Expected: FAIL(ModuleNotFoundError: medo_core.requirements)

- [x] **Step 3: 実装**

`core/src/medo_core/requirements.py`:

```python
"""要件ドキュメント(ハブ)。バージョンは保存のたびに自動インクリメント、旧版保持。"""

from typing import Literal

from pydantic import BaseModel, Field

from medo_core.storage import Storage

Confidence = Literal["confirmed", "assumed", "open"]


class FunctionalRequirement(BaseModel):
    text: str
    confidence: Confidence = "open"


class RequirementsDoc(BaseModel):
    project: str
    version: int = 1
    industry: str = ""
    goal: str = ""
    functional: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional: dict[str, str] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class RequirementsStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _path(self, project_id: str, version: int) -> str:
        return f"projects/{project_id}/requirements/v{version}"

    def latest_version(self, project_id: str) -> int:
        paths = self._storage.list(f"projects/{project_id}/requirements")
        versions = [int(p.rsplit("/v", 1)[1]) for p in paths]
        return max(versions, default=0)

    def save(self, project_id: str, doc: RequirementsDoc) -> int:
        version = self.latest_version(project_id) + 1
        doc = doc.model_copy(update={"version": version, "project": project_id})
        self._storage.put(self._path(project_id, version), doc.model_dump(mode="json"))
        return version

    def get(self, project_id: str, version: int | None = None) -> RequirementsDoc | None:
        if version is None:
            version = self.latest_version(project_id)
            if version == 0:
                return None
        raw = self._storage.get(self._path(project_id, version))
        return RequirementsDoc.model_validate(raw) if raw else None

    def diff(self, project_id: str) -> dict:
        to_v = self.latest_version(project_id)
        from_v = to_v - 1 if to_v > 1 else 0
        empty = {
            "from": from_v,
            "to": to_v,
            "functional_added": [],
            "functional_removed": [],
            "open_questions_added": [],
            "open_questions_resolved": [],
        }
        if from_v == 0:
            return empty
        old = self.get(project_id, from_v)
        new = self.get(project_id, to_v)
        old_f = {f.text for f in old.functional}
        new_f = {f.text for f in new.functional}
        old_q = set(old.open_questions)
        new_q = set(new.open_questions)
        empty.update(
            functional_added=sorted(new_f - old_f),
            functional_removed=sorted(old_f - new_f),
            open_questions_added=sorted(new_q - old_q),
            open_questions_resolved=sorted(old_q - new_q),
        )
        return empty
```

- [x] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_requirements.py -v`
Expected: PASS(5 passed)

- [x] **Step 5: コミット**

```bash
git add core/src/medo_core/requirements.py core/tests/test_requirements.py
git commit -m "feat(core): 要件ドキュメントのバージョン管理とdiff"
```

---

### Task 4: カタログ(CatalogEntry + CatalogStore)

**Files:**
- Create: `core/src/medo_core/catalog.py`
- Test: `core/tests/test_catalog.py`

**Interfaces:**
- Consumes: `Storage`(Task 2)
- Produces:
  - `CatalogEntry(service, feature, launch_stage: Literal["GA","Preview","Deprecated"], since: str|None, summary, pricing_refs=[], caveats=[], sources: list[str](1件以上必須), last_verified: str)` — 日付はISO文字列(`YYYY-MM-DD`)
  - `CatalogEntry.entry_id` プロパティ → `"{service}__{feature}"`
  - `CatalogEntry.is_stale(today: date | None = None, threshold_days: int = 30) -> bool`
  - `CatalogStore(storage)`:
    - `upsert(entry: CatalogEntry) -> None`(パス `catalog/{entry_id}`)
    - `get(service: str, feature: str) -> CatalogEntry | None`
    - `search(query: str = "", service: str | None = None, limit: int = 10) -> list[CatalogEntry]`(feature/summary/caveatsの部分一致・大文字小文字無視)

- [x] **Step 1: 失敗するテストを書く**

`core/tests/test_catalog.py`:

```python
from datetime import date
from pathlib import Path

import pytest
from medo_core.catalog import CatalogEntry, CatalogStore
from medo_core.storage import LocalJsonStorage
from pydantic import ValidationError


def _entry(**kw) -> CatalogEntry:
    base = dict(
        service="vertex-ai",
        feature="context-caching",
        launch_stage="GA",
        since="2025-11-01",
        summary="プロンプトの共通部分をキャッシュして入力コストを削減する",
        sources=["https://cloud.google.com/vertex-ai/docs/release-notes"],
        last_verified="2026-07-01",
    )
    base.update(kw)
    return CatalogEntry(**base)


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(LocalJsonStorage(tmp_path))


def test_entry_id():
    assert _entry().entry_id == "vertex-ai__context-caching"


def test_sources_required():
    with pytest.raises(ValidationError):
        _entry(sources=[])


def test_stale_when_older_than_30_days():
    e = _entry(last_verified="2026-05-01")
    assert e.is_stale(today=date(2026, 7, 5)) is True
    assert _entry(last_verified="2026-06-20").is_stale(today=date(2026, 7, 5)) is False


def test_upsert_and_get(store: CatalogStore):
    store.upsert(_entry())
    got = store.get("vertex-ai", "context-caching")
    assert got is not None and got.launch_stage == "GA"
    assert store.get("vertex-ai", "nashi") is None


def test_search_matches_feature_summary_caveats(store: CatalogStore):
    store.upsert(_entry())
    store.upsert(
        _entry(
            feature="batch-prediction",
            summary="バッチ推論",
            caveats=["リージョン制限あり"],
        )
    )
    store.upsert(_entry(service="cloud-run", feature="gpu", summary="GPUサポート"))

    assert [e.feature for e in store.search("caching")] == ["context-caching"]
    assert [e.feature for e in store.search("リージョン")] == ["batch-prediction"]
    assert {e.service for e in store.search("", service="vertex-ai")} == {"vertex-ai"}
    assert len(store.search("")) == 3
    assert len(store.search("", limit=2)) == 2
```

- [x] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_catalog.py -v`
Expected: FAIL(ModuleNotFoundError: medo_core.catalog)

- [x] **Step 3: 実装**

`core/src/medo_core/catalog.py`:

```python
"""鮮度メタデータ付きカタログ。出典必須・金額は焼き込まない(SKU参照のみ)。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from medo_core.storage import Storage

STALE_THRESHOLD_DAYS = 30

LaunchStage = Literal["GA", "Preview", "Deprecated"]


class CatalogEntry(BaseModel):
    service: str
    feature: str
    launch_stage: LaunchStage
    since: str | None = None
    summary: str
    pricing_refs: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    sources: list[str] = Field(min_length=1)
    last_verified: str

    @property
    def entry_id(self) -> str:
        return f"{self.service}__{self.feature}"

    def is_stale(self, today: date | None = None, threshold_days: int = STALE_THRESHOLD_DAYS) -> bool:
        today = today or date.today()
        verified = date.fromisoformat(self.last_verified)
        return (today - verified).days > threshold_days


class CatalogStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def upsert(self, entry: CatalogEntry) -> None:
        self._storage.put(f"catalog/{entry.entry_id}", entry.model_dump(mode="json"))

    def get(self, service: str, feature: str) -> CatalogEntry | None:
        raw = self._storage.get(f"catalog/{service}__{feature}")
        return CatalogEntry.model_validate(raw) if raw else None

    def search(self, query: str = "", service: str | None = None, limit: int = 10) -> list[CatalogEntry]:
        q = query.lower()
        results: list[CatalogEntry] = []
        for path in self._storage.list("catalog"):
            raw = self._storage.get(path)
            entry = CatalogEntry.model_validate(raw)
            if service and entry.service != service:
                continue
            haystack = " ".join([entry.feature, entry.summary, *entry.caveats]).lower()
            if q and q not in haystack:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results
```

- [x] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_catalog.py -v`
Expected: PASS(5 passed)

- [x] **Step 5: コミット**

```bash
git add core/src/medo_core/catalog.py core/tests/test_catalog.py
git commit -m "feat(core): 鮮度判定付きカタログストア"
```

---

### Task 5: 生成物(Artifact + ArtifactStore)

**Files:**
- Create: `core/src/medo_core/artifacts.py`
- Test: `core/tests/test_artifacts.py`

**Interfaces:**
- Consumes: `Storage`(Task 2)、`RequirementsStore.latest_version`(Task 3)
- Produces:
  - `Artifact(project, type: Literal["architecture","slides","mock","comparison"], version=1, requirements_version: int, cited_catalog_entries: list[str]=[], generated_by: Literal["claude","gemini"]|None=None, content: str)`
  - `ArtifactStore(storage)`:
    - `save(project_id: str, artifact: Artifact) -> str`(type別にversion自動採番。保存パス `projects/{id}/artifacts/{type}-v{n}`。返り値は `"{type}-v{n}"`)
    - `get(project_id: str, artifact_id: str) -> Artifact | None`
    - `list(project_id: str) -> list[Artifact]`
    - `stale_artifacts(project_id: str, current_requirements_version: int) -> list[Artifact]`(依存要件バージョンが古いもの)

- [x] **Step 1: 失敗するテストを書く**

`core/tests/test_artifacts.py`:

```python
from pathlib import Path

import pytest
from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.storage import LocalJsonStorage


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(LocalJsonStorage(tmp_path))


def _artifact(**kw) -> Artifact:
    base = dict(
        project="yoyaku",
        type="architecture",
        requirements_version=1,
        cited_catalog_entries=["vertex-ai__context-caching"],
        generated_by="claude",
        content="# アーキ案A\n...",
    )
    base.update(kw)
    return Artifact(**base)


def test_save_assigns_version_per_type(store: ArtifactStore):
    assert store.save("yoyaku", _artifact()) == "architecture-v1"
    assert store.save("yoyaku", _artifact()) == "architecture-v2"
    assert store.save("yoyaku", _artifact(type="slides")) == "slides-v1"


def test_get_and_list(store: ArtifactStore):
    store.save("yoyaku", _artifact())
    got = store.get("yoyaku", "architecture-v1")
    assert got is not None and got.generated_by == "claude"
    assert store.get("yoyaku", "architecture-v9") is None
    assert len(store.list("yoyaku")) == 1
    assert store.list("nashi") == []


def test_stale_artifacts(store: ArtifactStore):
    store.save("yoyaku", _artifact(requirements_version=1))
    store.save("yoyaku", _artifact(requirements_version=2, type="slides"))
    stale = store.stale_artifacts("yoyaku", current_requirements_version=2)
    assert [a.type for a in stale] == ["architecture"]
```

- [x] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_artifacts.py -v`
Expected: FAIL(ModuleNotFoundError: medo_core.artifacts)

- [x] **Step 3: 実装**

`core/src/medo_core/artifacts.py`:

```python
"""生成物。必ず要件バージョンと引用カタログエントリに紐づく(なぜこの提案かを追跡可能)。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from medo_core.storage import Storage

ArtifactType = Literal["architecture", "slides", "mock", "comparison"]


class Artifact(BaseModel):
    project: str
    type: ArtifactType
    version: int = 1
    requirements_version: int
    cited_catalog_entries: list[str] = Field(default_factory=list)
    generated_by: Literal["claude", "gemini"] | None = None
    content: str


class ArtifactStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/artifacts"

    def save(self, project_id: str, artifact: Artifact) -> str:
        existing = [
            p.rsplit("/", 1)[1]
            for p in self._storage.list(self._prefix(project_id))
        ]
        versions = [
            int(name.rsplit("-v", 1)[1])
            for name in existing
            if name.startswith(f"{artifact.type}-v")
        ]
        version = max(versions, default=0) + 1
        artifact = artifact.model_copy(update={"version": version, "project": project_id})
        artifact_id = f"{artifact.type}-v{version}"
        self._storage.put(
            f"{self._prefix(project_id)}/{artifact_id}", artifact.model_dump(mode="json")
        )
        return artifact_id

    def get(self, project_id: str, artifact_id: str) -> Artifact | None:
        raw = self._storage.get(f"{self._prefix(project_id)}/{artifact_id}")
        return Artifact.model_validate(raw) if raw else None

    def list(self, project_id: str) -> list[Artifact]:
        return [
            Artifact.model_validate(self._storage.get(p))
            for p in self._storage.list(self._prefix(project_id))
        ]

    def stale_artifacts(self, project_id: str, current_requirements_version: int) -> list[Artifact]:
        return [
            a for a in self.list(project_id)
            if a.requirements_version < current_requirements_version
        ]
```

- [x] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_artifacts.py -v`
Expected: PASS(3 passed)

- [x] **Step 5: コミット**

```bash
git add core/src/medo_core/artifacts.py core/tests/test_artifacts.py
git commit -m "feat(core): 要件バージョン紐づけ付き生成物ストア"
```

---

### Task 6: medo CLI(requirements / catalog / artifacts)

**Files:**
- Create: `cli/src/medo_cli/main.py`
- Test: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: `get_storage()`(Task 2)、`RequirementsStore`(Task 3)、`CatalogStore`(Task 4)、`ArtifactStore`(Task 5)
- Produces: console script `medo`。Skillが呼ぶコマンド群:
  - `medo requirements save --project <id> --file <yaml>` → `saved: v<n>` を出力
  - `medo requirements get --project <id> [--version n] [--format json|digest]`
  - `medo requirements diff --project <id>`(要件差分+陳腐化した生成物一覧をJSONで出力)
  - `medo catalog search <query> [--service s] [--limit n] [--format json|digest]`(各行/各要素に `stale` フラグ)
  - `medo catalog get <service> <feature> [--format json|digest]`
  - `medo artifacts save --project <id> --type <t> --file <md> --cites a,b [--generated-by claude|gemini] --requirements-version <n>` → `saved: <artifact_id>`
  - `medo artifacts list --project <id>`
  - エラー時: stderrに `error: <理由>`、終了コード1

- [ ] **Step 1: 失敗するテストを書く**

`cli/tests/test_cli.py`:

```python
import json
from pathlib import Path

import pytest
from medo_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


# Medoの実際のユースケース(AI/ML活用によるGCPアーキ提案)をfixtureに反映する。
# 飲食店がインバウンド客の電話予約に対応しきれず、多言語AI音声応対と
# ノーショウ予測でGCPのAI/ML機能を活用したい、という具体案件を想定する。
REQ_YAML = """\
project: yoyaku
goal: 飲食店の多言語対応AI自動音声予約システム
industry: 飲食
functional:
  - text: ネット予約とLINE通知
    confidence: confirmed
  - text: 多言語対応AIエージェントによる電話予約の自動応対・空席照会
    confidence: confirmed
  - text: 過去の予約データに基づくノーショウ(無断キャンセル)確率の事前予測
    confidence: assumed
non_functional:
  performance: 音声応対のレスポンスを2秒以内に抑える
  budget_cap: 月額ランニングコストを低く抑える
open_questions:
  - ピーク時の同時電話着信数は?
  - 既存のPOSシステムや座席管理システムとの連携APIは存在するか?
"""

ENTRY = {
    "service": "vertex-ai",
    "feature": "context-caching",
    "launch_stage": "GA",
    "since": "2025-11-01",
    "summary": "電話応対のシステムプロンプト(店舗情報・予約ルール)をキャッシュし入力コストと応答遅延を削減",
    "pricing_refs": [],
    "caveats": [],
    "sources": ["https://cloud.google.com/vertex-ai/docs/release-notes"],
    "last_verified": "2020-01-01",
}


@pytest.fixture(autouse=True)
def medo_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDO_BACKEND", "local")
    monkeypatch.setenv("MEDO_HOME", str(tmp_path))
    return tmp_path


def _save_requirements(tmp_path: Path) -> None:
    f = tmp_path / "req.yaml"
    f.write_text(REQ_YAML, encoding="utf-8")
    result = runner.invoke(app, ["requirements", "save", "--project", "yoyaku", "--file", str(f)])
    assert result.exit_code == 0, result.output


def test_requirements_save_and_get(medo_home: Path):
    _save_requirements(medo_home)
    result = runner.invoke(app, ["requirements", "get", "--project", "yoyaku", "--format", "json"])
    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["goal"] == "飲食店の多言語対応AI自動音声予約システム" and doc["version"] == 1


def test_requirements_get_missing_project_fails(medo_home: Path):
    result = runner.invoke(app, ["requirements", "get", "--project", "nashi"])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_catalog_search_marks_stale(medo_home: Path):
    from medo_core.catalog import CatalogEntry, CatalogStore
    from medo_core.storage import LocalJsonStorage

    CatalogStore(LocalJsonStorage(medo_home)).upsert(CatalogEntry(**ENTRY))
    result = runner.invoke(app, ["catalog", "search", "caching", "--format", "json"])
    assert result.exit_code == 0
    items = json.loads(result.output)
    assert items[0]["entry"]["feature"] == "context-caching"
    assert items[0]["stale"] is True


def test_catalog_get_digest_and_json_format(medo_home: Path):
    from medo_core.catalog import CatalogEntry, CatalogStore
    from medo_core.storage import LocalJsonStorage

    CatalogStore(LocalJsonStorage(medo_home)).upsert(CatalogEntry(**ENTRY))

    result = runner.invoke(app, ["catalog", "get", "vertex-ai", "context-caching", "--format", "digest"])
    assert result.exit_code == 0
    assert "vertex-ai__context-caching" in result.output
    assert "[STALE]" in result.output

    result = runner.invoke(app, ["catalog", "get", "vertex-ai", "context-caching", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["entry"]["feature"] == "context-caching"


def test_requirements_get_invalid_format_fails(medo_home: Path):
    _save_requirements(medo_home)
    result = runner.invoke(app, ["requirements", "get", "--project", "yoyaku", "--format", "yaml"])
    assert result.exit_code != 0


def test_requirements_save_invalid_yaml_fails(medo_home: Path):
    f = medo_home / "bad.yaml"
    f.write_text("- just\n- a\n- list\n", encoding="utf-8")
    result = runner.invoke(app, ["requirements", "save", "--project", "yoyaku", "--file", str(f)])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_catalog_get_missing_entry_fails(medo_home: Path):
    result = runner.invoke(app, ["catalog", "get", "vertex-ai", "nashi"])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_requirements_diff_missing_project_fails(medo_home: Path):
    result = runner.invoke(app, ["requirements", "diff", "--project", "nashi"])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_artifacts_list_empty_and_after_save(medo_home: Path):
    result = runner.invoke(app, ["artifacts", "list", "--project", "yoyaku"])
    assert result.exit_code == 0
    assert "(生成物なし)" in result.output

    _save_requirements(medo_home)
    arch = medo_home / "arch.md"
    arch.write_text(
        "# 案A: 多言語AI音声予約\n"
        "店舗情報・予約ルールをVertex AI Context Cachingに保持し、"
        "Geminiで多言語音声応対の入力コストと遅延を削減する。\n",
        encoding="utf-8",
    )
    runner.invoke(
        app,
        [
            "artifacts", "save", "--project", "yoyaku", "--type", "architecture",
            "--file", str(arch), "--requirements-version", "1",
        ],
    )
    result = runner.invoke(app, ["artifacts", "list", "--project", "yoyaku"])
    assert result.exit_code == 0
    assert "architecture-v1" in result.output


def test_artifacts_save_and_diff_flow(medo_home: Path):
    _save_requirements(medo_home)
    arch = medo_home / "arch.md"
    arch.write_text(
        "# 案A: 多言語AI音声予約\n"
        "店舗情報・予約ルールをVertex AI Context Cachingに保持し、"
        "Geminiで多言語音声応対の入力コストと遅延を削減する。\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "artifacts", "save", "--project", "yoyaku", "--type", "architecture",
            "--file", str(arch), "--cites", "vertex-ai__context-caching",
            "--generated-by", "claude", "--requirements-version", "1",
        ],
    )
    assert result.exit_code == 0 and "architecture-v1" in result.output

    _save_requirements(medo_home)  # v2を保存 → v1依存のarchitectureが陳腐化
    result = runner.invoke(app, ["requirements", "diff", "--project", "yoyaku"])
    assert result.exit_code == 0
    d = json.loads(result.output)
    assert d["requirements"]["to"] == 2
    assert d["stale_artifacts"] == ["architecture-v1"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_cli.py -v`
Expected: FAIL(ModuleNotFoundError: medo_cli.main)

- [ ] **Step 3: 実装**

`cli/src/medo_cli/main.py`:

```python
"""medo CLI。事実と計算の決定論的インターフェース。失敗時は推測せずエラーを返す。"""

import json
from pathlib import Path
from typing import Literal

import typer
import yaml
from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.catalog import CatalogStore
from medo_core.config import get_storage
from medo_core.requirements import RequirementsDoc, RequirementsStore

app = typer.Typer(no_args_is_help=True, help="Medo(目処) — Google Cloud上流工程Agent CLI")
requirements_app = typer.Typer(no_args_is_help=True)
catalog_app = typer.Typer(no_args_is_help=True)
artifacts_app = typer.Typer(no_args_is_help=True)
app.add_typer(requirements_app, name="requirements", help="要件ドキュメント(バージョン管理)")
app.add_typer(catalog_app, name="catalog", help="鮮度メタ付きカタログ照会")
app.add_typer(artifacts_app, name="artifacts", help="生成物の保存・一覧")


def _fail(reason: str) -> None:
    typer.echo(f"error: {reason}", err=True)
    raise typer.Exit(code=1)


@requirements_app.command("save")
def requirements_save(
    project: str = typer.Option(...),
    file: Path = typer.Option(..., exists=True, readable=True),
):
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("YAMLのトップレベルはマッピングである必要があります")
        doc = RequirementsDoc.model_validate({**data, "project": project})
    except Exception as e:  # yaml.YAMLError, ValueError, pydantic.ValidationError
        _fail(f"要件のスキーマ不正: {e}")
    version = RequirementsStore(get_storage()).save(project, doc)
    typer.echo(f"saved: v{version}")


@requirements_app.command("get")
def requirements_get(
    project: str = typer.Option(...),
    version: int | None = typer.Option(None),
    format: Literal["json", "digest"] = typer.Option("json"),
):
    doc = RequirementsStore(get_storage()).get(project, version)
    if doc is None:
        _fail(f"プロジェクト '{project}' の要件が見つかりません")
    if format == "json":
        typer.echo(json.dumps(doc.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"{doc.project} v{doc.version}: {doc.goal}")
        for f in doc.functional:
            typer.echo(f"  - [{f.confidence}] {f.text}")
        for q in doc.open_questions:
            typer.echo(f"  ? {q}")


@requirements_app.command("diff")
def requirements_diff(project: str = typer.Option(...)):
    storage = get_storage()
    req_store = RequirementsStore(storage)
    current = req_store.latest_version(project)
    if current == 0:
        _fail(f"プロジェクト '{project}' の要件が見つかりません")
    stale = ArtifactStore(storage).stale_artifacts(project, current)
    typer.echo(
        json.dumps(
            {
                "requirements": req_store.diff(project),
                "stale_artifacts": [f"{a.type}-v{a.version}" for a in stale],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _entry_payload(entry) -> dict:
    return {"entry": entry.model_dump(mode="json"), "stale": entry.is_stale()}


@catalog_app.command("search")
def catalog_search(
    query: str = typer.Argument(""),
    service: str | None = typer.Option(None),
    limit: int = typer.Option(10),
    format: Literal["json", "digest"] = typer.Option("digest"),
):
    entries = CatalogStore(get_storage()).search(query, service=service, limit=limit)
    if format == "json":
        typer.echo(json.dumps([_entry_payload(e) for e in entries], ensure_ascii=False, indent=2))
        return
    if not entries:
        typer.echo("(該当なし)")
        return
    for e in entries:
        stale = " [STALE]" if e.is_stale() else ""
        typer.echo(f"{e.entry_id} [{e.launch_stage}]{stale} {e.summary[:60]}")


@catalog_app.command("get")
def catalog_get(
    service: str,
    feature: str,
    format: Literal["json", "digest"] = typer.Option("json"),
):
    entry = CatalogStore(get_storage()).get(service, feature)
    if entry is None:
        _fail(f"カタログに {service}/{feature} が見つかりません")
    if format == "json":
        typer.echo(json.dumps(_entry_payload(entry), ensure_ascii=False, indent=2))
        return
    stale = " [STALE]" if entry.is_stale() else ""
    typer.echo(f"{entry.entry_id} [{entry.launch_stage}]{stale} {entry.summary[:60]}")


@artifacts_app.command("save")
def artifacts_save(
    project: str = typer.Option(...),
    artifact_type: str = typer.Option(..., "--type"),
    file: Path = typer.Option(..., exists=True, readable=True),
    cites: str = typer.Option("", help="引用カタログエントリID(カンマ区切り)"),
    generated_by: str | None = typer.Option(None),
    requirements_version: int = typer.Option(...),
):
    try:
        artifact = Artifact(
            project=project,
            type=artifact_type,
            requirements_version=requirements_version,
            cited_catalog_entries=[c for c in cites.split(",") if c],
            generated_by=generated_by,
            content=file.read_text(encoding="utf-8"),
        )
    except Exception as e:
        _fail(f"生成物のスキーマ不正: {e}")
    artifact_id = ArtifactStore(get_storage()).save(project, artifact)
    typer.echo(f"saved: {artifact_id}")


@artifacts_app.command("list")
def artifacts_list(project: str = typer.Option(...)):
    items = ArtifactStore(get_storage()).list(project)
    for a in items:
        by = f" by {a.generated_by}" if a.generated_by else ""
        typer.echo(f"{a.type}-v{a.version} (req v{a.requirements_version}){by}")
    if not items:
        typer.echo("(生成物なし)")


if __name__ == "__main__":
    app()
```

**設計メモ(実装時のレビューで追加した箇所)**: `--format` は `Literal["json", "digest"]` でtyperのChoiceとして検証し、不正値はUsageエラー(exit 2)で拒否する。`catalog get` は `catalog search` と同じdigest整形を持つ。`requirements save` のYAML読み込みはパース失敗・非マッピング・スキーマ不正のすべてを`try`内で捕捉して`error:`契約を満たす。`artifacts_save` の内部パラメータ名は `artifact_type`(CLIフラグは `--type` のまま)でbuiltin shadowingを避ける。

**テストfixtureの見直し(PR#11レビュー対応)**: 当初のfixtureは「飲食店の予約システム」という汎用プレースホルダーだったが、MedoのAI/ML中心のGCPアーキ提案という価値提案を反映していないという指摘を受け、agyによる設計ドキュメント調査(product.md・medo-design.md)を踏まえ「多言語対応AI自動音声予約(電話応対の自動化・ノーショウ予測)」という、実際にVertex AIのcontext-caching/batch-prediction的な機能が根拠として効くシナリオに更新した(Task 3/5で既に確定した`project: yoyaku`のIDと`vertex-ai__context-caching`エントリは踏襲し、既存テストとの一貫性を保っている)。

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest cli/tests/test_cli.py -v`
Expected: PASS(10 passed。契約の網羅性向上のためcatalog get digest/json・不正format・不正YAML・catalog get未登録・requirements diff未登録・artifacts list空/保存後のテストをレビューで追加)

- [ ] **Step 5: インストール済みコマンドとしての動作確認**

Run: `uv run medo --help`
Expected: `requirements` / `catalog` / `artifacts` サブコマンドが表示される

- [ ] **Step 6: コミット**

```bash
git add cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(cli): medoコマンド(requirements/catalog/artifacts)"
```

---

### Task 6b: 要件スキーマ拡張(background / principles / challenges)

**Files:**
- Modify: `core/src/medo_core/requirements.py`
- Modify: `cli/src/medo_cli/main.py`(requirements get のdigest表示)
- Test: `core/tests/test_requirements.py`(追記)、`cli/tests/test_cli.py`(追記)

**Interfaces:**
- Consumes: 既存 `RequirementsDoc` / `RequirementsStore`(Task 3)
- Produces:
  - `ConfidenceItem(text: str, confidence: Literal["confirmed","assumed","open"]="open")`
  - `FunctionalRequirement(ConfidenceItem)`(後方互換のため名前を維持)
  - `RequirementsDoc` に追加: `background: str=""` / `principles: list[ConfidenceItem]=[]` / `challenges: list[ConfidenceItem]=[]`(全てデフォルト付きのadditive change。既存保存データはそのまま検証を通る)
- **契約変更**: 要件スキーマの拡張のため、PRは人間レビューを経てマージする

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_requirements.py` に追記:

```python
def test_business_context_fields_roundtrip(store: RequirementsStore):
    from medo_core.requirements import ConfidenceItem

    doc = _doc(
        background="インバウンド客の増加と人手不足が同時進行",
        principles=[ConfidenceItem(text="地域の食文化を海外客に開く", confidence="confirmed")],
        challenges=[ConfidenceItem(text="外国語の電話予約に対応できず機会損失")],
    )
    store.save("yoyaku", doc)
    got = store.get("yoyaku")
    assert got.background == "インバウンド客の増加と人手不足が同時進行"
    assert got.principles[0].confidence == "confirmed"
    assert got.challenges[0].confidence == "open"  # 既定はopen


def test_backward_compat_docs_without_new_fields(store: RequirementsStore):
    raw = _doc().model_dump(mode="json")
    for key in ("background", "principles", "challenges"):
        raw.pop(key, None)
    doc = RequirementsDoc.model_validate(raw)
    assert doc.background == "" and doc.principles == [] and doc.challenges == []
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_requirements.py -v`
Expected: FAIL(ImportError: ConfidenceItem / ValidationError)

- [ ] **Step 3: 実装**

`core/src/medo_core/requirements.py` の `FunctionalRequirement` と `RequirementsDoc` を次に変更:

```python
class ConfidenceItem(BaseModel):
    text: str
    confidence: Confidence = "open"


class FunctionalRequirement(ConfidenceItem):
    """機能要件。後方互換のため名前を維持(実体はConfidenceItem)。"""


class RequirementsDoc(BaseModel):
    project: str
    version: int = 1
    industry: str = ""
    background: str = ""  # 業界・ビジネス状況の要約
    goal: str = ""
    principles: list[ConfidenceItem] = Field(default_factory=list)  # 経営思想・理念・方針
    challenges: list[ConfidenceItem] = Field(default_factory=list)  # 課題(What/Whyの起点)
    functional: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional: dict[str, str] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
```

`cli/src/medo_cli/main.py` の `requirements_get` のdigest分岐(`else:`)を次に変更:

```python
    else:
        typer.echo(f"{doc.project} v{doc.version}: {doc.goal}")
        if doc.background:
            typer.echo(f"  背景: {doc.background}")
        for p in doc.principles:
            typer.echo(f"  理念 [{p.confidence}] {p.text}")
        for c in doc.challenges:
            typer.echo(f"  課題 [{c.confidence}] {c.text}")
        for f in doc.functional:
            typer.echo(f"  - [{f.confidence}] {f.text}")
        for q in doc.open_questions:
            typer.echo(f"  ? {q}")
```

`cli/tests/test_cli.py` の `REQ_YAML` に以下を追加し(goal行の直後)、digestテストを追記:

```yaml
background: インバウンド客の増加と人手不足が同時進行
principles:
  - text: 地域の食文化を海外客に開く
    confidence: confirmed
challenges:
  - text: 外国語の電話予約に対応できず機会損失
    confidence: confirmed
```

```python
def test_requirements_get_digest_shows_business_context(medo_home: Path):
    _save_requirements(medo_home)
    result = runner.invoke(app, ["requirements", "get", "--project", "yoyaku", "--format", "digest"])
    assert result.exit_code == 0
    assert "課題 [confirmed] 外国語の電話予約に対応できず機会損失" in result.output
    assert "理念 [confirmed] 地域の食文化を海外客に開く" in result.output
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_requirements.py cli/tests/test_cli.py -v && uv run ruff check .`
Expected: 全件PASS、リント警告なし

- [ ] **Step 5: コミット**

```bash
git add core/src/medo_core/requirements.py core/tests/test_requirements.py cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(core): 要件スキーマにビジネス文脈(背景・理念・課題)を追加"
```

---

### Task 6c: 市場ファクト(Fact + FactStore + CLI facts)

**Files:**
- Create: `core/src/medo_core/facts.py`
- Modify: `cli/src/medo_cli/main.py`(facts サブコマンド追加)
- Test: `core/tests/test_facts.py`、`cli/tests/test_cli.py`(追記)

**Interfaces:**
- Consumes: `Storage`(Task 2)
- Produces:
  - `Fact(fact_id="", kind: Literal["market","policy","trend","company"], statement, value: float|None=None, unit="", source, retrieved, note="")` — source必須。market/policy/trendはURL形式を検証、companyは由来表記
  - `Fact.is_stale(today=None, threshold_days=180) -> bool`
  - `FactStore(storage)`: `save(project_id, fact) -> str`(fact_id空なら `fact-<n>` を自動採番)/ `get(project_id, fact_id) -> Fact|None` / `list(project_id) -> list[Fact]`
  - CLI: `medo facts save --project <id> --kind <k> --statement <s> --source <src> [--value f] [--unit u] [--retrieved YYYY-MM-DD] [--note n]` → `saved: fact-<n>` / `medo facts list --project <id> [--format json|digest]`(stale付き)
- **契約変更**: CLI新コマンドのため、PRは人間レビューを経てマージする

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_facts.py`:

```python
from datetime import date

import pytest
from medo_core.facts import Fact, FactStore
from medo_core.storage import LocalJsonStorage
from pydantic import ValidationError


def _fact(**kw) -> Fact:
    base = dict(
        kind="market",
        statement="訪日外国人旅行者数 3,687万人(2024年)",
        value=36870000.0,
        unit="人",
        source="https://www.jnto.go.jp/statistics/",
        retrieved="2026-07-01",
    )
    base.update(kw)
    return Fact(**base)


def test_market_fact_requires_url_source():
    with pytest.raises(ValidationError):
        _fact(source="ヒアリングで聞いた")


def test_company_fact_accepts_hearing_source():
    f = _fact(kind="company", statement="現在の月間予約数は約1,200件", source="ヒアリング(2026-07-01 顧客X)")
    assert f.kind == "company"


def test_empty_source_rejected():
    with pytest.raises(ValidationError):
        _fact(kind="company", source="   ")


def test_invalid_retrieved_date_rejected():
    with pytest.raises(ValidationError):
        _fact(retrieved="not-a-date")


def test_stale_when_older_than_180_days():
    assert _fact(retrieved="2026-01-01").is_stale(today=date(2026, 7, 12)) is True
    assert _fact(retrieved="2026-02-01").is_stale(today=date(2026, 7, 12)) is False


def test_save_assigns_incrementing_fact_ids(tmp_path):
    store = FactStore(LocalJsonStorage(tmp_path))
    assert store.save("yoyaku", _fact()) == "fact-1"
    assert store.save("yoyaku", _fact(statement="外食単価")) == "fact-2"
    got = store.get("yoyaku", "fact-1")
    assert got is not None and got.value == 36870000.0
    assert len(store.list("yoyaku")) == 2
    assert store.list("nashi") == []
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_facts.py -v`
Expected: FAIL(ModuleNotFoundError: medo_core.facts)

- [ ] **Step 3: 実装**

`core/src/medo_core/facts.py`:

```python
"""市場・国策・業界動向・個社ファクト。出典必須(仮定はファクトにしない=fermi側のassumeのみ)。"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, model_validator

from medo_core.storage import Storage

FACT_STALE_THRESHOLD_DAYS = 180

FactKind = Literal["market", "policy", "trend", "company"]
_URL_KINDS = {"market", "policy", "trend"}


class Fact(BaseModel):
    fact_id: str = ""
    kind: FactKind
    statement: str
    value: float | None = None
    unit: str = ""
    source: str
    retrieved: str  # ISO日付 YYYY-MM-DD
    note: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "Fact":
        if not self.source.strip():
            raise ValueError("source は必須です(出典のないファクトは保存できません)")
        if self.kind in _URL_KINDS:
            parsed = urlparse(self.source)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"kind={self.kind} の source はURLである必要があります")
        try:
            date.fromisoformat(self.retrieved)
        except ValueError as e:
            raise ValueError(f"retrieved はISO日付(YYYY-MM-DD)である必要があります: {e}") from e
        return self

    def is_stale(
        self, today: date | None = None, threshold_days: int = FACT_STALE_THRESHOLD_DAYS
    ) -> bool:
        today = today or date.today()
        return (today - date.fromisoformat(self.retrieved)).days > threshold_days


class FactStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/facts"

    def save(self, project_id: str, fact: Fact) -> str:
        if not fact.fact_id:
            nums = []
            for path in self._storage.list(self._prefix(project_id)):
                m = re.fullmatch(r"fact-(\d+)", path.rsplit("/", 1)[1])
                if m:
                    nums.append(int(m.group(1)))
            fact = fact.model_copy(update={"fact_id": f"fact-{max(nums, default=0) + 1}"})
        self._storage.put(f"{self._prefix(project_id)}/{fact.fact_id}", fact.model_dump(mode="json"))
        return fact.fact_id

    def get(self, project_id: str, fact_id: str) -> Fact | None:
        raw = self._storage.get(f"{self._prefix(project_id)}/{fact_id}")
        return Fact.model_validate(raw) if raw else None

    def list(self, project_id: str) -> list[Fact]:
        return [
            Fact.model_validate(self._storage.get(p))
            for p in self._storage.list(self._prefix(project_id))
        ]
```

`cli/src/medo_cli/main.py` に追記(import に `from datetime import date`・`from medo_core.facts import Fact, FactStore` を追加。`from typing import Literal` が未importの場合はそれも追加):

```python
facts_app = typer.Typer(no_args_is_help=True)
app.add_typer(facts_app, name="facts", help="市場・国策・業界動向・個社ファクト(出典必須)")


@facts_app.command("save")
def facts_save(
    project: str = typer.Option(...),
    kind: str = typer.Option(..., help="market | policy | trend | company"),
    statement: str = typer.Option(...),
    source: str = typer.Option(..., help="market/policy/trendはURL、companyは由来表記"),
    value: float | None = typer.Option(None),
    unit: str = typer.Option(""),
    retrieved: str | None = typer.Option(None, help="取得日 YYYY-MM-DD(省略時は今日)"),
    note: str = typer.Option(""),
):
    try:
        fact = Fact(
            kind=kind,
            statement=statement,
            value=value,
            unit=unit,
            source=source,
            retrieved=retrieved or date.today().isoformat(),
            note=note,
        )
    except Exception as e:
        _fail(f"ファクトのスキーマ不正: {e}")
    fact_id = FactStore(get_storage()).save(project, fact)
    typer.echo(f"saved: {fact_id}")


@facts_app.command("list")
def facts_list(
    project: str = typer.Option(...),
    format: Literal["json", "digest"] = typer.Option("digest"),
):
    facts = FactStore(get_storage()).list(project)
    if format == "json":
        payload = [{"fact": f.model_dump(mode="json"), "stale": f.is_stale()} for f in facts]
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not facts:
        typer.echo("(ファクトなし)")
        return
    for f in facts:
        stale = " [STALE]" if f.is_stale() else ""
        typer.echo(f"{f.fact_id} [{f.kind}]{stale} {f.statement} (出典: {f.source}, {f.retrieved})")
```

`cli/tests/test_cli.py` に追記:

```python
def test_facts_save_and_list_with_stale_flag(medo_home: Path):
    result = runner.invoke(
        app,
        [
            "facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "訪日外国人旅行者数 3,687万人", "--value", "36870000",
            "--unit", "人", "--source", "https://www.jnto.go.jp/statistics/",
            "--retrieved", "2020-01-01",
        ],
    )
    assert result.exit_code == 0 and "fact-1" in result.output

    result = runner.invoke(app, ["facts", "list", "--project", "yoyaku", "--format", "json"])
    items = json.loads(result.output)
    assert items[0]["fact"]["fact_id"] == "fact-1"
    assert items[0]["stale"] is True


def test_facts_save_rejects_non_url_source_for_market(medo_home: Path):
    result = runner.invoke(
        app,
        [
            "facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "x", "--source", "ヒアリングで聞いた",
        ],
    )
    assert result.exit_code == 1
    assert "error:" in result.output
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_facts.py cli/tests/test_cli.py -v && uv run ruff check .`
Expected: 全件PASS、リント警告なし

- [ ] **Step 5: コミット**

```bash
git add core/src/medo_core/facts.py core/tests/test_facts.py cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(core): 出典必須の市場ファクトストア(kind別検証・180日stale)"
```

---

### Task 6d: 生成物スキーマ拡張(mini-prfaq / prfaq / fermi、引用ファクト)

**Files:**
- Modify: `core/src/medo_core/artifacts.py`
- Modify: `cli/src/medo_cli/main.py`(artifacts save のフラグ追加、artifacts get 新設)
- Test: `core/tests/test_artifacts.py`(追記)、`cli/tests/test_cli.py`(追記)

**Interfaces:**
- Consumes: `Storage`(Task 2)
- Produces:
  - `ArtifactType` に `"mini-prfaq" | "prfaq" | "fermi"` を追加
  - `OptionMeta(name: str, approach_type: str="")` / `GrownFrom(artifact: str, option: str)`
  - `Artifact` に追加: `cited_facts: list[str]=[]` / `options: list[OptionMeta]=[]`(mini-prfaq用)/ `grown_from: GrownFrom|None=None`(prfaqは必須。バリデーションで強制)
  - `generated_by`: 生成的な生成物(mini-prfaq / prfaq / architecture / slides / mock / comparison)には `claude|gemini` 必須、`fermi` はコード生成のため `None` 固定(バリデーションで強制)
  - CLI: `medo artifacts save` に `--cites-facts a,b` / `--options "name:approach_type,..."` / `--grown-from "mini-prfaq-vN:打ち手名"` を追加。`medo artifacts get --project <id> --id <artifact_id>`(JSON出力)を新設
- **契約変更**: 生成物スキーマ・CLIの変更のため、PRは人間レビューを経てマージする

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_artifacts.py` に追記:

```python
def test_mini_prfaq_holds_option_set_metadata(store: ArtifactStore):
    from medo_core.artifacts import OptionMeta

    artifact = _artifact(
        type="mini-prfaq",
        options=[
            OptionMeta(name="多言語AI音声予約", approach_type="業務改革"),
            OptionMeta(name="予約代行アウトソース", approach_type="既存解決"),
        ],
        cited_facts=["fact-1"],
    )
    assert store.save("yoyaku", artifact) == "mini-prfaq-v1"
    got = store.get("yoyaku", "mini-prfaq-v1")
    assert [o.name for o in got.options] == ["多言語AI音声予約", "予約代行アウトソース"]
    assert got.cited_facts == ["fact-1"]


def test_prfaq_requires_grown_from(store: ArtifactStore):
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _artifact(type="prfaq")

    from medo_core.artifacts import GrownFrom

    artifact = _artifact(type="prfaq", grown_from=GrownFrom(artifact="mini-prfaq-v1", option="多言語AI音声予約"))
    assert store.save("yoyaku", artifact) == "prfaq-v1"


def test_fermi_artifact_requires_generated_by_none(store: ArtifactStore):
    artifact = _artifact(type="fermi", generated_by=None)
    assert store.save("yoyaku", artifact) == "fermi-v1"

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _artifact(type="fermi", generated_by="claude")


def test_generative_artifact_requires_generated_by(store: ArtifactStore):
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _artifact(type="architecture", generated_by=None)
```

あわせて `cli/tests/test_cli.py` の既存テスト `test_artifacts_list_empty_and_after_save` の `artifacts save` 呼び出しに `"--generated-by", "claude",` を追加する(generated_by必須化のため)。

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_artifacts.py -v`
Expected: FAIL(ValidationError: type / ImportError: OptionMeta)

- [ ] **Step 3: 実装**

`core/src/medo_core/artifacts.py` を次に変更(`model_validator` をpydanticからimport):

```python
ArtifactType = Literal[
    "architecture", "slides", "mock", "comparison", "mini-prfaq", "prfaq", "fermi"
]


class OptionMeta(BaseModel):
    name: str
    approach_type: str = ""


class GrownFrom(BaseModel):
    artifact: str  # 例: "mini-prfaq-v2"
    option: str    # 選択した打ち手名


class Artifact(BaseModel):
    project: str
    type: ArtifactType
    version: int = 1
    requirements_version: int
    cited_catalog_entries: list[str] = Field(default_factory=list)
    cited_facts: list[str] = Field(default_factory=list)
    options: list[OptionMeta] = Field(default_factory=list)  # mini-prfaq: 打ち手候補メタ
    grown_from: GrownFrom | None = None  # prfaq: 育成元
    generated_by: Literal["claude", "gemini"] | None = None  # fermiはコード生成のためNone
    content: str

    @model_validator(mode="after")
    def _validate_type_rules(self) -> "Artifact":
        if self.type == "prfaq" and self.grown_from is None:
            raise ValueError("prfaq には grown_from(育成元のミニPRFAQ候補セットと打ち手)が必須です")
        if self.type == "fermi":
            if self.generated_by is not None:
                raise ValueError("fermi はコードが生成するため generated_by は指定できません")
        elif self.generated_by is None:
            raise ValueError(f"{self.type} には generated_by(claude|gemini)が必須です")
        return self
```

`cli/src/medo_cli/main.py` の `artifacts_save` を次に変更し、`artifacts_get` を追加(importに `OptionMeta, GrownFrom` を追加):

```python
@artifacts_app.command("save")
def artifacts_save(
    project: str = typer.Option(...),
    artifact_type: str = typer.Option(..., "--type"),
    file: Path = typer.Option(..., exists=True, readable=True),
    cites: str = typer.Option("", help="引用カタログエントリID(カンマ区切り)"),
    cites_facts: str = typer.Option("", help="引用ファクトID(カンマ区切り)"),
    options: str = typer.Option("", help="mini-prfaq用: name:approach_type をカンマ区切り"),
    grown_from: str = typer.Option("", help="prfaq用: <mini-prfaq-vN>:<打ち手名>"),
    generated_by: str | None = typer.Option(None),
    requirements_version: int = typer.Option(...),
):
    try:
        option_metas = [
            OptionMeta(name=name, approach_type=approach)
            for name, _, approach in (o.partition(":") for o in options.split(",") if o)
        ]
        gf = None
        if grown_from:
            art, _, opt = grown_from.partition(":")
            gf = GrownFrom(artifact=art, option=opt)
        artifact = Artifact(
            project=project,
            type=artifact_type,
            requirements_version=requirements_version,
            cited_catalog_entries=[c for c in cites.split(",") if c],
            cited_facts=[c for c in cites_facts.split(",") if c],
            options=option_metas,
            grown_from=gf,
            generated_by=generated_by,
            content=file.read_text(encoding="utf-8"),
        )
    except Exception as e:
        _fail(f"生成物のスキーマ不正: {e}")
    artifact_id = ArtifactStore(get_storage()).save(project, artifact)
    typer.echo(f"saved: {artifact_id}")


@artifacts_app.command("get")
def artifacts_get(
    project: str = typer.Option(...),
    id: str = typer.Option(..., "--id", help="例: mini-prfaq-v1"),
):
    artifact = ArtifactStore(get_storage()).get(project, id)
    if artifact is None:
        _fail(f"生成物 {id} が見つかりません")
    typer.echo(json.dumps(artifact.model_dump(mode="json"), ensure_ascii=False, indent=2))
```

`cli/tests/test_cli.py` に追記:

```python
def test_artifacts_save_mini_prfaq_and_get(medo_home: Path):
    _save_requirements(medo_home)
    doc = medo_home / "options.md"
    doc.write_text("# 打ち手候補セット", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "artifacts", "save", "--project", "yoyaku", "--type", "mini-prfaq",
            "--file", str(doc), "--cites-facts", "fact-1",
            "--options", "多言語AI音声予約:業務改革,予約代行:既存解決",
            "--generated-by", "claude", "--requirements-version", "1",
        ],
    )
    assert result.exit_code == 0 and "mini-prfaq-v1" in result.output

    result = runner.invoke(app, ["artifacts", "get", "--project", "yoyaku", "--id", "mini-prfaq-v1"])
    payload = json.loads(result.output)
    assert payload["options"][0]["name"] == "多言語AI音声予約"
    assert payload["cited_facts"] == ["fact-1"]


def test_artifacts_save_prfaq_requires_grown_from(medo_home: Path):
    _save_requirements(medo_home)
    doc = medo_home / "prfaq.md"
    doc.write_text("# PRFAQ", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "artifacts", "save", "--project", "yoyaku", "--type", "prfaq",
            "--file", str(doc), "--generated-by", "claude", "--requirements-version", "1",
        ],
    )
    assert result.exit_code == 1 and "error:" in result.output
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_artifacts.py cli/tests/test_cli.py -v && uv run ruff check .`
Expected: 全件PASS、リント警告なし

- [ ] **Step 5: コミット**

```bash
git add core/src/medo_core/artifacts.py core/tests/test_artifacts.py cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(core): 生成物にmini-prfaq/prfaq/fermiと引用ファクトを追加"
```

---

### Task 6e: フェルミ推定(決定論計算 + CLI fermi)

**Files:**
- Create: `core/src/medo_core/fermi.py`
- Modify: `cli/src/medo_cli/main.py`(fermi サブコマンド追加)
- Test: `core/tests/test_fermi.py`、`cli/tests/test_cli.py`(追記)

**Interfaces:**
- Consumes: `Fact` / `FactStore`(Task 6c)、`Artifact` / `ArtifactStore`(Task 6d)、`RequirementsStore.latest_version`(Task 3)
- Produces:
  - `FermiVar(fact: str|None=None, assume: float|None=None, note="")` — factかassumeのどちらか一方のみ(バリデーション)
  - `FermiModel(name, variables: dict[str, FermiVar], formula: str)`
  - `evaluate(model, facts: dict[str, Fact]) -> FermiResult(name, value, resolved, cited_facts)` — ast制限の四則演算+累乗のみ。未定義変数・許可外構文・ファクト不在・value欠落はValueError
  - CLI: `medo fermi calc --project <id> --file <model.yaml>` → 計算し `type: fermi` 生成物(content=モデル+結果のJSON、cited_facts付き、generated_by=None)として保存、`saved: fermi-v<n>` と結果を出力。`--from-artifact fermi-v<n>` で保存済みモデルからファクトを最新解決して再計算(新バージョン保存)
- **契約変更**: CLI新コマンドのため、PRは人間レビューを経てマージする

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_fermi.py`:

```python
import pytest
from medo_core.facts import Fact
from medo_core.fermi import FermiModel, FermiVar, evaluate
from pydantic import ValidationError


def _fact(**kw) -> Fact:
    base = dict(
        fact_id="fact-1",
        kind="market",
        statement="訪日外国人旅行者数",
        value=36870000.0,
        unit="人",
        source="https://www.jnto.go.jp/statistics/",
        retrieved="2026-07-01",
    )
    base.update(kw)
    return Fact(**base)


def test_evaluate_mixes_facts_and_assumptions():
    model = FermiModel(
        name="多言語予約対応の市場機会",
        variables={
            "visitors": FermiVar(fact="fact-1"),
            "dining_rate": FermiVar(assume=0.8, note="外食利用率の仮定"),
            "unit_price": FermiVar(assume=5000.0),
        },
        formula="visitors * dining_rate * unit_price",
    )
    result = evaluate(model, {"fact-1": _fact()})
    assert result.value == 36870000.0 * 0.8 * 5000.0
    assert result.cited_facts == ["fact-1"]
    assert result.resolved["dining_rate"] == 0.8


def test_power_operator_enables_cagr():
    model = FermiModel(
        name="5年後の市場規模",
        variables={"base": FermiVar(assume=100.0), "growth": FermiVar(assume=1.1)},
        formula="base * growth ** 5",
    )
    assert abs(evaluate(model, {}).value - 100.0 * 1.1**5) < 1e-9


def test_undefined_variable_rejected():
    model = FermiModel(name="x", variables={"a": FermiVar(assume=1.0)}, formula="a + b")
    with pytest.raises(ValueError):
        evaluate(model, {})


def test_huge_exponent_rejected():
    model = FermiModel(
        name="x", variables={"a": FermiVar(assume=10.0)}, formula="a ** 1000000"
    )
    with pytest.raises(ValueError):
        evaluate(model, {})


def test_bool_constant_rejected():
    model = FermiModel(name="x", variables={"a": FermiVar(assume=1.0)}, formula="a + True")
    with pytest.raises(ValueError):
        evaluate(model, {})


def test_disallowed_syntax_rejected():
    model = FermiModel(
        name="x", variables={"a": FermiVar(assume=1.0)}, formula="__import__('os').getcwd()"
    )
    with pytest.raises(ValueError):
        evaluate(model, {})


def test_missing_fact_and_missing_value_rejected():
    model = FermiModel(name="x", variables={"a": FermiVar(fact="fact-9")}, formula="a")
    with pytest.raises(ValueError):
        evaluate(model, {})
    with pytest.raises(ValueError):
        evaluate(FermiModel(name="x", variables={"a": FermiVar(fact="fact-1")}, formula="a"),
                 {"fact-1": _fact(value=None)})


def test_var_requires_exactly_one_of_fact_or_assume():
    with pytest.raises(ValidationError):
        FermiVar(fact="fact-1", assume=1.0)
    with pytest.raises(ValidationError):
        FermiVar()
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_fermi.py -v`
Expected: FAIL(ModuleNotFoundError: medo_core.fermi)

- [ ] **Step 3: 実装**

`core/src/medo_core/fermi.py`:

```python
"""フェルミ推定の決定論計算。仮定は明示、計算はコード(ast制限: 四則演算+累乗)。LLM・eval不使用。"""

from __future__ import annotations

import ast

from pydantic import BaseModel, Field, model_validator

from medo_core.facts import Fact

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
MAX_EXPONENT = 100  # 資源枯渇(巨大数の計算)防止


class FermiVar(BaseModel):
    fact: str | None = None      # ファクトID参照(valueを使う)
    assume: float | None = None  # 明示的仮定
    note: str = ""

    @model_validator(mode="after")
    def _exactly_one(self) -> "FermiVar":
        if (self.fact is None) == (self.assume is None):
            raise ValueError("fact か assume のどちらか一方を指定してください")
        return self


class FermiModel(BaseModel):
    name: str
    variables: dict[str, FermiVar]
    formula: str


class FermiResult(BaseModel):
    name: str
    value: float
    resolved: dict[str, float]
    cited_facts: list[str] = Field(default_factory=list)


def _safe_eval(node: ast.AST, names: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body, names)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in names:
            raise ValueError(f"未定義の変数です: {node.id}")
        return names[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _safe_eval(node.operand, names)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        lhs = _safe_eval(node.left, names)
        rhs = _safe_eval(node.right, names)
        if isinstance(node.op, ast.Add):
            return lhs + rhs
        if isinstance(node.op, ast.Sub):
            return lhs - rhs
        if isinstance(node.op, ast.Mult):
            return lhs * rhs
        if isinstance(node.op, ast.Div):
            return lhs / rhs
        if abs(rhs) > MAX_EXPONENT:
            raise ValueError(f"累乗の指数が大きすぎます(上限{MAX_EXPONENT})")
        return lhs**rhs
    raise ValueError(f"許可されていない式の要素です: {type(node).__name__}")


def evaluate(model: FermiModel, facts: dict[str, Fact]) -> FermiResult:
    resolved: dict[str, float] = {}
    cited: list[str] = []
    for name, var in model.variables.items():
        if var.fact is not None:
            fact = facts.get(var.fact)
            if fact is None:
                raise ValueError(f"参照先ファクトが見つかりません: {var.fact}")
            if fact.value is None:
                raise ValueError(f"ファクト {var.fact} に数値(value)がありません")
            resolved[name] = fact.value
            cited.append(var.fact)
        else:
            resolved[name] = float(var.assume)  # _exactly_oneによりNoneでないことが保証される
    tree = ast.parse(model.formula, mode="eval")
    value = _safe_eval(tree, resolved)
    return FermiResult(name=model.name, value=value, resolved=resolved, cited_facts=cited)
```

`cli/src/medo_cli/main.py` に追記(importに `from medo_core.fermi import FermiModel, evaluate` を追加。`yaml` は既存importを使う):

```python
fermi_app = typer.Typer(no_args_is_help=True)
app.add_typer(fermi_app, name="fermi", help="フェルミ推定(仮定明示・コードが計算)")


@fermi_app.command("calc")
def fermi_calc(
    project: str = typer.Option(...),
    file: Path | None = typer.Option(None, exists=True, readable=True, help="モデルYAML"),
    from_artifact: str | None = typer.Option(None, help="保存済みfermi生成物から再計算(例: fermi-v1)"),
):
    storage = get_storage()
    try:
        if from_artifact and file:
            raise ValueError("--file と --from-artifact は同時に指定できません")
        if from_artifact:
            saved = ArtifactStore(storage).get(project, from_artifact)
            if saved is None:
                raise ValueError(f"生成物 {from_artifact} が見つかりません")
            model = FermiModel.model_validate(json.loads(saved.content)["model"])
        elif file:
            model = FermiModel.model_validate(yaml.safe_load(file.read_text(encoding="utf-8")))
        else:
            raise ValueError("--file か --from-artifact のどちらかを指定してください")
        facts = {f.fact_id: f for f in FactStore(storage).list(project)}
        result = evaluate(model, facts)
    except Exception as e:
        _fail(f"フェルミ計算に失敗: {e}")
    artifact = Artifact(
        project=project,
        type="fermi",
        requirements_version=RequirementsStore(storage).latest_version(project),
        cited_facts=result.cited_facts,
        content=json.dumps(
            {"model": model.model_dump(mode="json"), "result": result.model_dump(mode="json")},
            ensure_ascii=False,
            indent=2,
        ),
    )
    artifact_id = ArtifactStore(storage).save(project, artifact)
    typer.echo(f"saved: {artifact_id}")
    typer.echo(f"{result.name} = {result.value}")
```

`cli/tests/test_cli.py` に追記:

```python
FERMI_YAML = """\
name: 多言語予約対応の市場機会
variables:
  visitors: {fact: fact-1}
  dining_rate: {assume: 0.8}
formula: visitors * dining_rate
"""


def test_fermi_calc_saves_artifact_and_recalcs(medo_home: Path):
    _save_requirements(medo_home)
    runner.invoke(
        app,
        [
            "facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "訪日客数", "--value", "36870000",
            "--source", "https://www.jnto.go.jp/statistics/",
        ],
    )
    model = medo_home / "model.yaml"
    model.write_text(FERMI_YAML, encoding="utf-8")

    result = runner.invoke(app, ["fermi", "calc", "--project", "yoyaku", "--file", str(model)])
    assert result.exit_code == 0, result.output
    assert "fermi-v1" in result.output and "29496000" in result.output

    result = runner.invoke(app, ["fermi", "calc", "--project", "yoyaku", "--from-artifact", "fermi-v1"])
    assert result.exit_code == 0 and "fermi-v2" in result.output


def test_fermi_calc_missing_fact_fails(medo_home: Path):
    _save_requirements(medo_home)
    model = medo_home / "model.yaml"
    model.write_text(FERMI_YAML, encoding="utf-8")
    result = runner.invoke(app, ["fermi", "calc", "--project", "yoyaku", "--file", str(model)])
    assert result.exit_code == 1 and "error:" in result.output
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_fermi.py cli/tests/test_cli.py -v && uv run ruff check .`
Expected: 全件PASS、リント警告なし

- [ ] **Step 5: コミット**

```bash
git add core/src/medo_core/fermi.py core/tests/test_fermi.py cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(core): フェルミ推定の決定論計算と再計算可能なfermi生成物"
```

---

### Task 6f: medo status(現在地の可視化)+ docs/usage.md

**Files:**
- Create: `core/src/medo_core/status.py`
- Create: `docs/usage.md`
- Modify: `cli/src/medo_cli/main.py`(status コマンド追加、requirements diff を引用根拠込みの陳腐化判定に変更)
- Test: `core/tests/test_status.py`、`cli/tests/test_cli.py`(追記)

**Interfaces:**
- Consumes: `RequirementsStore`(Task 3/6b)、`CatalogStore`(Task 4)、`FactStore`(Task 6c)、`ArtifactStore`(Task 6d)
- Produces:
  - `project_status(storage, project_id, today=None) -> dict` — requirements / facts / artifacts(typeごと最新のみ・type昇順)/ next_step を決定論的に返す
  - 陳腐化判定: `requirements_version` が古い、または引用ファクト(180日)・引用カタログエントリ(30日)にstale/欠落がある場合
  - `next_step`(優先順): 要件なし→`"hearing"` / 最新生成物に陳腐化→`"regenerate-stale-artifacts"` / mini-prfaqなし→`"propose-options"` / prfaqなし→`"grow-prfaq"` / それ以外→`"up-to-date"`
  - `stale_artifact_ids(storage, project_id, today=None) -> list[str]`(requirements diff CLIが使用)
  - CLI: `medo status --project <id>` がJSONで現在地を出力(要件未作成はエラーではなく `next_step: "hearing"`)

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_status.py`:

```python
from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore, GrownFrom
from medo_core.catalog import CatalogEntry, CatalogStore
from medo_core.facts import Fact, FactStore
from medo_core.requirements import ConfidenceItem, FunctionalRequirement, RequirementsDoc, RequirementsStore
from medo_core.status import project_status, stale_artifact_ids
from medo_core.storage import LocalJsonStorage

TODAY = date(2026, 7, 12)


def _doc(**kw) -> RequirementsDoc:
    base = dict(
        project="yoyaku",
        goal="飲食店の多言語対応AI自動音声予約システム",
        industry="飲食",
        challenges=[ConfidenceItem(text="外国語の電話予約に対応できず機会損失", confidence="confirmed")],
        functional=[FunctionalRequirement(text="ネット予約", confidence="confirmed")],
        open_questions=["ピーク時の同時電話着信数は?"],
    )
    base.update(kw)
    return RequirementsDoc(**base)


def _mini(**kw) -> Artifact:
    base = dict(
        project="yoyaku", type="mini-prfaq", requirements_version=1,
        generated_by="claude", content="# 候補セット",
    )
    base.update(kw)
    return Artifact(**base)


def _prfaq(**kw) -> Artifact:
    base = dict(
        project="yoyaku",
        type="prfaq",
        requirements_version=1,
        grown_from=GrownFrom(artifact="mini-prfaq-v1", option="多言語AI音声予約"),
        generated_by="claude",
        content="# PRFAQ",
    )
    base.update(kw)
    return Artifact(**base)


def test_no_requirements_suggests_hearing(tmp_path):
    report = project_status(LocalJsonStorage(tmp_path), "yoyaku", today=TODAY)
    assert report["requirements"] is None and report["next_step"] == "hearing"


def test_requirements_only_suggests_propose_options(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    report = project_status(s, "yoyaku", today=TODAY)
    assert report["next_step"] == "propose-options"
    assert report["requirements"]["confidence_counts"]["confirmed"] == 2  # challenges+functional


def test_mini_prfaq_suggests_grow_prfaq(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    ArtifactStore(s).save("yoyaku", _mini())
    assert project_status(s, "yoyaku", today=TODAY)["next_step"] == "grow-prfaq"


def test_prfaq_reaches_up_to_date(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    ArtifactStore(s).save("yoyaku", _mini())
    ArtifactStore(s).save("yoyaku", _prfaq())
    assert project_status(s, "yoyaku", today=TODAY)["next_step"] == "up-to-date"


def test_stale_cited_fact_triggers_regenerate(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    FactStore(s).save("yoyaku", Fact(
        fact_id="fact-1", kind="market", statement="訪日客数", value=1.0,
        source="https://example.com/", retrieved="2025-01-01",
    ))
    ArtifactStore(s).save("yoyaku", _mini(cited_facts=["fact-1"]))
    assert project_status(s, "yoyaku", today=TODAY)["next_step"] == "regenerate-stale-artifacts"
    assert stale_artifact_ids(s, "yoyaku", today=TODAY) == ["mini-prfaq-v1"]


def test_stale_cited_catalog_entry_triggers_regenerate(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    CatalogStore(s).upsert(CatalogEntry(
        service="vertex-ai", feature="context-caching", launch_stage="GA",
        summary="x", sources=["https://cloud.google.com/"], last_verified="2020-01-01",
    ))
    ArtifactStore(s).save("yoyaku", _mini(cited_catalog_entries=["vertex-ai__context-caching"]))
    assert project_status(s, "yoyaku", today=TODAY)["next_step"] == "regenerate-stale-artifacts"


def test_regeneration_recovers_via_latest_per_type(tmp_path):
    s = LocalJsonStorage(tmp_path)
    store = RequirementsStore(s)
    art = ArtifactStore(s)
    store.save("yoyaku", _doc())                       # 要件v1
    art.save("yoyaku", _mini())                        # mini-prfaq-v1
    store.save("yoyaku", _doc(goal="改"))              # 要件v2 → v1候補セットが陳腐化
    assert project_status(s, "yoyaku", today=TODAY)["next_step"] == "regenerate-stale-artifacts"
    art.save("yoyaku", _mini(requirements_version=2))  # 再生成
    assert project_status(s, "yoyaku", today=TODAY)["next_step"] == "grow-prfaq"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_status.py -v`
Expected: FAIL(ModuleNotFoundError: medo_core.status)

- [ ] **Step 3: 実装**

`core/src/medo_core/status.py`:

```python
"""プロジェクトの現在地レポート。保存状態から決定論的に導出し、LLMを挟まない。"""

from __future__ import annotations

from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.catalog import CatalogStore
from medo_core.facts import Fact, FactStore
from medo_core.requirements import RequirementsStore
from medo_core.storage import Storage


def _catalog_entry_stale(store: CatalogStore, entry_id: str, today: date | None) -> bool:
    """引用カタログエントリがstaleまたは欠落ならTrue。"""
    if "__" not in entry_id:
        return True
    service, feature = entry_id.split("__", 1)
    entry = store.get(service, feature)
    return entry is None or entry.is_stale(today=today)


def _artifact_stale(
    artifact: Artifact,
    current_version: int,
    facts_by_id: dict[str, Fact],
    cat_store: CatalogStore,
    today: date | None,
) -> bool:
    if artifact.requirements_version < current_version:
        return True
    for fact_id in artifact.cited_facts:
        fact = facts_by_id.get(fact_id)
        if fact is None or fact.is_stale(today=today):
            return True
    return any(
        _catalog_entry_stale(cat_store, entry_id, today)
        for entry_id in artifact.cited_catalog_entries
    )


def project_status(storage: Storage, project_id: str, today: date | None = None) -> dict:
    req_store = RequirementsStore(storage)
    version = req_store.latest_version(project_id)
    if version == 0:
        return {
            "project": project_id,
            "requirements": None,
            "facts": {"count": 0, "stale": 0},
            "artifacts": [],
            "next_step": "hearing",
        }

    doc = req_store.get(project_id)
    counts = {"confirmed": 0, "assumed": 0, "open": 0}
    for item in [*doc.functional, *doc.principles, *doc.challenges]:
        counts[item.confidence] += 1

    facts = FactStore(storage).list(project_id)
    facts_by_id = {f.fact_id: f for f in facts}
    cat_store = CatalogStore(storage)

    # typeごとの最新バージョンのみを対象にする(旧版のstaleに引きずられて
    # 再生成後も up-to-date に到達できない事態を防ぐ)。type昇順で決定論的に返す
    latest_by_type: dict[str, Artifact] = {}
    for a in ArtifactStore(storage).list(project_id):
        current = latest_by_type.get(a.type)
        if current is None or a.version > current.version:
            latest_by_type[a.type] = a
    artifact_rows = [
        {
            "id": f"{a.type}-v{a.version}",
            "type": a.type,
            "requirements_version": a.requirements_version,
            "stale": _artifact_stale(a, version, facts_by_id, cat_store, today),
        }
        for a in sorted(latest_by_type.values(), key=lambda a: a.type)
    ]

    types = {row["type"] for row in artifact_rows}
    if any(row["stale"] for row in artifact_rows):
        next_step = "regenerate-stale-artifacts"
    elif "mini-prfaq" not in types:
        next_step = "propose-options"
    elif "prfaq" not in types:
        next_step = "grow-prfaq"
    else:
        next_step = "up-to-date"

    return {
        "project": project_id,
        "requirements": {
            "version": version,
            "confidence_counts": counts,
            "open_questions": len(doc.open_questions),
        },
        "facts": {
            "count": len(facts),
            "stale": sum(1 for f in facts if f.is_stale(today=today)),
        },
        "artifacts": artifact_rows,
        "next_step": next_step,
    }


def stale_artifact_ids(storage: Storage, project_id: str, today: date | None = None) -> list[str]:
    report = project_status(storage, project_id, today=today)
    return [row["id"] for row in report["artifacts"] if row["stale"]]
```

`cli/src/medo_cli/main.py` に status コマンドを追加し、`requirements_diff` の陳腐化判定を差し替える(importに `from medo_core.status import project_status, stale_artifact_ids` を追加):

```python
@app.command()
def status(project: str = typer.Option(...)):
    """プロジェクトの現在地(要件・ファクト・生成物・next_step)をJSONで出力する。"""
    report = project_status(get_storage(), project)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
```

```python
@requirements_app.command("diff")
def requirements_diff(project: str = typer.Option(...)):
    storage = get_storage()
    req_store = RequirementsStore(storage)
    current = req_store.latest_version(project)
    if current == 0:
        _fail(f"プロジェクト '{project}' の要件が見つかりません")
    typer.echo(
        json.dumps(
            {
                "requirements": req_store.diff(project),
                "stale_artifacts": stale_artifact_ids(storage, project),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
```

`cli/tests/test_cli.py` に追記:

```python
def test_status_flow_next_steps(medo_home: Path):
    result = runner.invoke(app, ["status", "--project", "yoyaku"])
    assert result.exit_code == 0
    assert json.loads(result.output)["next_step"] == "hearing"

    _save_requirements(medo_home)
    result = runner.invoke(app, ["status", "--project", "yoyaku"])
    assert json.loads(result.output)["next_step"] == "propose-options"
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest -v && uv run ruff check .`
Expected: 全件PASS(既存の `test_artifacts_save_and_diff_flow` も引き続き通る)、リント警告なし

- [ ] **Step 5: docs/usage.md を書く(人間用の全体像)**

`docs/usage.md`:

```markdown
# Medo 使い方ガイド(フェーズ1)

Medoは「ビジネスの打ち手に目処をつける」上流工程を支援する。作業は次のステージを進む:

    課題 ──(medo-hearing)──▶ 要件v1(背景・理念・課題)
      ──(medo-propose-options)──▶ 市場ファクト+フェルミ推定+カタログ根拠
                                   → 打ち手候補のミニPRFAQ候補セット
      ──(比較・Q&A・合意)──▶ (medo-grow-prfaq)──▶ 完全版PRFAQ(How+効果+ロードマップ)
                  ▲                                    │
                  └── 過不足に気づいたら要件・ファクトを更新 ◀──┘
                      → medo status / requirements diff が陳腐化を検出 → 再生成

## 今どこにいるかを知る

    medo status --project <id>

が現在地を返す。`next_step` の意味:

| next_step | 状態 | 次にやること |
|---|---|---|
| `hearing` | 要件が未作成 | ホストで medo-hearing Skill を実行 |
| `propose-options` | 要件はあるが打ち手候補がない | medo-propose-options Skill を実行 |
| `grow-prfaq` | 候補セットはあるが完全版PRFAQがない | 合意した打ち手を medo-grow-prfaq で育成 |
| `regenerate-stale-artifacts` | 要件更新・引用ファクト/カタログの鮮度切れで生成物が陳腐化 | `medo requirements diff` で確認→再生成 |
| `up-to-date` | 最新要件・鮮度に生成物が追従 | フェーズ1のゴール到達(フェーズ2でスライド等に続く) |

## ステージとコマンドの対応

| ステージ | Skill | 主なCLI |
|---|---|---|
| 課題・方針の構造化 | medo-hearing | `medo requirements save/get` |
| 打ち手候補の提案 | medo-propose-options | `medo facts save/list`、`medo fermi calc`、`medo catalog search`、`medo artifacts save --type mini-prfaq` |
| PRFAQ育成 | medo-grow-prfaq | `medo artifacts get`、`medo catalog search`、`medo artifacts save --type prfaq` |
| 見直し | (どこからでも) | `medo requirements diff`、`medo status`、`medo fermi calc --from-artifact` |
```

- [ ] **Step 6: コミット**

```bash
git add core/src/medo_core/status.py core/tests/test_status.py cli/src/medo_cli/main.py cli/tests/test_cli.py docs/usage.md
git commit -m "feat(core): medo status(引用根拠込みの陳腐化判定とnext_step導出)"
```

---

### Task 7: ETL — リリースノート取得とGemini構造化

**Files:**
- Create: `etl/src/medo_etl/release_notes.py`
- Create: `etl/src/medo_etl/structure.py`
- Create: `etl/services.yaml`
- Test: `etl/tests/test_release_notes.py`, `etl/tests/test_structure.py`

**Interfaces:**
- Consumes: `CatalogEntry`(Task 4)
- Produces:
  - `ReleaseNote(product_name: str, description: str, release_note_type: str, published_at: str)`
  - `fetch_release_notes(bq_client, product_names: list[str], since: str) -> list[ReleaseNote]`
  - `load_services(path: Path) -> list[ServiceConfig]`(`ServiceConfig(slug, product_name, release_notes_url)`)
  - `structure_notes(service: ServiceConfig, notes: list[ReleaseNote], generate: Callable[[str], str], today: str) -> tuple[list[CatalogEntry], list[str]]` — `generate` はプロンプト→JSON文字列を返す注入可能関数(本番はGemini Flash)。返り値は(検証通過エントリ, 検証エラーメッセージ)。**LLM出力は必ずpydanticで検証し、通過分のみ返す**

- [ ] **Step 1: services.yaml を作成**

`etl/services.yaml`:

```yaml
# カタログ対象サービス。AI/ML重点+アプリ構築定番。
services:
  - slug: vertex-ai
    product_name: "Vertex AI"
    release_notes_url: "https://cloud.google.com/vertex-ai/docs/release-notes"
  - slug: gemini-api
    product_name: "Gemini API"
    release_notes_url: "https://ai.google.dev/gemini-api/docs/changelog"
  - slug: cloud-run
    product_name: "Cloud Run"
    release_notes_url: "https://cloud.google.com/run/docs/release-notes"
  - slug: cloud-functions
    product_name: "Cloud Functions"
    release_notes_url: "https://cloud.google.com/functions/docs/release-notes"
  - slug: bigquery
    product_name: "BigQuery"
    release_notes_url: "https://cloud.google.com/bigquery/docs/release-notes"
  - slug: firestore
    product_name: "Firestore"
    release_notes_url: "https://cloud.google.com/firestore/docs/release-notes"
```

- [ ] **Step 2: 失敗するテストを書く(release_notes)**

`etl/tests/test_release_notes.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from medo_etl.release_notes import ReleaseNote, fetch_release_notes, load_services


def test_load_services():
    services = load_services(Path(__file__).parent.parent / "services.yaml")
    slugs = [s.slug for s in services]
    assert "vertex-ai" in slugs and "cloud-run" in slugs
    va = next(s for s in services if s.slug == "vertex-ai")
    assert va.product_name == "Vertex AI"
    assert va.release_notes_url.startswith("https://")


def test_fetch_release_notes_builds_query_and_maps_rows():
    row = MagicMock()
    row.product_name = "Vertex AI"
    row.description = "Context caching is GA."
    row.release_note_type = "FEATURE"
    row.published_at = __import__("datetime").date(2026, 6, 20)
    bq = MagicMock()
    bq.query.return_value.result.return_value = [row]

    notes = fetch_release_notes(bq, ["Vertex AI"], since="2026-06-01")
    assert notes == [
        ReleaseNote(
            product_name="Vertex AI",
            description="Context caching is GA.",
            release_note_type="FEATURE",
            published_at="2026-06-20",
        )
    ]
    sql = bq.query.call_args.args[0]
    assert "bigquery-public-data.google_cloud_release_notes.release_notes" in sql
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `uv run pytest etl/tests/test_release_notes.py -v`
Expected: FAIL(ModuleNotFoundError: medo_etl.release_notes)

- [ ] **Step 4: release_notes を実装**

`etl/src/medo_etl/release_notes.py`:

```python
"""リリースノートの決定論的取得(BigQuery公開データセット)。"""

from pathlib import Path

import yaml
from pydantic import BaseModel


class ReleaseNote(BaseModel):
    product_name: str
    description: str
    release_note_type: str
    published_at: str  # YYYY-MM-DD


class ServiceConfig(BaseModel):
    slug: str
    product_name: str
    release_notes_url: str


def load_services(path: Path) -> list[ServiceConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [ServiceConfig.model_validate(s) for s in data["services"]]


QUERY = """
SELECT product_name, description, release_note_type, published_at
FROM `bigquery-public-data.google_cloud_release_notes.release_notes`
WHERE product_name IN UNNEST(@products)
  AND published_at >= @since
ORDER BY published_at DESC
"""


def fetch_release_notes(bq_client, product_names: list[str], since: str) -> list[ReleaseNote]:
    from google.cloud import bigquery

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("products", "STRING", product_names),
            bigquery.ScalarQueryParameter("since", "DATE", since),
        ]
    )
    rows = bq_client.query(QUERY, job_config=job_config).result()
    return [
        ReleaseNote(
            product_name=row.product_name,
            description=row.description,
            release_note_type=row.release_note_type,
            published_at=row.published_at.isoformat(),
        )
        for row in rows
    ]
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run pytest etl/tests/test_release_notes.py -v`
Expected: PASS(2 passed)

- [ ] **Step 6: 失敗するテストを書く(structure)**

`etl/tests/test_structure.py`:

```python
import json

from medo_etl.release_notes import ReleaseNote, ServiceConfig
from medo_etl.structure import structure_notes

SERVICE = ServiceConfig(
    slug="vertex-ai",
    product_name="Vertex AI",
    release_notes_url="https://cloud.google.com/vertex-ai/docs/release-notes",
)

NOTES = [
    ReleaseNote(
        product_name="Vertex AI",
        description="Context caching is now GA.",
        release_note_type="FEATURE",
        published_at="2026-06-20",
    )
]


def _fake_generate(valid: list[dict]):
    def generate(prompt: str) -> str:
        assert "Context caching" in prompt  # ノート本文がプロンプトに含まれる
        return json.dumps(valid)

    return generate


def test_structure_notes_returns_validated_entries():
    generate = _fake_generate(
        [
            {
                "feature": "context-caching",
                "launch_stage": "GA",
                "since": "2026-06-20",
                "summary": "コンテキストキャッシュがGA",
                "caveats": [],
            }
        ]
    )
    entries, errors = structure_notes(SERVICE, NOTES, generate, today="2026-07-05")
    assert errors == []
    assert len(entries) == 1
    e = entries[0]
    assert e.service == "vertex-ai"
    assert e.launch_stage == "GA"
    assert e.last_verified == "2026-07-05"
    assert e.sources == ["https://cloud.google.com/vertex-ai/docs/release-notes"]


def test_structure_notes_rejects_invalid_items_but_keeps_valid():
    generate = _fake_generate(
        [
            {"feature": "ok-feature", "launch_stage": "Preview", "summary": "ok", "caveats": []},
            {"feature": "bad-feature", "launch_stage": "不正な値", "summary": "ng", "caveats": []},
        ]
    )
    entries, errors = structure_notes(SERVICE, NOTES, generate, today="2026-07-05")
    assert [e.feature for e in entries] == ["ok-feature"]
    assert len(errors) == 1 and "bad-feature" in errors[0]


def test_structure_notes_rejects_broken_json():
    entries, errors = structure_notes(SERVICE, NOTES, lambda p: "not json", today="2026-07-05")
    assert entries == [] and len(errors) == 1
```

- [ ] **Step 7: テストが失敗することを確認**

Run: `uv run pytest etl/tests/test_structure.py -v`
Expected: FAIL(ModuleNotFoundError: medo_etl.structure)

- [ ] **Step 8: structure を実装**

`etl/src/medo_etl/structure.py`:

```python
"""Gemini Flashによる構造化(生成的だが出典・検証必須)。generate関数は注入可能。"""

import json
from typing import Callable

from medo_core.catalog import CatalogEntry
from medo_etl.release_notes import ReleaseNote, ServiceConfig

PROMPT_TEMPLATE = """\
あなたはGoogle Cloudのリリースノートを機能カタログに構造化する係です。
以下のリリースノート群から、アーキテクチャ検討に有用な「機能」単位のエントリを抽出し、
JSON配列のみを出力してください。各要素のスキーマ:
{{"feature": "kebab-case-slug", "launch_stage": "GA|Preview|Deprecated",
  "since": "YYYY-MM-DD または null", "summary": "日本語で1〜2文", "caveats": ["注意点", ...]}}

規則:
- launch_stageはノート本文の記述(GA/generally available/Preview/deprecated)から判定する
- 判定できない情報は捏造せず、その項目を出力しない
- 修正のみのノート(FIX)はスキップしてよい

対象サービス: {product_name}

リリースノート:
{notes}
"""


def structure_notes(
    service: ServiceConfig,
    notes: list[ReleaseNote],
    generate: Callable[[str], str],
    today: str,
) -> tuple[list[CatalogEntry], list[str]]:
    notes_text = "\n".join(
        f"- [{n.release_note_type}] ({n.published_at}) {n.description}" for n in notes
    )
    prompt = PROMPT_TEMPLATE.format(product_name=service.product_name, notes=notes_text)
    raw = generate(prompt)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        return [], [f"{service.slug}: LLM出力がJSONとして不正: {e}"]

    entries: list[CatalogEntry] = []
    errors: list[str] = []
    for item in items:
        try:
            entries.append(
                CatalogEntry(
                    service=service.slug,
                    feature=item.get("feature", ""),
                    launch_stage=item.get("launch_stage"),
                    since=item.get("since"),
                    summary=item.get("summary", ""),
                    caveats=item.get("caveats", []),
                    sources=[service.release_notes_url],
                    last_verified=today,
                )
            )
        except Exception as e:  # pydantic.ValidationError
            errors.append(f"{service.slug}/{item.get('feature', '?')}: 検証エラー: {e}")
    return entries, errors


def gemini_generate(model: str = "gemini-flash-latest") -> Callable[[str], str]:
    """本番用generate。google-genaiクライアントを遅延生成する。"""
    from google import genai

    client = genai.Client()

    def generate(prompt: str) -> str:
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return resp.text

    return generate
```

- [ ] **Step 9: テストが通ることを確認**

Run: `uv run pytest etl/tests/test_structure.py -v`
Expected: PASS(3 passed)

- [ ] **Step 10: コミット**

```bash
git add etl/services.yaml etl/src/medo_etl/release_notes.py etl/src/medo_etl/structure.py etl/tests/test_release_notes.py etl/tests/test_structure.py
git commit -m "feat(etl): リリースノート取得とGemini構造化(検証必須・注入可能)"
```

---

### Task 8: ETL — SKUスナップショットとパイプライン+CLI統合

**Files:**
- Create: `etl/src/medo_etl/skus.py`
- Create: `etl/src/medo_etl/pipeline.py`
- Modify: `cli/src/medo_cli/main.py`(etlサブコマンド追加。`app.add_typer(etl_app, name="etl", ...)` を既存のadd_typer群の直後に追加)
- Modify: `cli/pyproject.toml`(dependenciesに `"medo-etl"` を追加し、ルート `pyproject.toml` の `[tool.uv.sources]` に `medo-etl = { workspace = true }` を追加)
- Test: `etl/tests/test_skus.py`, `etl/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `fetch_release_notes` / `structure_notes` / `load_services`(Task 7)、`CatalogStore`(Task 4)、`Storage`(Task 2)
- Produces:
  - `fetch_skus(billing_client, service_display_name: str) -> list[dict]`(各dict: `{"sku_id", "description", "category"}`)
  - `save_sku_snapshot(storage, service_slug: str, skus: list[dict], fetched_at: str) -> None`(パス `sku_snapshots/{service_slug}`)
  - `run_pipeline(storage, services, notes_by_service: dict[str, list[ReleaseNote]], generate, today: str, dry_run: bool) -> PipelineReport`(`PipelineReport(upserted: list[str], errors: list[str], skipped: int)`)
  - CLI: `medo etl run --since YYYY-MM-DD [--services slug,slug] [--dry-run]` / `medo etl skus --service <slug>`

- [ ] **Step 1: 失敗するテストを書く(skus)**

`etl/tests/test_skus.py`:

```python
from unittest.mock import MagicMock

from medo_core.storage import LocalJsonStorage
from medo_etl.skus import fetch_skus, save_sku_snapshot


def _sku(sku_id: str, desc: str) -> MagicMock:
    m = MagicMock()
    m.sku_id = sku_id
    m.description = desc
    m.category.resource_family = "AI"
    return m


def test_fetch_skus_finds_service_and_lists_skus():
    svc = MagicMock()
    svc.display_name = "Vertex AI"
    svc.name = "services/ABC-123"
    billing = MagicMock()
    billing.list_services.return_value = [svc]
    billing.list_skus.return_value = [_sku("0001-AAAA", "Gemini Flash input tokens")]

    skus = fetch_skus(billing, "Vertex AI")
    assert skus == [
        {"sku_id": "0001-AAAA", "description": "Gemini Flash input tokens", "category": "AI"}
    ]
    billing.list_skus.assert_called_once_with(parent="services/ABC-123")


def test_fetch_skus_unknown_service_raises():
    billing = MagicMock()
    billing.list_services.return_value = []
    try:
        fetch_skus(billing, "Nashi Service")
        raise AssertionError("should raise")
    except ValueError as e:
        assert "Nashi Service" in str(e)


def test_save_sku_snapshot(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    save_sku_snapshot(storage, "vertex-ai", [{"sku_id": "x", "description": "d", "category": "AI"}], "2026-07-05")
    doc = storage.get("sku_snapshots/vertex-ai")
    assert doc["fetched_at"] == "2026-07-05" and len(doc["skus"]) == 1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest etl/tests/test_skus.py -v`
Expected: FAIL(ModuleNotFoundError: medo_etl.skus)

- [ ] **Step 3: skus を実装**

`etl/src/medo_etl/skus.py`:

```python
"""Billing Catalog APIからのSKUスナップショット。金額はカタログに焼き込まず、ここに保存する。"""

from medo_core.storage import Storage


def fetch_skus(billing_client, service_display_name: str) -> list[dict]:
    service_name = None
    for svc in billing_client.list_services():
        if svc.display_name == service_display_name:
            service_name = svc.name
            break
    if service_name is None:
        raise ValueError(f"Billing Catalogにサービスが見つかりません: {service_display_name}")
    return [
        {
            "sku_id": sku.sku_id,
            "description": sku.description,
            "category": sku.category.resource_family,
        }
        for sku in billing_client.list_skus(parent=service_name)
    ]


def save_sku_snapshot(storage: Storage, service_slug: str, skus: list[dict], fetched_at: str) -> None:
    storage.put(
        f"sku_snapshots/{service_slug}",
        {"service": service_slug, "fetched_at": fetched_at, "skus": skus},
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest etl/tests/test_skus.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: 失敗するテストを書く(pipeline)**

`etl/tests/test_pipeline.py`:

```python
import json

from medo_core.catalog import CatalogStore
from medo_core.storage import LocalJsonStorage
from medo_etl.release_notes import ReleaseNote, ServiceConfig
from medo_etl.pipeline import run_pipeline

SERVICE = ServiceConfig(
    slug="vertex-ai",
    product_name="Vertex AI",
    release_notes_url="https://cloud.google.com/vertex-ai/docs/release-notes",
)

NOTES = {
    "vertex-ai": [
        ReleaseNote(
            product_name="Vertex AI",
            description="Context caching is now GA.",
            release_note_type="FEATURE",
            published_at="2026-06-20",
        )
    ]
}


def _generate(prompt: str) -> str:
    return json.dumps(
        [{"feature": "context-caching", "launch_stage": "GA", "summary": "GAになった", "caveats": []}]
    )


def test_pipeline_upserts_validated_entries(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    report = run_pipeline(storage, [SERVICE], NOTES, _generate, today="2026-07-05", dry_run=False)
    assert report.upserted == ["vertex-ai__context-caching"]
    assert report.errors == []
    assert CatalogStore(storage).get("vertex-ai", "context-caching") is not None


def test_pipeline_dry_run_does_not_write(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    report = run_pipeline(storage, [SERVICE], NOTES, _generate, today="2026-07-05", dry_run=True)
    assert report.upserted == ["vertex-ai__context-caching"]
    assert CatalogStore(storage).get("vertex-ai", "context-caching") is None


def test_pipeline_collects_errors_without_aborting(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    report = run_pipeline(
        storage, [SERVICE], NOTES, lambda p: "not json", today="2026-07-05", dry_run=False
    )
    assert report.upserted == [] and len(report.errors) == 1
```

- [ ] **Step 6: テストが失敗することを確認**

Run: `uv run pytest etl/tests/test_pipeline.py -v`
Expected: FAIL(ModuleNotFoundError: medo_etl.pipeline)

- [ ] **Step 7: pipeline を実装**

`etl/src/medo_etl/pipeline.py`:

```python
"""取得→構造化→検証→upsert。検証通過分のみコミットし、エラーはレポートに集約する。"""

from typing import Callable

from pydantic import BaseModel, Field

from medo_core.catalog import CatalogStore
from medo_core.storage import Storage
from medo_etl.release_notes import ReleaseNote, ServiceConfig
from medo_etl.structure import structure_notes


class PipelineReport(BaseModel):
    upserted: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    skipped: int = 0


def run_pipeline(
    storage: Storage,
    services: list[ServiceConfig],
    notes_by_service: dict[str, list[ReleaseNote]],
    generate: Callable[[str], str],
    today: str,
    dry_run: bool,
) -> PipelineReport:
    report = PipelineReport()
    catalog = CatalogStore(storage)
    for service in services:
        notes = notes_by_service.get(service.slug, [])
        if not notes:
            report.skipped += 1
            continue
        entries, errors = structure_notes(service, notes, generate, today)
        report.errors.extend(errors)
        for entry in entries:
            if not dry_run:
                catalog.upsert(entry)
            report.upserted.append(entry.entry_id)
    return report
```

- [ ] **Step 8: テストが通ることを確認**

Run: `uv run pytest etl/tests/test_pipeline.py -v`
Expected: PASS(3 passed)

- [ ] **Step 9: CLIにetlサブコマンドを追加**

`cli/pyproject.toml` の dependencies を修正:

```toml
dependencies = [
    "medo-core",
    "medo-etl",
    "typer>=0.12",
]
```

ルート `pyproject.toml` の `[tool.uv.sources]` を修正:

```toml
[tool.uv.sources]
medo-core = { workspace = true }
medo-etl = { workspace = true }
```

`cli/src/medo_cli/main.py` に追加(既存の `app.add_typer(...)` 群の直後):

```python
etl_app = typer.Typer(no_args_is_help=True)
app.add_typer(etl_app, name="etl", help="カタログ更新パイプライン(手動実行)")


@etl_app.command("run")
def etl_run(
    since: str = typer.Option(..., help="この日付以降のリリースノートを対象(YYYY-MM-DD)"),
    services: str = typer.Option("", help="対象サービスslug(カンマ区切り。空なら全件)"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    from datetime import date
    from pathlib import Path as P

    from medo_etl.pipeline import run_pipeline
    from medo_etl.release_notes import fetch_release_notes, load_services
    from medo_etl.structure import gemini_generate

    from google.cloud import bigquery

    all_services = load_services(P(__file__).parents[3] / "etl" / "services.yaml")
    wanted = [s for s in services.split(",") if s]
    targets = [s for s in all_services if not wanted or s.slug in wanted]
    if not targets:
        _fail(f"対象サービスがありません: {services}")

    bq = bigquery.Client()
    notes_by_service = {}
    for svc in targets:
        notes = fetch_release_notes(bq, [svc.product_name], since=since)
        notes_by_service[svc.slug] = notes

    report = run_pipeline(
        get_storage(), targets, notes_by_service,
        gemini_generate(), today=date.today().isoformat(), dry_run=dry_run,
    )
    typer.echo(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    if report.errors:
        raise typer.Exit(code=1)


@etl_app.command("skus")
def etl_skus(service: str = typer.Option(..., help="サービスslug(services.yaml準拠)")):
    from datetime import date
    from pathlib import Path as P

    from google.cloud import billing_v1
    from medo_etl.release_notes import load_services
    from medo_etl.skus import fetch_skus, save_sku_snapshot

    all_services = load_services(P(__file__).parents[3] / "etl" / "services.yaml")
    target = next((s for s in all_services if s.slug == service), None)
    if target is None:
        _fail(f"services.yamlに未定義のサービス: {service}")
    client = billing_v1.CloudCatalogClient()
    skus = fetch_skus(client, target.product_name)
    save_sku_snapshot(get_storage(), service, skus, fetched_at=date.today().isoformat())
    typer.echo(f"saved: sku_snapshots/{service} ({len(skus)} SKUs)")
```

- [ ] **Step 10: 全テストが通ることを確認**

Run: `uv sync --all-packages && uv run pytest -v`
Expected: PASS(全テスト。etl runコマンド自体の実行はGCP認証が要るため手動スモーク=Task 10で確認)

- [ ] **Step 11: コミット**

```bash
git add etl/src/medo_etl/skus.py etl/src/medo_etl/pipeline.py etl/tests/test_skus.py etl/tests/test_pipeline.py cli/src/medo_cli/main.py cli/pyproject.toml pyproject.toml uv.lock
git commit -m "feat(etl): SKUスナップショットとパイプライン、medo etlコマンド"
```

---

### Task 9: Skill 3本(hearing / propose-options / grow-prfaq)とビルドスクリプト

**Files:**
- Create: `skills/src/hearing.md`
- Create: `skills/src/propose-options.md`
- Create: `skills/src/grow-prfaq.md`
- Create: `skills/build.py`
- Test: `skills/tests/test_build.py`

**Interfaces:**
- Consumes: `medo` CLI のコマンド体系(Task 6・6b〜6f)
- Produces:
  - `skills/dist/claude/<name>/SKILL.md`(Claude Code形式: frontmatter付きそのまま)
  - `skills/dist/agy/<name>.md`(agy/Gemini形式: frontmatter除去。AGENTS.mdから参照)
  - `python skills/build.py` で dist を再生成

- [ ] **Step 1: hearing Skill本文を書く**

`skills/src/hearing.md`:

```markdown
---
name: medo-hearing
description: 業界・ビジネス状況・課題・経営思想/方針をヒアリングとブレストで構造化し、medoの要件ドキュメント(バージョン付き)として保存する。課題も要件も最初から確定しない前提で、confidenceとopen_questionsを育てる。
---

# medo-hearing: 課題と方針を構造化する

あなたは上流工程のビジネス課題整理を支援する。ユーザーの話・ヒアリングメモ・参考資料から、システム要件に直行せず、まず業界・ビジネス状況・課題・経営思想を構造化する。

## 進め方

0. プロジェクトIDが既に決まっている場合は `medo status --project <project-id>` を実行し、現在地(要件バージョン・ファクト・生成物・next_step)をユーザーに報告してから始める。
1. ユーザーの入力を読み、まず理解した内容を1段落で要約して確認する。
2. 次を一つずつ質問して埋める(すでに分かっている項目は聞かない):
   - industry / background: 業界と、そのビジネス状況の要約(市場環境・競合・業務の現状)
   - challenges: 課題(What/Whyの起点)。各項目に confidence を付ける
     - confirmed: ユーザーが明言した / assumed: 文脈からの推定 / open: 要検討
   - principles: 経営思想・理念・方針。**これは検索で調べる事実ではなく、ヒアリングとブレストで引き出して合意する対象**。「何を大切にしたいか」「どんな会社でありたいか」を対話し、ブレストで言語化を手伝い、合意した文言だけを confirmed にする
   - goal: 現時点のやりたいことの一文(打ち手の合意とともに変わってよい)
   - functional / non_functional: 既に見えているシステム要件があれば(薄くてよい。打ち手合意後に育てる)
3. 確認できなかった事項・判断に効く未確定事項は、勝手に埋めずに open_questions に残す。
4. 以下のYAMLを作り、ユーザーに見せて確認を取ってから保存する。

## 保存

要件YAMLを一時ファイル(例: /tmp/req.yaml)に書き、次を実行する:

    medo requirements save --project <project-id> --file /tmp/req.yaml

- project-id はユーザーと合意した英数字slug(例: yoyaku-system)
- 保存後、`saved: v<n>` の出力をユーザーに伝える
- 2回目以降の保存は自動的に新バージョンになる。保存後に `medo requirements diff --project <project-id>` を実行し、差分と陳腐化した生成物を報告する
- 最後に `medo status --project <project-id>` を実行し、現在地と次ステップ(next_step)を報告して終える

## YAMLスキーマ

    project: <slug>
    industry: <業界>
    background: <業界・ビジネス状況の要約>
    goal: <一文>
    principles:
      - text: <経営思想・理念・方針>
        confidence: confirmed | assumed | open
    challenges:
      - text: <課題>
        confidence: confirmed | assumed | open
    functional:
      - text: <機能要件>
        confidence: confirmed | assumed | open
    non_functional:
      performance: <値>
      budget_cap: <値>
    open_questions:
      - <未確定事項>
    sources:
      - <ヒアリングメモや参考URLの出所>

## 契約(必ず守る)

- CLIが失敗したら(非ゼロ終了)、推測で補完せずエラー内容をそのまま報告する
- 開始時(プロジェクトIDが分かる場合)と終了時に `medo status` を実行し、現在地と次ステップを報告する
- ユーザーが言っていないことを confirmed にしない。principles はユーザーが合意した文言だけを書く
- 課題の妥当性への意見(見落とし・深掘りの提案)は述べてよいが、本文はユーザーの合意した内容だけを書く
```

- [ ] **Step 2: propose-options Skill本文を書く**

`skills/src/propose-options.md`:

```markdown
---
name: medo-propose-options
description: 要件ドキュメント(課題・方針)を起点に、市場・国策・業界動向ファクトとフェルミ推定に裏づけられた打ち手候補(2〜3案)を生成し、ミニPRFAQ候補セットとして保存する。事実はCLIが検証・保存した出典付きファクトとカタログ値に縛る。
---

# medo-propose-options: 打ち手候補をミニPRFAQで比較可能にする

要件ドキュメントを入力に、ビジネスの打ち手候補を2〜3案生成する。発想は自由に、事実はファクトとカタログに縛る。

## 進め方

1. 現在地を確認し、ユーザーに報告する:

       medo status --project <project-id>

   `next_step` が `hearing` なら「まず medo-hearing で課題を構造化する」よう案内して終了する。
   続けて最新要件を取得する:

       medo requirements get --project <project-id> --format json

2. 市場・国策・業界動向を検索し(自分の検索能力を使う)、案件の判断に効くファクトを保存する:

       medo facts save --project <project-id> --kind <market|policy|trend> \
         --statement "<出典の記述に忠実な一文>" --value <数値> --unit <単位> \
         --source <出典URL> --retrieved <取得日YYYY-MM-DD>

   - **数値は出典に忠実に転記し、加工しない**(換算・集計が必要ならフェルミ推定で行う)
   - ヒアリング由来の個社情報は `--kind company --source "ヒアリング(<日付> <相手>)"` で保存する
   - 出典のないデータは保存も引用もしない

3. 効果・市場規模の桁感をフェルミ推定で計算する。モデルYAML(variables: fact参照 or assume、formula)を一時ファイルに書き:

       medo fermi calc --project <project-id> --file /tmp/model.yaml

   - 仮定(assume)は明示し、計算は自分でしない(CLIのコードが計算する)
   - 将来予測は policy/trend ファクトを成長率等の根拠に使う

4. Howの目処のためカタログを検索する(複数回実行してよい):

       medo catalog search "<キーワード>" --format json

5. 打ち手候補を2〜3案作る。切り口: **既存の解決 / 破壊的業務改革 / 新規市場開拓** × **スコープ / 立ち位置 / 根本治療vs対症療法**。各案のミニPRFAQに必ず含めること:
   - 打ち手の宣言(顧客に届いた未来のプレスリリース1段落)
   - 価値仮説(What/Why)。**principles(理念・方針)との整合を明記**
   - 効果の桁感(フェルミ推定の生成物IDと結果を引用)
   - Howの目処(カタログ根拠の要点。launch_stageと引用エントリID)
   - 主要リスク・open_questions

6. 全案を1つのmarkdown(候補セット)にまとめて保存する:

       medo artifacts save --project <project-id> --type mini-prfaq \
         --file /tmp/options.md \
         --options "<打ち手名>:<切り口>,<打ち手名>:<切り口>" \
         --cites <entry-id,...> --cites-facts <fact-id,...> \
         --generated-by <claude|gemini> --requirements-version <n>

7. 保存後 `medo status --project <project-id>` を実行し、「候補セットを比較・Q&Aし、合意した打ち手を medo-grow-prfaq で完全版に育てる」ことを案内して終える。

## 契約(必ず守る)

- 引用する市場数値・国策・業界動向は `medo facts` に保存済みの出典付きファクトのみ。launch_stage・GCP機能の有無はカタログ値のみ
- ファクト・カタログに `"stale": true` が付いたものを使う場合、文中に「(情報が古い可能性: <取得日/last_verified>)」と必ず注記する
- フェルミ推定の計算をLLM(自分)で行わない。必ず `medo fermi calc` の結果を使う
- assumed/open の課題・要件に依存する判断には「要確認」の印を付ける
- CLIが失敗したら推測で補完せずエラー内容を報告する
```

- [ ] **Step 3: grow-prfaq Skill本文を書く**

`skills/src/grow-prfaq.md`:

```markdown
---
name: medo-grow-prfaq
description: 合意した打ち手を完全版PRFAQ(技術的背景・workflow改善見込み・効果・ロードマップ付き)に育成して保存する。技術的背景はGCPカタログ根拠に縛り、育成元(grown_from)を記録する。
---

# medo-grow-prfaq: 合意した打ち手を完全版PRFAQに育てる

ミニPRFAQ候補セットから合意された打ち手を、顧客に持ち帰れる完全版PRFAQに育成する。

## 進め方

1. 現在地を確認し、ユーザーに報告する:

       medo status --project <project-id>

   `next_step` が `propose-options` なら「まず medo-propose-options で候補を作る」よう案内して終了する。
2. **どの打ち手に合意したかをユーザーに確認する**(合意はツールの外の意思決定。勝手に選ばない)。
3. 育成元の候補セットと要件を取得する:

       medo artifacts get --project <project-id> --id <mini-prfaq-vN>
       medo requirements get --project <project-id> --format json

4. 技術的背景を深めるためカタログを検索し(`medo catalog search`)、必要に応じてファクトを追加保存する。
5. 完全版PRFAQを作る。ミニPRFAQの内容に加えて:
   - 技術的背景(GCP構成の要点。launch_stage・引用エントリID付きで、絵に描いた餅にしない)
   - workflow改善見込み(現状業務がどう変わるか)
   - 効果(フェルミ推定の引用。必要なら `medo fermi calc` で追加計算)
   - ロードマップ(段階と、open_questionsが各段階に与える影響)
   - FAQ(顧客・社内から想定される問いと答え)
6. 保存する:

       medo artifacts save --project <project-id> --type prfaq \
         --file /tmp/prfaq.md \
         --grown-from "<mini-prfaq-vN>:<合意した打ち手名>" \
         --cites <entry-id,...> --cites-facts <fact-id,...> \
         --generated-by <claude|gemini> --requirements-version <n>

7. 保存後 `medo status --project <project-id>` を実行し、現在地と次ステップを報告して終える。

## 契約(必ず守る)

- launch_stage・鮮度・機能の有無はカタログ値のみ。市場数値は保存済みファクトのみを引用する
- stale なファクト・カタログエントリを使う場合は必ず注記する
- 打ち手の選択(合意)を自分で行わない。ユーザーの確認を必ず取る
- `--grown-from` に育成元の候補セットIDと打ち手名を必ず記録する
- CLIが失敗したら推測で補完せずエラー内容を報告する
```

- [ ] **Step 4: 失敗するテストを書く**

`skills/tests/test_build.py`:

```python
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent

SKILL_NAMES = ["medo-hearing", "medo-propose-options", "medo-grow-prfaq"]


def test_build_generates_claude_and_agy_dist(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    for name in SKILL_NAMES:
        claude_skill = tmp_path / "claude" / name / "SKILL.md"
        assert claude_skill.exists(), name
        text = claude_skill.read_text(encoding="utf-8")
        assert text.startswith("---") and f"name: {name}" in text

        agy_skill = tmp_path / "agy" / f"{name}.md"
        assert agy_skill.exists(), name
        assert not agy_skill.read_text(encoding="utf-8").startswith("---")  # frontmatter除去

    hearing = (tmp_path / "agy" / "medo-hearing.md").read_text(encoding="utf-8")
    assert "medo requirements save" in hearing
```

- [ ] **Step 5: テストが失敗することを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: FAIL(build.py が存在しない)

- [ ] **Step 6: build.py を実装**

`skills/build.py`:

```python
"""Skill共通md → Claude形式(SKILL.md)とagy形式(.md)への変換。"""

import argparse
import re
from pathlib import Path

SRC = Path(__file__).parent / "src"


def parse(src_text: str) -> tuple[str, str]:
    """frontmatterのname値と本文(frontmatter除去済み)を返す。"""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", src_text, re.DOTALL)
    if not m:
        raise ValueError("frontmatter(---区切り)がありません")
    fm, body = m.groups()
    name_m = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
    if not name_m:
        raise ValueError("frontmatterにnameがありません")
    return name_m.group(1), body.lstrip("\n")


def build(out: Path) -> None:
    for src_file in sorted(SRC.glob("*.md")):
        text = src_file.read_text(encoding="utf-8")
        name, body = parse(text)

        claude_dir = out / "claude" / name
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "SKILL.md").write_text(text, encoding="utf-8")

        agy_dir = out / "agy"
        agy_dir.mkdir(parents=True, exist_ok=True)
        (agy_dir / f"{name}.md").write_text(body, encoding="utf-8")
    print(f"built skills into {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "dist")
    args = parser.parse_args()
    build(args.out)
```

- [ ] **Step 7: テストが通ることを確認**

Run: `uv run pytest skills/tests/test_build.py -v && uv run ruff check .`
Expected: PASS(1 passed)、リント警告なし

- [ ] **Step 8: distを生成して中身を目視確認**

Run: `python skills/build.py && ls -R skills/dist`
Expected: `claude/{medo-hearing,medo-propose-options,medo-grow-prfaq}/SKILL.md` と `agy/{medo-hearing,medo-propose-options,medo-grow-prfaq}.md`

- [ ] **Step 9: コミット**

```bash
git add skills/src/ skills/build.py skills/tests/
git commit -m "feat(skills): hearing/propose-options/grow-prfaq Skillとビルドスクリプト"
```

---

### Task 10: 統合スモーク(実環境でのWhat/Why縦切り確認)

**Files:**
- Create: `docs/setup.md`(セットアップ手順の記録)

**Interfaces:**
- Consumes: これまでの全タスク
- Produces: フェーズ1完了の定義「実案件1件で 課題ヒアリング→市場ファクト+フェルミ推定→打ち手ミニPRFAQ比較→合意案の完全版PRFAQ(GCPカタログ根拠付き) が両ホストで通る」の確認記録

このタスクは人間(ikeoさん)との共同作業。GCP認証・課金・実案件の意思決定が絡むため自動化しない。

- [ ] **Step 1: GCP前提の確認**

```bash
gcloud auth application-default login   # 対話認証(ユーザー実行)
gcloud config get-value project         # 課金有効なプロジェクトが設定されていること
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
```

注: BigQuery公開データセットのクエリとGemini API(`google-genai` はADC/Vertex経由または `GEMINI_API_KEY`)、Billing Catalog APIが使えること。

- [ ] **Step 2: ローカルバックエンドでETLをdry-run**

Run: `MEDO_BACKEND=local uv run medo etl run --since 2026-06-01 --services vertex-ai --dry-run`
Expected: upserted にエントリID群、errors が空(または少数。errorsの内容を確認)

- [ ] **Step 3: 本実行してカタログを確認**

Run: `MEDO_BACKEND=local uv run medo etl run --since 2026-04-01 --services vertex-ai,cloud-run && uv run medo catalog search "" --limit 20`
Expected: 鮮度付きカタログエントリが一覧表示される

- [ ] **Step 4: SKUスナップショットを取得**

Run: `MEDO_BACKEND=local uv run medo etl skus --service vertex-ai`
Expected: `saved: sku_snapshots/vertex-ai (<N> SKUs)`

- [ ] **Step 5: SkillをClaude Codeに配置**

```bash
python skills/build.py
mkdir -p ~/.claude/skills
cp -r skills/dist/claude/medo-hearing ~/.claude/skills/
cp -r skills/dist/claude/medo-propose-options ~/.claude/skills/
cp -r skills/dist/claude/medo-grow-prfaq ~/.claude/skills/
```

- [ ] **Step 6: Skillをagyに配置**

`skills/dist/agy/*.md` をagyのワークフロー参照場所に置き、リポジトリのAGENTS.md(なければ作成)に次を追記:

```markdown
## Medo Skills
- 課題・方針の構造化: skills/dist/agy/medo-hearing.md の手順に従う
- 打ち手候補の提案: skills/dist/agy/medo-propose-options.md の手順に従う
- PRFAQ育成: skills/dist/agy/medo-grow-prfaq.md の手順に従う
```

- [ ] **Step 7: 実案件1件でWhat/Why縦切りを通す(受け入れテスト)**

1. Claude Codeで `medo-hearing` を起動し、実案件の課題を入力 → 背景・理念(principles)・課題(challenges)込みで要件保存(`saved: v1` を確認)
2. `medo-propose-options` → 市場・国策・業界動向ファクトが出典付きで保存され(`medo facts list` で確認)、フェルミ推定が `fermi-v1` として保存され、打ち手2〜3案のミニPRFAQ候補セットが `--options`・`--cites-facts`・`--cites` 付きで保存されることを確認
3. 候補セットを見て打ち手を1つ選び(合意)、`medo-grow-prfaq` → 完全版PRFAQが `--grown-from` 付きで保存されることを確認
4. agyでも手順1〜3を実行し、`--generated-by gemini` で保存されることを確認
5. `medo artifacts list --project <id>` で claude / gemini 両方の生成物が並ぶことを確認
6. 課題を1項目追加して再保存(v2)→ `medo status` が `regenerate-stale-artifacts` を返し、`medo requirements diff` が陳腐化した生成物を報告することを確認
7. `medo fermi calc --from-artifact fermi-v1` で再計算できることを確認

- [ ] **Step 8: セットアップ手順を docs/setup.md に記録してコミット**

スモークで実際に使ったコマンド・環境変数・ハマりどころを `docs/setup.md` に記録する(内容はスモーク結果に依存するため、実行時に書く。「GCP前提」「ETL実行」「Skill配置(Claude Code/agy)」「What/Why縦切りの流れ」の4節を含めること)。

```bash
git add docs/setup.md
git commit -m "docs: フェーズ1セットアップ手順とスモーク結果"
```

---

## 自己レビュー結果

- **スペック対応**: What/Why縦切りMVPの構成要素(要件拡張=background/principles/challenges、市場ファクト=kind別出典検証+180日stale、フェルミ=決定論計算+再計算、生成物=mini-prfaq候補セット/grown_from付きprfaq、status=引用根拠込み陳腐化判定、Skill 3本、最小ETL)はTask 1〜10で網羅
- **フェーズ1対象外(意図的)**: make-slides・build-mock・propose-architecture(詳細)・pricing計算機・decision-roadmap・knowledge-digest・Webアプリ・Scheduler自動化はフェーズ2以降、compare-awsはバックログ(スペックのフェーズ計画どおり)
- **型整合**: `Fact.fact_id`=`fact-<n>`、`CatalogEntry.entry_id`=`{service}__{feature}`、生成物ID=`{type}-v{n}`、`GrownFrom{artifact, option}`、`ConfidenceItem{text, confidence}` を core / CLI / Skill 間で共通使用。日付はISO文字列で統一
- **契約変更の扱い**: Task 6b(要件スキーマ)・6c/6e(CLI新コマンド)・6d(生成物スキーマ)は人間レビュー対象としてGlobal Constraintsに明記
