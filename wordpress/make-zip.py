#!/usr/bin/env python3
"""WordPress eklentisini yuklenmeye hazir ZIP olarak paketler.

Neden PowerShell'in Compress-Archive'i degil: Windows PowerShell 5.1 ZIP
girdilerini TERS BOLU ile yaziyor ('sudo2go-labs\\includes\\x.php'). Linux
sunucuda unzip bunu dizin ayraci saymayip, adinda ters bolu olan tek bir
dosya olusturabiliyor - eklenti de sessizce bozuluyor.

ZIP belirtimi dizin ayraci olarak DUZ bolu ister. Burada arcname'leri acikca
duz boluyle yaziyoruz.

Kullanim:
    python make-zip.py            # sudo2go-labs.zip uretir
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE / "sudo2go-labs"
OUT = HERE / "sudo2go-labs.zip"

# WordPress'e gitmemesi gereken dosyalar
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
SKIP_SUFFIX = {".pyc", ".zip", ".log"}


def main() -> int:
    if not PLUGIN.is_dir():
        print("eklenti dizini yok: " + str(PLUGIN))
        return 1

    files = []
    for path in sorted(PLUGIN.rglob("*")):
        if not path.is_file():
            continue
        if path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIX:
            continue
        if "__pycache__" in path.parts:
            continue
        files.append(path)

    if not files:
        print("paketlenecek dosya bulunamadi")
        return 1

    if OUT.exists():
        OUT.unlink()

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            # arcname: eklenti klasorunu koke alarak, DUZ boluyle
            arcname = PLUGIN.name + "/" + path.relative_to(PLUGIN).as_posix()
            zf.write(path, arcname)

    print("  {}  ({:.1f} KB)".format(OUT.name, OUT.stat().st_size / 1024))
    with zipfile.ZipFile(OUT) as zf:
        bad = [n for n in zf.namelist() if "\\" in n]
        for name in zf.namelist():
            print("    " + name)
        print()
        if bad:
            print("  !! ters bolu iceren girdi var: " + ", ".join(bad))
            return 1
        print("  tum girdiler duz bolu kullaniyor - Linux sunucuda guvenli")
    return 0


if __name__ == "__main__":
    sys.exit(main())
