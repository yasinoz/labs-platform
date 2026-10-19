"""YAML'in bu projede kullanilan altkumesi icin bagimlilik gerektirmeyen okuyucu.

Neden PyYAML yok: lab araclari ogrenci/egitmen makinesinde ve CI'da
'pip install' gerektirmeden calismali. Kendi yazdigimiz dosyalari
okuyoruz, dolayisiyla YAML'in tamamini desteklemek gereksiz.

Desteklenen: ic ice sozlukler, listeler (- skaler / - anahtar: deger),
blok skalerler (| ve >), yorumlar, tirnakli dizgiler, bool/int/null.
Desteklenmeyen: capalar, etiketler, akis stili ({} []), cok satirli anahtarlar.
"""
from __future__ import annotations

__all__ = ["load", "loads", "MiniYamlError"]


class MiniYamlError(ValueError):
    pass


def _split_flow(body: str):
    """Akis stili liste govdesini virgullerden ayirir; tirnak icini atlar."""
    parts, buf, quote, depth = [], [], None, 0
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return parts


def _scalar(raw: str):
    s = raw.strip()
    if not s:
        return ""
    # Akis stili liste: [a, b, c] - frontmatter'da 'requires: [docker]' sik.
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        return [_scalar(p) for p in _split_flow(s[1:-1])]
    if len(s) >= 2 and s[0] == "{" and s[-1] == "}":
        out = {}
        for part in _split_flow(s[1:-1]):
            k, v = _split_kv(part)
            if k is None:
                raise MiniYamlError(f"akis stili sozlukte ':' yok -> {part!r}")
            out[_key(k)] = _scalar(v)
        return out
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _key(raw: str) -> str:
    """Anahtari normalize et: cevresindeki tirnaklari kaldir."""
    k = raw.strip()
    if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
        return k[1:-1]
    return k


def _split_kv(s: str):
    """'anahtar: deger' ayrimi - tirnak icindeki ':' karakterini atlar.

    Imaj referanslari anahtar olarak kullanildiginda ("alpine:3.13": "alpine:3.24")
    naif partition(':') anahtari ortadan bolerdi.
    """
    quote = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch == ":":
            return s[:i], s[i + 1:]
    return None, None


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            # bosluktan sonra gelen # yorumdur
            if out and out[-1] in (" ", "\t"):
                break
            if not out:
                break
        out.append(ch)
    return "".join(out).rstrip()


class _Lines:
    def __init__(self, text: str):
        self.rows = []
        for n, raw in enumerate(text.splitlines(), 1):
            if raw.strip().startswith("#") or not raw.strip():
                self.rows.append((n, None, raw))  # blok skalerler icin sakla
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            self.rows.append((n, indent, raw))
        self.i = 0

    def peek(self):
        while self.i < len(self.rows) and self.rows[self.i][1] is None:
            self.i += 1
        return self.rows[self.i] if self.i < len(self.rows) else None

    def raw_at(self, idx):
        return self.rows[idx] if idx < len(self.rows) else None


def _block_scalar(lines: _Lines, parent_indent: int, fold: bool) -> str:
    chunks, first_indent = [], None
    while lines.i < len(lines.rows):
        _, indent, raw = lines.rows[lines.i]
        if indent is None:                      # bos satir / yorum satiri
            if not raw.strip():
                chunks.append("")
                lines.i += 1
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= parent_indent:
                break
            if first_indent is None:
                first_indent = indent
            chunks.append(raw[first_indent:])
            lines.i += 1
            continue
        if indent <= parent_indent:
            break
        if first_indent is None:
            first_indent = indent
        chunks.append(raw[first_indent:])
        lines.i += 1
    while chunks and chunks[-1] == "":
        chunks.pop()
    if fold:
        return " ".join(c for c in chunks if c) + ("\n" if chunks else "")
    return "\n".join(chunks) + ("\n" if chunks else "")


def _parse(lines: _Lines, indent: int):
    nxt = lines.peek()
    if nxt is None:
        return None
    if nxt[2].lstrip().startswith("- "):
        return _parse_list(lines, indent)
    return _parse_map(lines, indent)


def _parse_list(lines: _Lines, indent: int):
    items = []
    while True:
        nxt = lines.peek()
        if nxt is None:
            break
        n, ind, raw = nxt
        if ind < indent or not raw.lstrip().startswith("- "):
            break
        body = _strip_comment(raw.lstrip()[2:])
        lines.i += 1
        key, val = _split_kv(body)
        if key is not None:
            # - anahtar: deger  -> ayni satirda baslayan sozluk
            item = {}
            item[_key(key)] = _value(lines, ind + 2, val)
            nxt2 = lines.peek()
            while nxt2 and nxt2[1] is not None and nxt2[1] > ind and not nxt2[2].lstrip().startswith("- "):
                sub = _parse_map(lines, nxt2[1])
                if isinstance(sub, dict):
                    item.update(sub)
                nxt2 = lines.peek()
            items.append(item)
        else:
            items.append(_scalar(body))
    return items


def _value(lines: _Lines, child_indent: int, inline: str):
    inline = _strip_comment(inline).strip()
    if inline == "|":
        return _block_scalar(lines, child_indent - 2, fold=False)
    if inline == ">":
        return _block_scalar(lines, child_indent - 2, fold=True)
    if inline:
        return _scalar(inline)
    nxt = lines.peek()
    if nxt is None or nxt[1] is None or nxt[1] <= child_indent - 2:
        return None
    return _parse(lines, nxt[1])


def _parse_map(lines: _Lines, indent: int):
    out = {}
    while True:
        nxt = lines.peek()
        if nxt is None:
            break
        n, ind, raw = nxt
        if ind < indent:
            break
        if ind > indent:
            raise MiniYamlError(f"satir {n}: beklenmeyen girinti")
        stripped = _strip_comment(raw.strip())
        if stripped.startswith("- "):
            break
        key, val = _split_kv(stripped)
        if key is None:
            raise MiniYamlError(f"satir {n}: ':' bulunamadi -> {raw!r}")
        lines.i += 1
        out[_key(key)] = _value(lines, indent + 2, val)
    return out


def loads(text: str):
    lines = _Lines(text)
    nxt = lines.peek()
    if nxt is None:
        return {}
    return _parse(lines, nxt[1])


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return loads(fh.read())
