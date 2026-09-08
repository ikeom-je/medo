"""フェルミ推定の決定論計算。仮定は明示、計算はコード(ast制限: 四則演算+累乗)。LLM・eval不使用。"""

from __future__ import annotations

import ast

from pydantic import BaseModel, Field, model_validator

from medo_core.facts import Fact

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
MAX_EXPONENT = 100  # 資源枯渇(巨大数の計算)防止


class FermiVar(BaseModel):
    fact: str | None = None  # ファクトID参照(valueを使う)
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
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
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
