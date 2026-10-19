#!/usr/bin/env python3
"""sections.yaml -> manifest.json (ve istege bagli frontmatter enjeksiyonu).

manifest.json, WordPress eklentisinin okudugu makine-okunur lab dizinidir:
hangi lab var, hangi dilde hazir, hangi bolumde, ne kadar suruyor, durumu ne.

Dil durumu DOSYA VARLIGINDAN okunur, elle beyan edilmez: README.tr.md yoksa
o lab TR'de yayinlanmaz. Boylece "cevrildi" diye isaretlenip aslinda
cevrilmemis lab yayina cikamaz.

Kullanim:
    python make-manifest.py <repo>                     # manifest.json yaz
    python make-manifest.py <repo> --write-frontmatter # README'lere frontmatter da bas
    python make-manifest.py <repo> --check             # fark varsa 1 don (CI icin)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import miniyaml  # noqa: E402

DOC_KINDS = ("README", "hints", "solution")


def doc_paths(lab_dir: Path, lang: str):
    """Bir lab dizinindeki mevcut dokumanlari dile gore dondurur."""
    suffix = ".tr.md" if lang == "tr" else ".md"
    out = {}
    for kind in DOC_KINDS:
        p = lab_dir / (kind + suffix)
        if p.exists():
            out[kind.lower()] = p
    return out


def frontmatter_block(lab, section, lang, repo_rel):
    title = lab["titles"].get(lang) or lab["titles"]["en"]
    requires = lab.get("requires") or []
    lines = [
        "---",
        "title: " + title,
        "lang: " + lang,
        "slug: " + lab["slug"],
        "section: " + section["slug"],
        "order: " + str(lab["order"]),
        "duration: " + str(lab.get("duration") or 0),
        "requires: [" + ", ".join(requires) + "]",
        "status: " + lab.get("status", "needs-review"),
        "upstream: " + repo_rel,
        "---",
        "",
    ]
    return "\n".join(lines)


def strip_frontmatter(text):
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:].lstrip("\n")


MARK_START = "<!-- labs:start -->"
MARK_END = "<!-- labs:end -->"

LABELS = {
    "en": {"lab": "Lab", "time": "Time", "needs": "Needs", "min": "min",
           "en_only": " _(EN)_"},
    "tr": {"lab": "Lab", "time": "Süre", "needs": "Gerekir", "min": "dk",
           "en_only": " _(EN)_"},
}


def render_index_tables(manifest, lang):
    """index.md / index.tr.md icindeki lab tablolarini uretir.

    Elle tutulan tablo, 74 lablik bir yapida kacinilmaz olarak gercekten
    kayar: yeni lab eklenir tabloya girmez, ya da cevrilmemis bir lab'a
    .tr.md baglantisi verilip kirik link olusur. Burada tablo dosya
    varligindan uretiliyor, yani kayamaz.
    """
    L = LABELS[lang]
    out = [MARK_START, ""]
    for section in manifest["sections"]:
        titles = section.get("titles") or {}
        out.append("## " + (titles.get(lang) or titles.get("en") or section["slug"]))
        out.append("")
        summary = (section.get("summaries") or {}).get(lang)
        if summary:
            out.append(summary)
            out.append("")
        out.append("| {} | {} | {} |".format(L["lab"], L["time"], L["needs"]))
        out.append("|---|---|---|")
        for lab in section["labs"]:
            lt = lab.get("titles") or {}
            title = lt.get(lang) or lt.get("en") or lab["slug"]
            has_lang = lang in (lab.get("langs") or [])
            doc = (lab.get("docs", {}).get(lang if has_lang else "en", {})
                   .get("readme", lab["path"] + "/README.md"))
            suffix = "" if has_lang else L["en_only"]
            dur = lab.get("duration") or 0
            needs = ", ".join(lab.get("requires") or []) or "-"
            out.append("| [{}]({}){} | {} {} | {} |".format(
                title, doc, suffix, dur, L["min"], needs))
        out.append("")
    out.append(MARK_END)
    return "\n".join(out)


def update_index(repo, manifest, lang):
    name = "index.tr.md" if lang == "tr" else "index.md"
    path = repo / name
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if MARK_START not in text or MARK_END not in text:
        return "atlandi (isaretci yok: {} / {})".format(MARK_START, MARK_END)
    head, _, rest = text.partition(MARK_START)
    _, _, tail = rest.partition(MARK_END)
    new = head + render_index_tables(manifest, lang) + tail
    if new == text:
        return "guncel"
    path.write_text(new, encoding="utf-8", newline="")
    return "guncellendi"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--write-frontmatter", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default="manifest.json")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    spec_path = repo / "sections.yaml"
    if not spec_path.exists():
        sys.exit("sections.yaml yok: " + str(spec_path))
    spec = miniyaml.load(spec_path)
    track = spec["track"]

    manifest = {
        "schema": 1,
        "generated": date.today().isoformat(),
        "track": {
            "slug": track["slug"],
            "titles": track["titles"],
            "summaries": track.get("summaries") or {},
        },
        "repo": track["repo"],
        "raw_base": "https://raw.githubusercontent.com/{}/{}/{}".format(
            track["repo"]["owner"], track["repo"]["name"], track["repo"]["branch"]),
        "web_base": "https://github.com/{}/{}/blob/{}".format(
            track["repo"]["owner"], track["repo"]["name"], track["repo"]["branch"]),
        "setup": {},
        "languages": [],
        "sections": [],
    }

    # Kurulum dokumani her dil icin ayri
    for lang in ("en", "tr"):
        p = repo / "setup" / ("README.tr.md" if lang == "tr" else "README.md")
        if p.exists():
            manifest["setup"][lang] = p.relative_to(repo).as_posix()

    langs_seen, written, stats = set(), [], {"total": 0, "en": 0, "tr": 0, "by_status": {}}

    for section in sorted(spec.get("sections") or [], key=lambda s: s["order"]):
        sec_entry = {
            "slug": section["slug"],
            "order": section["order"],
            "titles": section["titles"],
            "summaries": section.get("summaries") or {},
            "labs": [],
        }
        for lab in sorted(section.get("labs") or [], key=lambda x: x["order"]):
            lab_dir = repo / "labs" / lab["slug"]
            if not lab_dir.is_dir():
                print("  [atlandi] dizin yok: labs/" + lab["slug"])
                continue
            stats["total"] += 1
            entry = {
                "slug": lab["slug"],
                "order": lab["order"],
                "titles": lab["titles"],
                "duration": lab.get("duration") or 0,
                "requires": lab.get("requires") or [],
                "status": lab.get("status", "needs-review"),
                "path": ("labs/" + lab["slug"]),
                "docs": {},
            }
            for lang in ("en", "tr"):
                docs = doc_paths(lab_dir, lang)
                if not docs.get("readme"):
                    continue
                langs_seen.add(lang)
                stats[lang] += 1
                entry["docs"][lang] = {
                    k: v.relative_to(repo).as_posix() for k, v in docs.items()
                }
                if args.write_frontmatter:
                    p = docs["readme"]
                    text = p.read_text(encoding="utf-8")
                    body = strip_frontmatter(text)
                    block = frontmatter_block(lab, section, lang,
                                              "labs/" + lab["slug"])
                    new = block + body
                    if new != text:
                        p.write_text(new, encoding="utf-8", newline="")
                        written.append(p.relative_to(repo).as_posix())
            entry["langs"] = sorted(entry["docs"])
            st = entry["status"]
            stats["by_status"][st] = stats["by_status"].get(st, 0) + 1
            sec_entry["labs"].append(entry)
        manifest["sections"].append(sec_entry)

    manifest["languages"] = sorted(langs_seen) or ["en"]
    manifest["stats"] = stats

    out_path = repo / args.out
    new_json = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        old = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
        # 'generated' alani her gun degisir; karsilastirmadan cikar
        norm = lambda s: "\n".join(                                # noqa: E731
            l for l in s.splitlines() if '"generated"' not in l)
        if norm(old) != norm(new_json):
            print("  manifest.json guncel DEGIL - 'make-manifest.py <repo>' calistir")
            sys.exit(1)
        print("  manifest.json guncel")
        sys.exit(0)

    out_path.write_text(new_json, encoding="utf-8", newline="")

    index_status = {}
    for lang in ("en", "tr"):
        status = update_index(repo, manifest, lang)
        if status:
            index_status["index.tr.md" if lang == "tr" else "index.md"] = status

    print("\n  {} -> {}".format(repo.name, args.out))
    for name, status in sorted(index_status.items()):
        print("    {:14} {}".format(name, status))
    print("    lab: {}  |  EN: {}  TR: {}".format(stats["total"], stats["en"], stats["tr"]))
    print("    durum: " + ", ".join("{}={}".format(k, v) for k, v in sorted(stats["by_status"].items())))
    print("    diller: " + ", ".join(manifest["languages"]))
    if written:
        print("    frontmatter yazilan: {} dosya".format(len(written)))
    missing_tr = stats["total"] - stats["tr"]
    if missing_tr:
        print("    !! TR cevirisi bekleyen lab: {}".format(missing_tr))
    print()


if __name__ == "__main__":
    main()
