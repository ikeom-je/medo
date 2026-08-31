"""案件内容のノード型。永続化を持たない純粋なスキーマ。

要件・イベント・診断のすべてが参照するため、Storeを持つモジュールから分離する
(requirements.py に置くと events.py との循環参照になる)。
"""

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["confirmed", "assumed", "open"]
Scope = Literal["core", "secondary", "out"]


class Node(BaseModel):
    """IDを持つ案件内容の最小単位。

    id が空文字なら保存時に core が採番する。
    """

    id: str = ""
    text: str
    confidence: Confidence = "open"
    evidence_refs: list[str] = Field(default_factory=list)


class ScopedNode(Node):
    """診断のスコープ絞り込み対象になるノード。

    案件の属性(Kpi / Stakeholder)には scope を付けない。
    """

    scope: Scope = "core"
