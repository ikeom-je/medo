from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from medo_cli.fetch import fetch_body


class Response:
    def __init__(self, body: bytes, content_type: str):
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


def _opener(body: bytes, content_type: str):
    def open_response(request, timeout):
        assert request.get_header("User-agent")
        assert timeout == 15
        return Response(body, content_type)

    return open_response


def test_fetch_extracts_html():
    html = b"<html><body><p>The market reached 3.2 trillion yen in 2024.</p></body></html>"
    result = fetch_body("https://example.com", opener=_opener(html, "text/html"))
    assert result.body and "3.2 trillion yen" in result.body


def test_fetch_extracts_shift_jis_html():
    html = ("<html><head><meta charset='Shift_JIS'></head><body>"
            "<p>市場規模は2024年に3.2兆円でした。</p></body></html>").encode("shift_jis")
    result = fetch_body("https://example.com", opener=_opener(html, "text/html"))
    assert result.body and "3.2兆円" in result.body


@pytest.mark.parametrize("content_type", ["application/pdf", "application/octet-stream"])
def test_fetch_extracts_pdf_even_when_served_as_octet_stream(content_type):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 100 Td (PDF evidence 2024) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    second = writer.add_blank_page(width=200, height=200)
    second[NameObject("/Resources")] = page["/Resources"]
    second_stream = DecodedStreamObject()
    second_stream.set_data(b"BT /F1 12 Tf 20 100 Td (second page evidence) Tj ET")
    second[NameObject("/Contents")] = writer._add_object(second_stream)
    output = BytesIO()
    writer.write(output)
    result = fetch_body("https://example.com/a.pdf", opener=_opener(output.getvalue(),
                                                                       content_type))
    assert result.body and "PDF evidence 2024" in result.body
    assert "second page evidence" in result.body


def test_fetch_reports_http_error():
    def forbidden(*_args, **_kwargs):
        raise HTTPError("https://example.com", 403, "Forbidden", {}, None)

    result = fetch_body("https://example.com", opener=forbidden)
    assert result.body is None and "403" in result.reason


def test_fetch_reports_empty_body_and_unsupported_content_type():
    empty = fetch_body("https://example.com", opener=_opener(b"", "text/html"))
    unsupported = fetch_body("https://example.com", opener=_opener(b"data", "text/plain"))
    assert empty.body is None and empty.reason
    assert unsupported.body is None and "text/plain" in unsupported.reason


def test_fetch_reports_timeout_and_url_error():
    def timeout(*_args, **_kwargs):
        raise TimeoutError("timed out")

    def unavailable(*_args, **_kwargs):
        raise URLError("unavailable")

    assert "timed out" in fetch_body("https://example.com", opener=timeout).reason
    assert "unavailable" in fetch_body("https://example.com", opener=unavailable).reason


def _text_pdf(text: bytes) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 100 Td (" + text + b") Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize("prefix", [b"\xef\xbb\xbf", b"\r\n  "])
def test_fetch_finds_pdf_header_after_leading_bytes(prefix):
    raw = prefix + _text_pdf(b"leading bytes evidence")
    result = fetch_body("https://example.com/a", opener=_opener(raw, "application/octet-stream"))
    assert result.body and "leading bytes evidence" in result.body


def test_fetch_reports_pdf_without_text_as_empty_body():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    output = BytesIO()
    writer.write(output)
    result = fetch_body("https://example.com/a.pdf", opener=_opener(output.getvalue(),
                                                                      "application/pdf"))
    assert result.body is None and "空本文" in result.reason


def test_fetch_reports_broken_pdf_as_fetch_failure():
    result = fetch_body("https://example.com/a.pdf",
                        opener=_opener(b"%PDF-1.7 broken", "application/pdf"))
    assert result.body is None and result.reason
