#!/usr/bin/env python3
"""Vendor'lanmis upstream kurulum manifestlerini guncel surumle degistirir.

manifests.yaml icindeki her kayit icin:
  1. URL'den manifesti indirir (dogrulama: bos degil, YAML gibi gorunuyor)
  2. hedef yola yazar
  3. eski dosyayi siler
  4. repo icindeki dokumanlarda eski yol referanslarini yenisiyle degistirir

Neden ayri arac: bu dosyalar mekanik yamaya uygun degil. Sadece imaj
etiketini degistirmek calisan kurulum vermez - CRD/RBAC/webhook yapisi
surumler arasinda degisir.

Kullanim:
    python fetch-manifests.py --repo-root ..            # tum repolar, deneme
    python fetch-manifests.py --repo-root .. --apply
    python fetch-manifests.py --repo-root .. --apply --only argocd,gatekeeper
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import miniyaml  # noqa: E402

PLATFORM = Path(__file__).resolve().parents[1]
TEXT_EXT = {".md", ".yml", ".yaml", ".json", ".sh", ".ps1"}


def download(url: str, timeout: int = 90) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "sudo2go-labs/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
    if len(data) < 500:
        raise ValueError("indirilen icerik beklenmeyecek kadar kucuk ({} bayt)".format(len(data)))
    if "apiVersion:" not in data:
        raise ValueError("YAML manifest gibi gorunmuyor ('apiVersion:' yok)")
    return data


def update_references(repo: Path, old_rel: str, new_rel: str, apply: bool):
    """Dokumanlardaki eski manifest yolunu yenisiyle degistirir."""
    old_name = Path(old_rel).name
    new_name = Path(new_rel).name
    hits = []
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXT:
            continue
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if old_rel not in text and old_name not in text:
            continue
        new_text = text.replace(old_rel, new_rel).replace(old_name, new_name)
        if new_text != text:
            hits.append((path.relative_to(repo).as_posix(),
                         text.count(old_rel) + text.count(old_name)))
            if apply:
                path.write_text(new_text, encoding="utf-8", newline="")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..",
                    help="lab repolarinin bulundugu ust dizin")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default=None, help="virgulle manifest id'leri")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    spec = miniyaml.load(PLATFORM / "manifests.yaml")
    wanted = set(args.only.split(",")) if args.only else None

    print("\n  {}\n".format("UYGULANIYOR" if args.apply else "DENEME (--apply ile yaz)"))
    rc = 0

    for entry in spec.get("manifests") or []:
        mid = entry["id"]
        if wanted and mid not in wanted:
            continue
        try:
            body = download(entry["url"])
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            print("  [HATA] {}: indirilemedi - {}".format(mid, exc))
            rc = 1
            continue

        lines = body.count("\n") + 1
        print("  {} {}  ({} satir, {:.0f} KB)".format(mid, entry["version"], lines, len(body) / 1024))

        for repo_name in entry.get("repos") or []:
            repo = root / repo_name
            if not repo.is_dir():
                print("      - {}: repo yok, atlandi".format(repo_name))
                continue
            target = repo / entry["target"]
            old = repo / entry["replaces"]
            status = []
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8", newline="")
                status.append("yazildi")
                if old.exists() and old.resolve() != target.resolve():
                    old.unlink()
                    status.append("eski silindi")
            else:
                status.append("yazilacak")
                if old.exists():
                    status.append("eski silinecek: " + entry["replaces"])
            refs = update_references(repo, entry["replaces"], entry["target"], args.apply)
            total = sum(n for _, n in refs)
            print("      - {:14} {} | {} dosyada {} yol referansi".format(
                repo_name, ", ".join(status), len(refs), total))
            for rel, n in refs[:6]:
                print("          {} ({})".format(rel, n))

    print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
