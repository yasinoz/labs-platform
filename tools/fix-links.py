#!/usr/bin/env python3
"""Markdown icindeki goreli baglantilari onarir.

Upstream kaynakta uc tur kirik baglanti vardi ve hepsi Jekyll sitesinde
calisip GitHub'da/klonlanmis repoda calismiyordu:

  1. Mutlak yollar:   ](/img/x.png)      -> ](../../img/x.png)
     Jekyll site kokune gore cozuyordu; repo icinde boyle bir kok yok.
  2. Windows ters bolusu:  ](\\lab\\queries\\x.json) -> ](./lab/queries/x.json)
  3. Hedefi hic var olmayan baglantilar -> otomatik duzeltilemez, raporlanir.

Kullanim:
    python fix-links.py <repo> --dry-run
    python fix-links.py <repo> --apply
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\))")
SKIP_DIRS = {".git", "node_modules", ".github", ".vscode", "obj", "bin"}


def split_code_blocks(text):
    """Kod bloklarinin satir numaralarini dondurur - oralara dokunmayiz."""
    fence, in_code = None, set()
    for n, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^(\s*)(`{3,}|~{3,})", line)
        if m:
            if fence is None:
                fence = m.group(2)
            elif line.strip().startswith(fence):
                fence = None
            in_code.add(n)
            continue
        if fence:
            in_code.add(n)
    return in_code


def fix_target(target, md_path, root):
    """Bir baglanti hedefini onarmaya calisir. (yeni_hedef, aciklama) doner."""
    if target.startswith(("http://", "https://", "mailto:", "#", "//")):
        return None, None

    # 2) Ters bolu -> egik bolu
    if "\\" in target:
        candidate = target.replace("\\", "/").lstrip("/")
        if (md_path.parent / candidate).exists():
            return "./" + candidate, "ters bolu"

    # 1) Mutlak yol -> repo kokune gore goreli
    if target.startswith("/"):
        rel = target.lstrip("/").split("#")[0].split("?")[0]
        if (root / rel).exists():
            relative = os.path.relpath(root / rel, md_path.parent)
            return relative.replace("\\", "/"), "mutlak yol"
        return None, "hedef repoda yok: " + target

    clean = target.split("#")[0].split("?")[0]
    if clean and not (md_path.parent / clean).exists():
        return None, "hedef yok: " + target
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    write = args.apply and not args.dry_run
    fixed, unresolved = [], []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            path = Path(dirpath) / fn
            text = path.read_text(encoding="utf-8", errors="replace")
            code_lines = split_code_blocks(text)
            lines = text.split("\n")
            changed = False

            for idx, line in enumerate(lines):
                if (idx + 1) in code_lines:
                    continue
                if "](" not in line:
                    continue

                def repl(m):
                    nonlocal changed
                    new, why = fix_target(m.group(2), path, root)
                    if new:
                        changed = True
                        fixed.append((path.relative_to(root).as_posix(),
                                      m.group(2), new, why))
                        return m.group(1) + new + m.group(3)
                    if why:
                        unresolved.append(
                            (path.relative_to(root).as_posix(), idx + 1, why))
                    return m.group(0)

                lines[idx] = LINK.sub(repl, line)

            if changed and write:
                path.write_text("\n".join(lines), encoding="utf-8", newline="")

    mode = "UYGULANDI" if write else "DENEME (--apply ile yaz)"
    print("\n  {} - {}\n".format(root.name, mode))
    print("  onarilan: {}".format(len(fixed)))
    by_why = {}
    for rel, old, new, why in fixed:
        by_why.setdefault(why, []).append((rel, old, new))
    for why, items in sorted(by_why.items()):
        print("\n  {} ({}):".format(why, len(items)))
        for rel, old, new in items[:15]:
            print("    {}\n      {}  ->  {}".format(rel, old, new))
        if len(items) > 15:
            print("    ... {} tane daha".format(len(items) - 15))

    if unresolved:
        print("\n  OTOMATIK ONARILAMAYAN ({}) - elle karar gerekiyor:".format(len(unresolved)))
        seen = set()
        for rel, line, why in unresolved:
            key = (rel, why)
            if key in seen:
                continue
            seen.add(key)
            print("    {}:{}  {}".format(rel, line, why))
    print()


if __name__ == "__main__":
    main()
