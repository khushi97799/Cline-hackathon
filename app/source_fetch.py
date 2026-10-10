"""Safe download of official scheme pages.

Only http/https URLs on allowed official domains (default .gov.in and .nic.in),
never private/internal addresses (SSRF protection), redirects re-checked on every
hop, small size cap, short timeout.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.htmltext import html_to_text
from app.textutil import sha256_text

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
TEXT_TYPES = {"text/html", "application/xhtml+xml", "text/plain"}
XML_TYPES = {"application/rss+xml", "application/atom+xml", "application/xml", "text/xml"}


class SourceFetchError(Exception):
    pass


@dataclass
class FetchResult:
    url: str
    title: str
    text: str
    sha256: str
    content_type: str
    html: str = ""          # raw page, kept so discovery can read the links on a listing page


def allowed_suffixes() -> list:
    raw = os.environ.get("SOURCE_ALLOWED_SUFFIXES", ".gov.in,.nic.in")
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def _resolve(host: str) -> list:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})
    except socket.gaierror as e:
        raise SourceFetchError("Could not find that website address.") from e


def host_allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    return any(host == s.lstrip(".") or host.endswith(s if s.startswith(".") else "." + s) for s in allowed_suffixes())


def validate_source_url(url: str) -> str:
    p = urlparse((url or "").strip())
    if p.scheme not in ("http", "https") or not p.hostname:
        raise SourceFetchError("Enter a full web address starting with http:// or https://")
    if p.username or p.password:
        raise SourceFetchError("Web addresses with a login inside are not allowed.")
    if p.port not in (None, 80, 443):
        raise SourceFetchError("Only standard web ports are allowed.")
    if not host_allowed(p.hostname):
        raise SourceFetchError("Only official government websites are allowed (" + ", ".join(allowed_suffixes()) + ").")
    for ip in _resolve(p.hostname):
        a = ipaddress.ip_address(ip)
        if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified:
            raise SourceFetchError("That address points to an internal network and is blocked.")
    return p.geturl()


def fetch_source(url: str, transport=None) -> FetchResult:
    """Download one official page (or feed) safely and return its plain text."""
    current = validate_source_url(url)
    headers = {"User-Agent": "SchemeSniperBot/1.0 (official sources only)"}
    try:
        with httpx.Client(timeout=15.0, follow_redirects=False, headers=headers, transport=transport) as client:
            for _ in range(MAX_REDIRECTS + 1):
                with client.stream("GET", current) as r:
                    if r.status_code in (301, 302, 303, 307, 308):
                        loc = r.headers.get("location")
                        if not loc:
                            raise SourceFetchError("The website redirected without a destination.")
                        current = validate_source_url(urljoin(current, loc))
                        continue
                    if r.status_code >= 400:
                        raise SourceFetchError(f"The website answered with error {r.status_code}.")
                    ctype = r.headers.get("content-type", "text/html").split(";")[0].strip().lower()
                    if "pdf" in ctype:
                        raise SourceFetchError("This is a PDF. Copy its text and paste it instead.")
                    if ctype not in TEXT_TYPES and ctype not in XML_TYPES:
                        raise SourceFetchError(f"Unsupported page type: {ctype}.")
                    data = bytearray()
                    for chunk in r.iter_bytes():
                        data += chunk
                        if len(data) > MAX_BYTES:
                            raise SourceFetchError("The page is too large to read safely.")
                    body = bytes(data).decode(r.encoding or "utf-8", errors="replace")
                    title, text = ("", body) if (ctype in XML_TYPES or ctype == "text/plain") else html_to_text(body)
                    return FetchResult(current, title, text, sha256_text(text), ctype, html=body if ctype not in XML_TYPES else "")
    except httpx.HTTPError as e:
        raise SourceFetchError("Could not download the page. Check the address and try again.") from e
    raise SourceFetchError("The website redirected too many times.")
