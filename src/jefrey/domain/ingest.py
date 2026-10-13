"""Importacao de documentos de texto para a memoria: extrai o texto e corta em trechos buscaveis."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import PurePosixPath

MAX_BYTES = 2 * 1024 * 1024
MAX_CHUNKS = 200
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".log", ".yaml", ".yml", ".xml"}


class IngestError(ValueError):
    """Arquivo recusado; a mensagem e para o usuario."""


class _HtmlText(HTMLParser):
    SKIP = {"script", "style", "noscript", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _decode(data: bytes) -> str:
    if b"\x00" in data[:4096]:
        raise IngestError("esse arquivo parece binário, não texto")
    for enc in ("utf-8-sig", "utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig",):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")  # arquivos antigos em portugues (ANSI) ainda ficam legiveis


def extract_text(filename: str, data: bytes) -> str:
    """Texto do arquivo. Levanta IngestError com motivo claro quando nao da para importar."""
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    ext = PurePosixPath(name.lower()).suffix
    if ext in (".pdf", ".docx", ".doc", ".xlsx", ".pptx"):
        raise IngestError("PDF e documentos do Office ainda não são suportados; salve como .txt ou .md e tente de novo")
    if ext not in TEXT_EXTENSIONS:
        raise IngestError("tipo de arquivo não suportado (use " + ", ".join(sorted(TEXT_EXTENSIONS)) + ")")
    if not data:
        raise IngestError("o arquivo está vazio")
    if len(data) > MAX_BYTES:
        raise IngestError(f"arquivo grande demais (máximo {MAX_BYTES // 1024 // 1024} MB)")
    text = _decode(data)
    if ext in (".html", ".htm"):
        p = _HtmlText()
        p.feed(text)
        text = "".join(p.parts)
    elif ext == ".json":
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False, indent=1)
        except ValueError:
            pass  # JSON invalido: importa como texto mesmo
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise IngestError("não encontrei texto nesse arquivo")
    return text


def chunk_text(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    """Trechos de ate `size` caracteres, cortados em paragrafo/frase, com sobreposicao para nao perder contexto."""
    text = text.strip()
    if not text:
        return []
    if size < 100 or overlap < 0 or overlap >= size // 2:
        raise ValueError("parametros de corte invalidos")
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(".\n"), window.rfind(". "), window.rfind("\n"))
            if cut > size * 0.5:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks
