#!/usr/bin/env python3
"""Lab repolarina mekanik modernizasyon uygular.

Yaptiklari:
  1. 'docker-compose' (v1 CLI) -> 'docker compose' (v2). Dosya adi
     referanslarina (docker-compose.yml) DOKUNMAZ.
  2. Compose dosyalarindan artik gereksiz 'version:' anahtarini kaldirir.
  3. rewrites.yaml + VERSIONS.yaml 'was:' alanlarina gore eski imaj
     referanslarini gunceller.
  4. rewrites.yaml 'text:' bolumundeki tam dizgi degisikliklerini uygular.

Kasitli olarak eski birakilan imajlar (VERSIONS.yaml icindeki
intentionally_vulnerable) ve rewrites.yaml icindeki exempt_paths atlanir.

Arac FIKIRSIZDIR: yalnizca tam eslesmeleri degistirir, tahmin yapmaz.
Geri kalan (anlatim metni, ekran yonlendirmeleri, surum farki yaratan
davranis degisiklikleri) insan elinde kalir.

Kullanim:
    python modernize.py <repo-dizini> --dry-run      # sadece rapor
    python modernize.py <repo-dizini> --apply        # dosyalari yaz
    python modernize.py <repo> --apply --only images
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import miniyaml  # noqa: E402

PLATFORM = Path(__file__).resolve().parents[1]
STEPS = ("compose-cli", "compose-version", "images", "text")

SKIP_DIRS = {".git", "node_modules", ".vscode", "obj", "bin", "img"}
TEXT_EXT = {".md", ".yml", ".yaml", ".json", ".conf", ".env", ".cs", ".java",
            ".go", ".xml", ".csproj", ".html", ".css", ".ps1", ".sh", ".mod"}

# 'docker-compose' komutu: ardindan .yml/.yaml gelen dosya adlarini dislar.
COMPOSE_CLI = re.compile(r"\bdocker-compose(?![\w.-]*\.ya?ml)\b")
COMPOSE_VERSION_KEY = re.compile(r"\A(\s*#[^\n]*\n|\s*\n)*version\s*:\s*[\"']?[\d.]+[\"']?[ \t]*\n+")


def is_textfile(p: Path) -> bool:
    return p.suffix.lower() in TEXT_EXT or p.name.lower().startswith("dockerfile") \
        or p.name in ("Jenkinsfile", "Jenkinsfile.original", "Pipfile.lock")


def load_rules():
    rw = miniyaml.load(PLATFORM / "rewrites.yaml")
    versions = miniyaml.load(PLATFORM / "VERSIONS.yaml")

    images = dict(rw.get("images") or {})
    # VERSIONS.yaml 'was:' alanlari da kural uretir; rewrites.yaml onceliklidir.
    def walk(node):
        if isinstance(node, dict):
            was, img, tag = node.get("was"), node.get("image"), node.get("tag")
            if was and img:
                images.setdefault(str(was).strip(), "{}:{}".format(img, tag))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(versions)

    intentional = {str(x.get("image"))
                   for x in (versions.get("intentionally_vulnerable") or [])}
    for img in intentional:
        images.pop(img, None)

    # Compose v1'den BAHSEDEN (kullanmayan) dokumanlar: gocu anlatan tablolar
    # ve ogrenciye "v1 kullanmayin" diyen uyarilar. Bunlarda yeniden yazma
    # metni anlamsiz hale getirir - lint araciyla ayni listeyi okuyoruz.
    epath = PLATFORM / "lint-exceptions.yaml"
    exc = miniyaml.load(epath) if epath.exists() else {}

    return {
        "images": images,
        "text": dict(rw.get("text") or {}),
        "exempt": [str(p).strip() for p in (rw.get("exempt_paths") or [])],
        "intentional": intentional,
        "compose_mentions": {str(p).strip()
                             for p in (exc.get("compose_v1_mentions") or [])},
    }


def is_exempt(rel: str, exempt) -> bool:
    rel = rel.replace("\\", "/")
    return any(rel == e or rel.startswith(e.rstrip("/") + "/") or rel.startswith(e)
               for e in exempt)


VENDOR_MIN_LINES = 300


def is_vendored_manifest(path: Path, text: str) -> bool:
    """Upstream projeden oldugu gibi kopyalanmis kurulum manifesti mi?

    Boyle dosyalarda SADECE imaj etiketini degistirmek calisan bir kurulum
    vermez - CRD semasi, RBAC kurallari ve webhook yapilandirmasi surumler
    arasinda degisir. Sessizce bozulan bir manifest, acikca eski olandan
    daha kotudur; bu yuzden dokunmayip "komple yenilenmeli" diye raporlariz.
    """
    if path.suffix.lower() not in (".yml", ".yaml"):
        return False
    if text.count("\n") < VENDOR_MIN_LINES:
        return False
    return ("kind: CustomResourceDefinition" in text
            or text.count("\n---") > 20
            or "app.kubernetes.io/managed-by: Helm" in text)


def apply_compose_cli(text):
    return COMPOSE_CLI.subn("docker compose", text)


def apply_compose_version(text, path: Path):
    if path.suffix.lower() not in (".yml", ".yaml"):
        return text, 0
    low = text.lower()
    if "services:" not in low:
        return text, 0
    new, n = COMPOSE_VERSION_KEY.subn("", text, count=1)
    return new, n


def apply_images(text, images, intentional):
    """Imaj referanslarini degistirir. Uzun anahtarlar once denenir ki
    'openjdk:11-jre-slim' , 'openjdk:11' tarafindan parcalanmasin."""
    total = Counter()
    for old in sorted(images, key=len, reverse=True):
        new = images[old]
        if old in intentional or old == new:
            continue
        # Sinir: imaj referansindan hemen sonra harf/rakam/nokta/tire gelmemeli,
        # yoksa 'alpine:3.13' , 'alpine:3.131' icinde eslesirdi.
        #
        # ETIKETSIZ kaynak referanslari icin ':' de sinira dahil. Aksi halde
        # kural idempotent olmuyor: 'courselabs/x' -> 'courselabs/x:25.03'
        # donusumu bir sonraki calistirmada 'courselabs/x:25.03:25.03'
        # uretiyor, cunku ':' sinir sayilmadigi icin ad tekrar esliyor.
        tail = r"(?![\w.\-:])" if ":" not in old else r"(?![\w.-])"
        pat = re.compile(r"(?<![\w./:-])" + re.escape(old) + tail)
        text, n = pat.subn(new, text)
        if n:
            total[old + " -> " + new] += n
    return text, total


def apply_text(text, rules):
    total = Counter()
    for old in sorted(rules, key=len, reverse=True):
        new = rules[old]
        if old == new:
            continue
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            total[old + " -> " + new] += n
    return text, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--apply", action="store_true", help="dosyalari gercekten yaz")
    ap.add_argument("--dry-run", action="store_true", help="varsayilan: sadece rapor")
    ap.add_argument("--only", default=None, help="virgulle: " + ",".join(STEPS))
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    if not root.is_dir():
        sys.exit("dizin yok: " + str(root))
    only = set(args.only.split(",")) if args.only else set(STEPS)
    write = args.apply and not args.dry_run

    rules = load_rules()
    counts = Counter()
    image_detail = Counter()
    text_detail = Counter()
    touched = []
    skipped = []
    vendored = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_textfile(path):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if is_exempt(rel, rules["exempt"]):
            skipped.append(rel)
            continue

        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if is_vendored_manifest(path, original):
            vendored.append(rel)
            continue
        text = original
        local = Counter()

        if "compose-cli" in only and rel not in rules["compose_mentions"]:
            text, n = apply_compose_cli(text)
            local["compose-cli"] += n
        if "compose-version" in only:
            text, n = apply_compose_version(text, path)
            local["compose-version"] += n
        if "images" in only:
            text, det = apply_images(text, rules["images"], rules["intentional"])
            image_detail.update(det)
            local["images"] += sum(det.values())
        if "text" in only:
            text, det = apply_text(text, rules["text"])
            text_detail.update(det)
            local["text"] += sum(det.values())

        if text != original:
            counts.update(local)
            touched.append((rel, dict((k, v) for k, v in local.items() if v)))
            if write:
                path.write_text(text, encoding="utf-8", newline="")

    mode = "UYGULANDI" if write else "DENEME (--apply ile yaz)"
    print("\n  {}  —  {}\n".format(root.name, mode))
    print("  degisen dosya: {}   muaf tutulan: {}".format(len(touched), len(skipped)))
    for step in STEPS:
        if counts.get(step):
            print("    {:18} {} degisiklik".format(step, counts[step]))
    if image_detail:
        print("\n  imaj degisiklikleri:")
        for k, v in image_detail.most_common():
            print("    {:3}x  {}".format(v, k))
    if text_detail:
        print("\n  metin degisiklikleri:")
        for k, v in text_detail.most_common():
            print("    {:3}x  {}".format(v, k))
    if skipped:
        print("\n  kasitli eski birakilan yollar (dokunulmadi):")
        for item in sorted(set(skipped))[:20]:
            print("    " + item)
    if vendored:
        print("\n  !! VENDOR'LANMIS KURULUM MANIFESTI - mekanik yamaya UYGUN DEGIL")
        print("     (etiket degistirmek calisan kurulum vermez; komple yenilenmeli)")
        for item in sorted(set(vendored)):
            print("    " + item)
    print("\n  dosya basina:")
    for rel, local in touched[:80]:
        print("    {:62} {}".format(rel, local))
    if len(touched) > 80:
        print("    ... ve {} dosya daha".format(len(touched) - 80))
    print()


if __name__ == "__main__":
    main()
