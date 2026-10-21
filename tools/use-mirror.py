#!/usr/bin/env python3
"""Lablardaki Docker Hub imaj referanslarini GHCR aynasina cevirir.

Esleme kurali tools/mirror_map.py'de; aynalama is akisi da ayni dosyayi
kullaniyor. Boylece "aynalanan ad" ile "lablarda yazan ad" ayrisamiyor.

Yalnizca mirror/images.txt'te YER ALAN imajlar degistirilir. Listede
olmayan bir sey (lab icinde derlenen imajlar, Docker Hub disi
registry'ler) oldugu gibi birakilir - aynalanmamis bir adrese
yonlendirmek labi tamamen bozardi.

Kullanim:
  python _platform/tools/use-mirror.py --dry-run    # ne degisecek, goster
  python _platform/tools/use-mirror.py              # uygula
  python _platform/tools/use-mirror.py --revert     # GHCR -> Docker Hub
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mirror_map import target  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
TRACKS = ("DevSecOps", "Docker", "Kubernetes", "Observability")
# GERCEKTEN aynalanmis imajlar. Aynalama is akisi uretiyor.
# images.txt "aynalanmasi istenenler", mirrored.txt ise "aynalanabilenler":
# ikincisi kullaniliyor cunku aynalanamamis bir adrese yonlendirmek labi
# tamamen bozar. Boylece aynalama listesinin kusursuz olmasina da
# bagimli degiliz.
LIST = ROOT / "_platform" / "mirror" / "mirrored.txt"
EXTS = (".yml", ".yaml", ".md")


def load_pairs():
    if not LIST.exists():
        sys.exit("mirror/mirrored.txt yok. Once aynalama is akisini calistir:
"
                 "  gh workflow run mirror-images.yml --repo yasinoz/labs-platform")
    pairs = []
    for line in io.open(LIST, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "	" in line:
            src, dst = line.split("	", 1)
        else:
            src, dst = line, target(line)
        # Digest'li kaynak referansi lab dosyalarinda nasil yaziliysa
        # oyle aranmali; crane icin kullanilan bicim degil.
        pairs.append((src.strip(), dst.strip()))
    # Uzun adlari once degistir: "alpine:3.24" kisa adi
    # "courselabs/alpine:3.24" icinde de gecebilir.
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    pairs = load_pairs()
    if args.revert:
        pairs = [(b, a) for a, b in pairs]
    print("esleme sayisi: %d%s" % (len(pairs), "  (GERI ALMA)" if args.revert else ""))

    total, touched = 0, []
    for t in TRACKS:
        base = ROOT / t
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or ".git" in p.parts or p.suffix not in EXTS:
                continue
            try:
                s = p.read_text(encoding="utf-8")
            except Exception:
                continue
            orig = s
            n = 0
            for src, dst in pairs:
                # Tam ad eslesmesi: onunde/arkasinda imaj adinin parcasi
                # olabilecek karakter olmamali. Aksi halde "alpine:3.8"
                # "courselabs/alpine:3.8" icindeki parcayi da degistirirdi.
                pat = re.compile(r"(?<![\w./@-])" + re.escape(src) + r"(?![\w.:@/-])")
                s, c = pat.subn(dst, s)
                n += c
            if n:
                total += n
                touched.append((p.relative_to(ROOT).as_posix(), n))
                if not args.dry_run:
                    p.write_text(s, encoding="utf-8", newline="")

    for rel, n in sorted(touched):
        print("  %-62s %d" % (rel[:62], n))
    print()
    print("%d dosyada %d referans%s" % (
        len(touched), total, " DEGISTIRILECEK" if args.dry_run else " degistirildi"))


if __name__ == "__main__":
    main()
