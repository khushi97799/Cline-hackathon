import httpx
import pytest

from app import source_fetch
from app.htmltext import html_to_text
from app.source_fetch import SourceFetchError, fetch_source, validate_source_url


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """Pretend every official host resolves to a public address."""
    monkeypatch.setattr(source_fetch, "_resolve", lambda host: ["93.184.216.34"])


def test_only_official_hosts_are_allowed():
    assert validate_source_url("https://pmkisan.gov.in/page").startswith("https://pmkisan.gov.in")
    assert validate_source_url("https://nsap.nic.in/")
    for bad in ("https://example.com/", "https://evilgov.in/", "https://gov.in.evil.com/", "ftp://x.gov.in/",
                "https://user:pw@x.gov.in/", "https://x.gov.in:8080/", "javascript:alert(1)", ""):
        with pytest.raises(SourceFetchError):
            validate_source_url(bad)


def test_internal_addresses_are_blocked(monkeypatch):
    for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1"):
        monkeypatch.setattr(source_fetch, "_resolve", lambda host, ip=ip: [ip])
        with pytest.raises(SourceFetchError):
            validate_source_url("https://sneaky.gov.in/")


def _client(handler):
    return httpx.MockTransport(handler)


def test_html_is_turned_into_clean_text():
    html = "<html><head><title> My  Scheme </title><style>x{}</style></head><body><script>bad()</script>" \
           "<h1>Scheme</h1><p>Last date to apply is 5 May 2027.</p><ul><li>One</li><li>Two</li></ul></body></html>"
    title, text = html_to_text(html)
    assert title == "My Scheme" and "bad()" not in text and "x{}" not in text
    assert "Last date to apply is 5 May 2027." in text and "One\nTwo" in text


def test_fetch_returns_text_and_stable_hash():
    page = "<html><body><p>Hello   world   scheme</p></body></html>"
    t = _client(lambda r: httpx.Response(200, text=page, headers={"content-type": "text/html; charset=utf-8"}))
    a = fetch_source("https://x.gov.in/a", transport=t)
    b = fetch_source("https://x.gov.in/a", transport=t)
    assert "Hello world scheme" in a.text and a.sha256 == b.sha256 and len(a.sha256) == 64


def test_redirect_to_a_non_official_host_is_refused():
    def handler(r):
        return httpx.Response(302, headers={"location": "https://evil.example.com/steal"})
    with pytest.raises(SourceFetchError):
        fetch_source("https://x.gov.in/a", transport=_client(handler))


def test_pdf_errors_and_oversize_are_rejected():
    pdf = _client(lambda r: httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}))
    with pytest.raises(SourceFetchError, match="PDF"):
        fetch_source("https://x.gov.in/a.pdf", transport=pdf)
    big = _client(lambda r: httpx.Response(200, content=b"a" * 2_100_000, headers={"content-type": "text/plain"}))
    with pytest.raises(SourceFetchError, match="too large"):
        fetch_source("https://x.gov.in/a", transport=big)
    err = _client(lambda r: httpx.Response(500))
    with pytest.raises(SourceFetchError):
        fetch_source("https://x.gov.in/a", transport=err)
