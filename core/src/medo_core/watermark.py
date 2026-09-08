"""ID採番簿。プレフィックス別の high-water mark を単調増加で保持する。

直前バージョンの最大ID+1で採番すると、最大IDのノードを削除した後に
そのIDを再利用してしまう。採番簿を永続化してこれを防ぐ。

load → allocate → save はトランザクションではない。並行保存が起きると同じIDを
二重に割り当てうる。利用スコープが本人のみで同時保存が起きない前提に依存している。
"""

from pydantic import BaseModel, Field

from medo_core.storage import Storage


class IdWatermark(BaseModel):
    marks: dict[str, int] = Field(default_factory=dict)

    def allocate(self, prefix: str, count: int) -> list[str]:
        """prefix の採番を count 件進め、割り当てたIDを返す。"""
        start = self.marks.get(prefix, 0)
        ids = [f"{prefix}-{n}" for n in range(start + 1, start + count + 1)]
        self.marks[prefix] = start + count
        return ids


class IdWatermarkStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _path(self, project_id: str) -> str:
        return f"projects/{project_id}/meta/id_watermark"

    def load(self, project_id: str) -> IdWatermark:
        raw = self._storage.get(self._path(project_id))
        return IdWatermark.model_validate(raw) if raw else IdWatermark()

    def save(self, project_id: str, watermark: IdWatermark) -> None:
        self._storage.put(self._path(project_id), watermark.model_dump(mode="json"))
