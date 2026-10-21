#!/usr/bin/env python3
"""Lablarda CEKILEN container imajlarini toplar.

Neden: lablardaki imajlarin buyuk cogunlugu Docker Hub'dan geliyor ve
Docker Hub anonim cekmeyi IP basina 6 saatte 100 istekle sinirliyor.
Tek bir ogrenci bir track'i bastan sona yaparken bu siniri tek basina
asabiliyor; ayni NAT arkasindaki bir sinif ilk dakikalarda doldurup
"toomanyrequests" aliyor. Bu liste, imajlari GHCR'a aynalayan is
akisinin girdisi (GHCR'da anonim cekme siniri yok).

Listeye GIRMEYENLER:
  - compose'da ayni servis hem image hem build tasiyorsa: lab sirasinda
    derleniyor, aynalanacak bir sey yok
  - hackathon/* gibi yalnizca lab icinde uretilen adlar
  - Docker Hub disindaki registry'ler (quay.io, mcr.microsoft.com,
    gcr.io, ghcr.io, docker.elastic.co ...): ayni sinira tabi degiller

Kullanim:
  python _platform/tools/collect-images.py            # listeyi yaz
  python _platform/tools/collect-images.py --print    # ekrana bas
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
TRACKS = ("DevSecOps", "Docker", "Kubernetes", "Observability")
OUT = ROOT / "_platform" / "mirror" / "images.txt"

# Digest'e sabitlenmis referanslar da kapsaniyor
# (courselabs/fulfilment-api@sha256:...). Bunlar da Docker Hub'dan
# cekiliyor; disarida birakmak, aynalamanin amacini bosa cikarirdi.
IMG_RE = re.compile(
    r"^[a-z0-9][a-z0-9._/-]*(:[\w.][\w.-]*)?(@sha256:[a-f0-9]{64})?$", re.I)
SKIP_RE = re.compile(r"^(scratch$|\$|\{\{|<)", re.I)
PORT_RE = re.compile(r"^\d+(:\d+)+$")

NON_HUB = ("ghcr.io/", "quay.io/", "gcr.io/", "k8s.gcr.io/", "registry.k8s.io/",
           "mcr.microsoft.com/", "docker.elastic.co/", "public.ecr.aws/",
           "registry.gitlab.com/")

LOCAL_ONLY = ("hackathon/", "labs/")

# "docker run -p 8010:80 nginx" gibi komutlarda bayraklarin DEGERLERI
# imaj sanilmasin diye: bu bayraklardan sonraki token atlanir.
VALUE_FLAGS = {
    "-p", "--publish", "-v", "--volume", "-e", "--env", "--name", "--network",
    "--net", "-u", "--user", "-w", "--workdir", "--restart", "--entrypoint",
    "--mount", "--label", "-l", "--add-host", "--env-file", "--memory", "-m",
    "--cpus", "--link", "--device", "--health-cmd", "--platform", "--pull",
}


def is_hub(img):
    """Imaj Docker Hub'dan mi cekiliyor?

    "docker.io/" oneki DOCKER HUB'IN KENDISIDIR; host adinda nokta
    oldugu icin baska registry sanmak bu imajlari aynalama disinda
    birakiyordu.
    """
    if img.startswith("docker.io/"):
        return True
    if any(img.startswith(p) for p in NON_HUB):
        return False
    host = img.split("/")[0]
    if "/" in img and ("." in host or ":" in host):
        return False
    return True


def docker_cmd_images(text):
    """README'lerdeki docker run/pull komutlarindan imaj adlarini cikarir.

    Tek bir regex yeterli degildi: bayraklari atliyor ama DEGERLERINI
    imaj saniyordu ve "8010:80" gibi port eslemeleri listeye giriyordu.
    """
    out = []
    for m in re.finditer(r"docker\s+(?:run|pull)\s+([^\n`]*)", text, re.I):
        toks = m.group(1).split()
        i = 0
        while i < len(toks):
            t = toks[i]
            if t.startswith("-"):
                if "=" in t:
                    i += 1
                elif t in VALUE_FLAGS:
                    i += 2
                else:
                    i += 1
                continue
            if PORT_RE.match(t) or "=" in t:
                i += 1
                continue
            if SKIP_RE.match(t) or not IMG_RE.match(t):
                break
            if "/" in t or ":" in t:
                out.append(t)
            break
    return out


def compose_built(text):
    """Ayni servis altinda hem image hem build varsa o imaj yerelde derleniyor."""
    built = set()
    cur_img, has_build, indent = None, False, None
    for line in text.splitlines():
        m = re.match(r"^(\s*)(image|build):\s*(.*)$", line)
        if not m:
            if re.match(r"^\s{0,4}\S+:\s*$", line) and indent is not None:
                if cur_img and has_build:
                    built.add(cur_img)
                cur_img, has_build, indent = None, False, None
            continue
        sp, key, val = m.groups()
        indent = len(sp)
        if key == "image":
            cur_img = val.strip().strip("\"'")
        else:
            has_build = True
    if cur_img and has_build:
        built.add(cur_img)
    return built


def collect():
    found = {}
    built_anywhere = set()

    for t in TRACKS:
        base = ROOT / t
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or ".git" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            rel = p.relative_to(ROOT).as_posix()
            name = p.name

            if name in ("docker-compose.yml", "docker-compose.yaml"):
                built_anywhere |= compose_built(text)

            if name.endswith(".md"):
                for img in docker_cmd_images(text):
                    found.setdefault(img, set()).add(rel)
                continue

            pat = None
            if name.endswith((".yml", ".yaml")):
                pat = r"^\s*-?\s*image:\s*(\S+)"
            elif name.startswith("Dockerfile"):
                pat = r"^\s*FROM\s+(\S+)"
            if not pat:
                continue
            for m in re.finditer(pat, text, re.M | re.I):
                img = m.group(1).strip().strip("\"'")
                if SKIP_RE.match(img) or not IMG_RE.match(img):
                    continue
                if "/" not in img and ":" not in img and "@" not in img:
                    continue
                found.setdefault(img, set()).add(rel)
    return found, built_anywhere


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    args = ap.parse_args()

    found, built = collect()
    keep, skipped = [], []
    for img in sorted(found):
        if img in built:
            skipped.append((img, "lab icinde derleniyor"))
        elif any(img.startswith(p) for p in LOCAL_ONLY):
            skipped.append((img, "yalnizca lab icinde uretiliyor"))
        elif not is_hub(img):
            skipped.append((img, "Docker Hub disi registry"))
        else:
            keep.append(img)

    print("lablarda gecen imaj : %d" % len(found))
    print("aynalanacak         : %d" % len(keep))
    print("atlanan             : %d" % len(skipped))

    if args.print:
        print()
        for i in keep:
            print(i)
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "# Docker Hub'dan GHCR'a aynalanacak imajlar.",
        "# Uretilir: python _platform/tools/collect-images.py",
        "# Aynalayan is akisi: .github/workflows/mirror-images.yml",
        "",
    ]
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        "\n".join(header + keep) + "\n")
    print("\nyazildi: %s" % OUT.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
