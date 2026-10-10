"""Turn an HTML page into plain text using only the standard library."""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser

from app.textutil import normalize_ws


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}
    BLOCK = {"p", "div", "section", "article", "main", "header", "footer", "table", "ul", "ol",
             "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}
    LINE = {"br", "li", "tr", "dt", "dd"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n\n")
        elif tag in self.LINE:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> tuple:
    """(title, text). Paragraph/line structure is kept, other whitespace collapsed."""
    p = _TextExtractor()
    p.feed(html)
    raw = unescape("".join(p.parts)).replace("\xa0", " ")
    out, blank = [], 0
    for line in (" ".join(l.split()) for l in raw.split("\n")):
        if line:
            out.append(line)
            blank = 0
        else:
            blank += 1
            if blank == 1 and out:
                out.append("")
    return normalize_ws(p.title), "\n".join(out).strip()
