"""URLから検証用の出典本文を取得する。"""

from dataclasses import dataclass
from io import BytesIO
from urllib.request import Request, urlopen

import trafilatura
from pypdf import PdfReader


@dataclass(frozen=True)
class FetchResult:
    body: str | None = None
    reason: str = ""


def fetch_body(url: str, *, opener=None, timeout: int = 15) -> FetchResult:
    request = Request(url, headers={"User-Agent": "Medo/0.1 (+source-verification)"})
    open_url = opener or urlopen
    if hasattr(open_url, "open"):
        open_url = open_url.open
    try:
        with open_url(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            raw = response.read()
        if not raw:
            return FetchResult(reason="本文が空です")
        # 行政サイトのPDFは application/octet-stream で返ることが多く、Content-Type だけでは漏れる。
        if content_type == "application/pdf" or raw.startswith(b"%PDF"):
            body = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
        elif content_type in ("text/html", "application/xhtml+xml"):
            body = trafilatura.extract(raw)
        else:
            return FetchResult(reason=f"非対応の Content-Type: {content_type or '(なし)'}")
        if not body or not body.strip():
            return FetchResult(reason="本文を抽出できませんでした(空本文)")
        return FetchResult(body=body)
    except Exception as exc:
        return FetchResult(reason=f"{type(exc).__name__}: {exc}")
