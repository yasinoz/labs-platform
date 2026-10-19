#!/usr/bin/env python3
"""Lab repolari icin dogrulama araci.

Upstream kaynagin derste patlamasina yol acan hatalari yakalar:
  * docker-compose v1 CLI cagrilari (v1 kaldirildi, komut artik 'docker compose')
  * compose dosyalarinda artik gereksiz 'version:' anahtari
  * pinlenmemis imajlar (:latest) - ders tekrar edilebilir olmali
  * VERSIONS.yaml'da 'was:' olarak isaretli ESKI imaj referanslari
  * eksik TR karsiligi olan dokumanlar
  * kirik goreli baglantilar
  * eksik/bozuk frontmatter
  * TR ile EN arasinda yapisal kayma (dusen adim, dusen kod blogu)

Kullanim:
    python lab-lint.py <repo-dizini>
    python lab-lint.py <repo-dizini> --only compose,links
    python lab-lint.py <repo-dizini> --json

Cikis kodu: hata varsa 1, temizse 0.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import miniyaml  # noqa: E402

CHECKS = ("compose", "pins", "stale", "i18n", "links", "frontmatter", "parity")

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})")


def split_code_blocks(text):
    """(prose, code) -> her biri (satir_no, metin) listesi."""
    prose, code, fence = [], [], None
    for n, line in enumerate(text.splitlines(), 1):
        m = FENCE.match(line)
        if m:
            tok = m.group(2)
            if fence is None:
                fence = tok
            elif line.strip().startswith(fence):
                fence = None
            continue
        (code if fence else prose).append((n, line))
    return prose, code


def read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    block = text[3:end].strip("\n")
    try:
        data = miniyaml.loads(block)
    except miniyaml.MiniYamlError:
        return "INVALID", text
    return data, text[end + 4:]


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, check, path, line, msg, fix=None):
        self.items.append({
            "level": level,
            "check": check,
            "file": str(path).replace("\\", "/"),
            "line": line,
            "message": msg,
            "fix": fix,
        })

    def error(self, *a, **k):
        self.add("ERROR", *a, **k)

    def warn(self, *a, **k):
        self.add("WARN", *a, **k)

    @property
    def errors(self):
        return [i for i in self.items if i["level"] == "ERROR"]


# ------------------------------------------------------------------ kontroller

# 'docker-compose' KOMUTU; 'docker-compose.yml' DOSYA ADI degil.
# Negatif ileri bakis dosya adi referanslarini disarida tutar.
COMPOSE_V1 = re.compile(r"\bdocker-compose(?![\w.-]*\.ya?ml)\b")


def check_compose_cli(rep, root, md_files, mentions=()):
    """Compose v1 Haziran 2023'te EOL oldu ve Docker Desktop ile gelmiyor:
    ogrencinin ilk komutu 'command not found' ile patliyor.

    mentions: v1'den bahseden (kullanmayan) dokumanlar - gocu anlatan
    metinler ve "v1 kullanmayin" uyarilari."""
    for f in md_files:
        rel = f.relative_to(root).as_posix()
        if rel in mentions:
            continue
        prose, code = split_code_blocks(read(f))
        for n, line in code + prose:
            if COMPOSE_V1.search(line):
                rep.error("compose", f.relative_to(root), n,
                          "docker-compose (v1 CLI) kullanilmis",
                          "bosluklu 'docker compose' (v2) olarak degistir")


def check_compose_version_key(rep, root, yaml_files):
    for f in yaml_files:
        text = read(f).lstrip()
        if not text:
            continue
        if re.match(r"^version\s*:", text.splitlines()[0]):
            rep.warn("compose", f.relative_to(root), 1,
                     "compose dosyasinda artik gereksiz 'version:' anahtari",
                     "satiri sil (Compose Spec bu alani yok sayar, uyari basar)")


IMAGE_REF = re.compile(r"""^[ \t-]*image\s*:\s*["']?([^\s"'#]+)""", re.M)
FROM_REF = re.compile(r"^\s*FROM\s+(?!--)(\S+)", re.M | re.I)


def plausible_ref(ref):
    """Yakalanan degerin gercekten bir imaj referansi olup olmadigini sorar.

    Iki yanlis pozitif kaynagi:
      * Helm sablonlari:  image: {{ .Values.apiImage }}
      * Ic ice image haritasi (Helm values.yaml):
            image:
              repository: foo
              tag: bar
        Bu durumda regex bir sonraki ANAHTARI ('repository:') yakalar.
    """
    if "{{" in ref or "}}" in ref:
        return False
    if ref.endswith(":"):          # YAML anahtari, imaj adi degil
        return False
    if ref.startswith(("$", "#")):
        return False
    return True


def collect_image_refs(yaml_files, dockerfiles):
    refs = []
    for f in yaml_files:
        text = read(f)
        for m in IMAGE_REF.finditer(text):
            ref = m.group(1)
            if not plausible_ref(ref):
                continue
            refs.append((f, text[:m.start()].count("\n") + 1, ref))
    for f in dockerfiles:
        text = read(f)
        for m in FROM_REF.finditer(text):
            refs.append((f, text[:m.start()].count("\n") + 1, m.group(1)))
    return refs


def split_tag(ref):
    """'registry:5000/app:1.2' -> ('registry:5000/app', '1.2')."""
    name, sep, tag = ref.rpartition(":")
    if not sep or "/" in tag:
        return ref, ""
    return name, tag


def unpinned_allowed(rules, rel, ref):
    """lint-exceptions.yaml 'allow_unpinned' kurallarina bakar."""
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        path = rule.get("path")
        if path and not rel.startswith(path):
            continue
        want = rule.get("ref")
        if want and want != ref:
            continue
        prefix = rule.get("ref_prefix")
        if prefix and not ref.startswith(prefix):
            continue
        if want or prefix:
            return True
    return False


def check_pins(rep, root, refs, intentional, stages, local_images,
               allow=(), placeholders=()):
    for f, line, ref in refs:
        if "${" in ref or ref.lower() in stages or ref in intentional:
            continue
        name, tag = split_tag(ref)
        if name in local_images or ref in local_images:
            continue
        if ref in placeholders:
            continue
        rel = f.relative_to(root).as_posix()
        if unpinned_allowed(allow, rel, name if not tag else ref):
            continue
        if not tag or tag == "latest":
            rep.error("pins", f.relative_to(root), line,
                      "imaj pinlenmemis: " + ref,
                      "tam surum etiketi ver (ders tekrar edilebilir olmali)")


def stale_map(versions):
    """VERSIONS.yaml icindeki her 'was:' alani eski referans kara listesidir."""
    out = {}

    def walk(node):
        if isinstance(node, dict):
            was, img, tag = node.get("was"), node.get("image"), node.get("tag")
            if was and img:
                out[str(was).strip()] = "{}:{}".format(img, tag)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(versions)
    return out


def check_stale(rep, root, refs, versions, intentional, allow=()):
    stale = stale_map(versions)
    by_base = {}
    for old, new in stale.items():
        by_base.setdefault(old.split(":")[0], new)
    for f, line, ref in refs:
        if ref in intentional or "${" in ref:
            continue
        # Pinlenmemis olmasina izin verilen referanslar (ornegin kasitli
        # ogretim noktalari) surum matrisiyle de karsilastirilmaz.
        if unpinned_allowed(allow, f.relative_to(root).as_posix(), ref):
            continue
        if ref in stale:
            rep.error("stale", f.relative_to(root), line,
                      "eski surum: " + ref, stale[ref] + " kullan")
            continue
        base, _, tag = ref.partition(":")
        want = by_base.get(base)
        if not want or ref == want:
            continue
        want_tag = want.partition(":")[2]
        # '10.0-alpine' matristeki '10.0' ile ayni surum, farkli varyant.
        # Varyant secimi lab'in isi: alpine/slim/noble tercihine karismiyoruz.
        if want_tag and tag.startswith(want_tag):
            continue
        rep.warn("stale", f.relative_to(root), line,
                 "surum matrisiyle uyusmuyor: " + ref, want + " kullan")


# Iki dilli olmasi beklenmeyen dosyalar: repo meta dokumanlari.
# (ATTRIBUTION zaten iki dilli tek dosya; MODERNIZASYON Turkce yazildi.)
SKIP_I18N = {"ATTRIBUTION.md", "LICENSE.md", "CONTRIBUTING.md",
             "CHANGELOG.md", "MODERNIZASYON.md", "README.md"}


def check_i18n(rep, root, md_files):
    md_set = set(md_files)
    for f in md_files:
        if f.name.endswith(".tr.md"):
            want = f.with_name(f.name[:-6] + ".md")
            if want not in md_set:
                rep.warn("i18n", f.relative_to(root), 0,
                         "EN karsiligi yok (yetim TR dosyasi)", None)
        else:
            if f.name in SKIP_I18N:
                continue
            want = f.with_name(f.name[:-3] + ".tr.md")
            if want not in md_set:
                rep.error("i18n", f.relative_to(root), 0, "TR karsiligi yok",
                          want.relative_to(root).as_posix() + " olustur")


# ([^)\s]*) : BOS parantez de yakalanir. Upstream'de uc tane
# "[metin]()" vardi; eski desen en az bir karakter istedigi icin
# bunlari hic gormuyordu.
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]*)\)")


def check_links(rep, root, md_files):
    for f in md_files:
        prose, _ = split_code_blocks(read(f))
        for n, line in prose:
            for target in LINK.findall(line):
                if not target.strip():
                    rep.error("links", f.relative_to(root), n,
                              "bos baglanti hedefi: [...]()",
                              "gercek bir URL ver ya da baglantiyi kaldir")
                    continue
                if target.startswith(("http://", "https://", "#", "mailto:", "//")):
                    continue
                clean = target.split("#")[0].split("?")[0]
                if not clean:
                    continue
                if not (f.parent / clean).exists():
                    rep.error("links", f.relative_to(root), n,
                              "kirik goreli baglanti: " + target, None)


REQUIRED_FM = ("title", "lang", "slug", "section", "order", "status")
VALID_STATUS = ("upstream", "needs-review", "updated")


def frontmatter_required(rel):
    """Frontmatter yalnizca sitenin yayinladigi dokumanlarda zorunlu.

    Kapsam: labs/**/README*.md, kok index*.md, setup/README*.md
    Kapsam disi: hackathon projeleri, setup-lab (sinif VM kurulumu), repo
    meta dosyalari. Bunlar manifest.json'da yok, dolayisiyla sitede de yok.
    """
    if rel.startswith("labs/"):
        return True
    if "/" not in rel and rel.split(".")[0] == "index":
        return True
    if rel.startswith("setup/") and rel.split("/")[-1].split(".")[0] == "README":
        return True
    return False


def check_frontmatter(rep, root, md_files):
    for f in md_files:
        stem = f.name.split(".")[0]
        if stem not in ("README", "index"):
            continue
        if f.parent == root and stem == "README":
            continue
        if not frontmatter_required(f.relative_to(root).as_posix()):
            continue
        fm, _ = parse_frontmatter(read(f))
        rel = f.relative_to(root)
        if fm is None:
            rep.error("frontmatter", rel, 1, "frontmatter yok",
                      "docs/REPO-YAPISI.md'deki blogu ekle")
            continue
        if fm == "INVALID" or not isinstance(fm, dict):
            rep.error("frontmatter", rel, 1, "frontmatter ayristirilamadi", None)
            continue
        for key in REQUIRED_FM:
            if key not in fm:
                rep.error("frontmatter", rel, 1, "frontmatter alani eksik: " + key, None)
        if "status" in fm and fm.get("status") not in VALID_STATUS:
            rep.error("frontmatter", rel, 1,
                      "gecersiz status: {!r}".format(fm.get("status")),
                      "su degerlerden biri: " + ", ".join(VALID_STATUS))
        want_lang = "tr" if f.name.endswith(".tr.md") else "en"
        if fm.get("lang") and fm.get("lang") != want_lang:
            rep.error("frontmatter", rel, 1,
                      "lang alani dosya adiyla uyusmuyor: {} != {}".format(fm["lang"], want_lang),
                      None)


TASK = re.compile("\U0001F4CB")


def check_parity(rep, root, md_files):
    """TR dokumani EN'deki adim sayisini korumali - cevirmen adim dusurmesin."""
    md_set = set(md_files)
    for f in md_files:
        if f.name.endswith(".tr.md"):
            continue
        tr = f.with_name(f.name[:-3] + ".tr.md")
        if tr not in md_set:
            continue
        en_text, tr_text = read(f), read(tr)
        _, en_code = split_code_blocks(en_text)
        _, tr_code = split_code_blocks(tr_text)
        checks = (
            ("kod blogu satiri", len(en_code), len(tr_code)),
            ("gorev isareti", len(TASK.findall(en_text)), len(TASK.findall(tr_text))),
            ("<details> blogu", en_text.count("<details>"), tr_text.count("<details>")),
        )
        for label, a, b in checks:
            if a != b:
                rep.warn("parity", tr.relative_to(root), 0,
                         "{} sayisi EN ile uyusmuyor (EN={}, TR={})".format(label, a, b),
                         "ceviri sirasinda adim dusmus olabilir")


# ------------------------------------------------------------------ toplama

# "platform"/".platform": CI'da yan yana checkout edilen arac reposu.
# Yanlislikla lab reposunun icine alinirsa platformun kendi
# VERSIONS.yaml'i pinlenmemis imaj gibi gorunur.
SKIP_DIRS = {".git", "node_modules", ".github", "img", ".vscode",
             "obj", "bin", "platform", ".platform"}


def helm_chart_dirs(root):
    """Chart.yaml iceren dizinler = Helm chart'i.

    Chart icindeki imajlar values.yaml ile yapilandirilir ve Chart.yaml'daki
    'artifacthub.io/images' gibi ek aciklamalar dagitilmayan metadata'dir;
    ikisinde de pin kontrolu yanlis alarm uretir.
    """
    dirs = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "Chart.yaml" in filenames:
            dirs.append(Path(dirpath).relative_to(root).as_posix())
    return dirs


# Blok sonu: 0. kolonda baslayan ve tire OLMAYAN bir karakter. Kustomize
# liste ogeleri ('- name: x') 0. kolonda basladigi icin basit '^\S' bitisi
# blogu ilk ogede keserdi.
KUSTOMIZE_IMAGES = re.compile(r"^images:[ \t]*$(.*?)(?=^[^\s-]|\Z)", re.M | re.S)
KUSTOMIZE_NAME = re.compile(r"^\s*-\s*name:\s*(\S+)", re.M)


def kustomize_placeholders(root):
    """kustomization.yaml 'images:' donusturucusunun yer tutucu adlari.

    Kustomize tabanlarinda 'image: image-of-the-day' gibi ETIKETSIZ adlar
    bilincli yer tutucudur; kustomization.yaml bunlari newName/newTag ile
    pinli imaja cevirir. Pin uyarisi vermek yanlis olur.
    """
    names = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn not in ("kustomization.yaml", "kustomization.yml"):
                continue
            text = read(Path(dirpath) / fn)
            block = KUSTOMIZE_IMAGES.search(text)
            if not block:
                continue
            for m in KUSTOMIZE_NAME.finditer(block.group(1)):
                names.add(m.group(1))
    return names


def gather(root, skip_paths=()):
    md, yml, dockerfiles = [], [], []
    skip_paths = [s.replace("\\", "/").rstrip("/") for s in skip_paths]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        if any(rel_dir == s or rel_dir.startswith(s + "/") for s in skip_paths):
            dirnames[:] = []
            continue
        for fn in filenames:
            p = Path(dirpath) / fn
            low = fn.lower()
            if low.endswith(".md"):
                md.append(p)
            elif low.endswith((".yml", ".yaml")):
                yml.append(p)
            elif low.startswith("dockerfile"):
                dockerfiles.append(p)
    return sorted(md), sorted(yml), sorted(dockerfiles)


def build_stage_names(dockerfiles):
    names = set()
    for f in dockerfiles:
        for m in re.finditer(r"^\s*FROM\s+\S+\s+AS\s+(\S+)", read(f), re.M | re.I):
            names.add(m.group(1).lower())
    return names


def local_build_images(yaml_files):
    """compose icinde 'build:' ile uretilen imajlar registry'de aranmaz."""
    names = set()
    for f in yaml_files:
        text = read(f)
        blocks = re.split(r"\n(?=\s{2}\w)", text)
        for b in blocks:
            if re.search(r"^\s+build\s*:", b, re.M):
                m = IMAGE_REF.search(b)
                if m:
                    ref = m.group(1)
                    names.add(ref)
                    names.add(split_tag(ref)[0])
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--versions", default=None)
    ap.add_argument("--only", default=None, help="virgulle: " + ",".join(CHECKS))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--warn-as-error", action="store_true")
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    if not root.is_dir():
        sys.exit("dizin yok: " + str(root))

    vpath = (Path(args.versions) if args.versions
             else Path(__file__).resolve().parents[1] / "VERSIONS.yaml")
    versions = miniyaml.load(vpath) if vpath.exists() else {}
    intentional = {str(x.get("image"))
                   for x in (versions.get("intentionally_vulnerable") or [])}

    epath = Path(__file__).resolve().parents[1] / "lint-exceptions.yaml"
    exc = miniyaml.load(epath) if epath.exists() else {}
    mentions = set(exc.get("compose_v1_mentions") or [])
    allow_unpinned = exc.get("allow_unpinned") or []
    skip_paths = [str(p) for p in (exc.get("skip_paths") or [])]

    charts = helm_chart_dirs(root)
    placeholders = kustomize_placeholders(root)
    only = set(args.only.split(",")) if args.only else set(CHECKS)
    md, yml, dfs = gather(root, list(skip_paths) + charts)
    rep = Report()
    refs = collect_image_refs(yml, dfs)
    stages = build_stage_names(dfs)
    local = local_build_images(yml)

    if "compose" in only:
        check_compose_cli(rep, root, md, mentions)
        check_compose_version_key(rep, root, yml)
    if "pins" in only:
        check_pins(rep, root, refs, intentional, stages, local,
                   allow_unpinned, placeholders)
    if "stale" in only:
        check_stale(rep, root, refs, versions, intentional, allow_unpinned)
    if "i18n" in only:
        check_i18n(rep, root, md)
    if "links" in only:
        check_links(rep, root, md)
    if "frontmatter" in only:
        check_frontmatter(rep, root, md)
    if "parity" in only:
        check_parity(rep, root, md)

    if args.json:
        print(json.dumps({"repo": root.name, "findings": rep.items},
                         ensure_ascii=False, indent=2))
    else:
        by_check = {}
        for i in rep.items:
            by_check.setdefault(i["check"], []).append(i)
        print("\n  {}  -  {} markdown, {} yaml, {} Dockerfile, {} imaj referansi"
              .format(root.name, len(md), len(yml), len(dfs), len(refs)))
        extra = []
        if charts:
            extra.append("{} Helm chart dizini atlandi".format(len(charts)))
        if placeholders:
            extra.append("{} kustomize yer tutucusu".format(len(placeholders)))
        print(("  " + ", ".join(extra) + "\n") if extra else "")
        for check in CHECKS:
            if check not in only:
                continue
            items = by_check.get(check)
            if not items:
                print("  [ok]    " + check)
                continue
            errs = sum(1 for i in items if i["level"] == "ERROR")
            tag = "HATA" if errs else "uyari"
            print("  [{}]  {}: {} bulgu ({} hata)".format(tag, check, len(items), errs))
            for i in items[:300]:
                loc = "{}:{}".format(i["file"], i["line"]) if i["line"] else i["file"]
                print("          {:5} {}  {}".format(i["level"], loc, i["message"]))
                if i["fix"]:
                    print("                -> " + i["fix"])
        print("\n  toplam: {} bulgu, {} hata\n".format(len(rep.items), len(rep.errors)))

    bad = rep.items if args.warn_as_error else rep.errors
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
