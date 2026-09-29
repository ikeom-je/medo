"""出典本文と抜粋の決定論的な照合。"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from medo_core.facts import Fact

_MULTIPLIERS = {"兆": 10**12, "億": 10**8, "百万": 10**6, "万": 10**4, "千": 10**3}
_NUMBER = re.compile(
    r"(?P<sign>マイナス|[-−▲△])?"
    r"(?P<digits>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(?P<mult>百万|兆|億|万|千)?"
)
_DECLARATION = re.compile(r"単位\s*:\s*([^\s)）]+)")
_SUFFIX = re.compile(r"[^\d\s,.:;()（）\-−▲△]*")


@dataclass(frozen=True)
class Number:
    value: float
    multiplier: str
    suffix: str


@dataclass(frozen=True)
class CheckResult:
    verified: bool
    reason: str = ""
    nearby: str | None = None


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _compact(text: str) -> str:
    return "".join(normalize(text).split())


def quote_in_body(quote: str, body: str) -> bool:
    return bool(_compact(quote)) and _compact(quote) in _compact(body)


def extract_numbers(quote: str) -> list[Number]:
    text = normalize(quote)
    tokens = list(_NUMBER.finditer(text))
    numbers: list[Number] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        multiplier = token.group("mult") or ""
        magnitude = _MULTIPLIERS.get(multiplier, 1)
        value = float(token.group("digits").replace(",", "")) * magnitude
        end = token.end()
        next_index = index + 1
        while (
            multiplier
            and next_index < len(tokens)
            and tokens[next_index].start() == end
            and tokens[next_index].group("mult")
            and _MULTIPLIERS[tokens[next_index].group("mult")] < magnitude
        ):
            part = tokens[next_index]
            value += float(part.group("digits").replace(",", "")) * _MULTIPLIERS[
                part.group("mult")
            ]
            magnitude = _MULTIPLIERS[part.group("mult")]
            end = part.end()
            next_index += 1
        if token.group("sign"):
            value = -value
        suffix = _SUFFIX.match(text, end).group()
        numbers.append(Number(value=value, multiplier=multiplier, suffix=suffix))
        index = next_index
    return numbers


def _without_annotation(unit: str) -> str:
    # 保存済みの単位には「%(F1向上率)」のような注記が付くことがある。注記は出典の表記に現れない。
    # 末尾の括弧書き1つだけを除く。単位本体の括弧(「円/(kWh)」)や括弧だけの単位(「(%)」)は残す。
    unit = normalize(unit).strip()
    stripped = re.sub(r"\([^()]*\)$", "", unit).strip()
    return stripped or unit


def _unit_parts(unit: str) -> tuple[int, str]:
    unit = _without_annotation(unit)
    for word in _MULTIPLIERS:
        if unit.startswith(word):
            return _MULTIPLIERS[word], unit[len(word):]
    return 1, unit


def value_matches(quote: str, value: float, unit: str) -> bool:
    declarations = _DECLARATION.findall(normalize(quote))
    unit_multiplier, base_unit = _unit_parts(unit)
    target = value * unit_multiplier
    for number in extract_numbers(quote):
        if not number.multiplier and not number.suffix:
            if len(declarations) == 1 and declarations[0] == _without_annotation(unit):
                if math.isclose(number.value, value, rel_tol=1e-9, abs_tol=0):
                    return True
            continue
        if (
            math.isclose(number.value, target, rel_tol=1e-9, abs_tol=0)
            and (not base_unit or number.suffix.startswith(base_unit))
        ):
            return True
    return False


def nearby_excerpt(quote: str, body: str, value: float | None, unit: str) -> str | None:
    compact_body = _compact(body)
    compact_quote = _compact(quote)
    position = -1
    for length in range(min(8, len(compact_quote)), 1, -1):
        position = compact_body.find(compact_quote[:length])
        if position >= 0:
            break
    if position < 0:
        candidates = [match.group("digits") for match in _NUMBER.finditer(normalize(quote))]
        if value is not None:
            candidates.append(str(value))
        position = next((i for candidate in candidates if (i := compact_body.find(candidate)) >= 0), -1)
    if position < 0:
        return None
    return compact_body[max(0, position - 30):position + 80]


def check(quote: str, body: str, value: float | None, unit: str) -> CheckResult:
    if not quote_in_body(quote, body):
        return CheckResult(False, "quote-not-found", nearby_excerpt(quote, body, value, unit))
    if value is not None and not value_matches(quote, value, unit):
        return CheckResult(False, "value-not-in-quote", nearby_excerpt(quote, body, value, unit))
    return CheckResult(True)


def verify_fact(fact: "Fact", body: str, checked: str) -> "Fact":
    from medo_core.facts import Verification

    result = check(fact.quote, body, fact.value, fact.unit)
    if not result.verified:
        raise ValueError(f"{result.reason}: {result.nearby or ''}")
    return type(fact).model_validate(fact.model_copy(update={
        "verification": Verification(status="verified", checked=checked)
    }).model_dump())
