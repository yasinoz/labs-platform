#!/usr/bin/env python3
"""Docker Hub imaj adini GHCR aynasindaki karsiligina cevirir.

TEK ESLEME KURALI: hem aynalama is akisi hem de lab referanslarini
guncelleyen betik burayi kullaniyor. Iki yerde iki ayri kural olsaydi
biri degisince digeri sessizce yanlis adrese bakardi.

Kurallar:
  alpine:3.24                  -> ghcr.io/yasinoz/library/alpine:3.24
  courselabs/curl:v2           -> ghcr.io/yasinoz/courselabs/curl:v2
  docker.io/kiamol/ch05-pi:latest -> ghcr.io/yasinoz/kiamol/ch05-pi:latest
  courselabs/x@sha256:ee65...  -> ghcr.io/yasinoz/courselabs/x:sha-ee65224f
  kindest/node:v1.20.2@sha256:8f7e... -> ghcr.io/yasinoz/kindest/node:v1.20.2

Digest'li referanslarda etiket digest'ten turetiliyor; icerik yine
digest'ten kopyalandigi icin tekrar edilebilirlik korunuyor.
"""
import re
import sys

OWNER = "yasinoz"
PREFIX = "ghcr.io/" + OWNER


def split_ref(ref):
    """ref -> (repo, tag, digest). Eksik olanlar None."""
    digest = None
    if "@" in ref:
        ref, digest = ref.split("@", 1)
    tag = None
    # Son ":" bir etiket mi yoksa port mu? Repo adinda port olmaz,
    # cunku bu listede yalnizca Docker Hub imajlari var.
    if ":" in ref.rsplit("/", 1)[-1]:
        ref, tag = ref.rsplit(":", 1)
    return ref, tag, digest


def target(ref):
    """Kaynak imaj adi -> GHCR aynasindaki tam ad."""
    repo, tag, digest = split_ref(ref)

    if repo.startswith("docker.io/"):
        repo = repo[len("docker.io/"):]
    if repo.startswith("library/"):
        repo = repo[len("library/"):]

    # Resmi imajlar (tek parcali ad) library/ altinda toplaniyor ki
    # "alpine" ile "courselabs/alpine" GHCR'da cakismasin.
    path = repo if "/" in repo else "library/" + repo

    if tag:
        out_tag = tag
    elif digest:
        out_tag = "sha-" + digest.split(":", 1)[1][:12]
    else:
        out_tag = "latest"

    return "%s/%s:%s" % (PREFIX, path.lower(), out_tag)


def source_for_copy(ref):
    """crane'e verilecek kaynak: digest varsa digest, yoksa etiket."""
    repo, tag, digest = split_ref(ref)
    if repo.startswith("docker.io/"):
        repo = repo[len("docker.io/"):]
    if digest:
        return "%s@%s" % (repo, digest)
    return "%s:%s" % (repo, tag or "latest")


if __name__ == "__main__":
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # UC kolon: crane'in cekecegi kaynak, GHCR hedefi, ve referansin
        # LAB DOSYALARINDAKI yazimi.
        #
        # Ucuncusu sart. crane kaynagi normallesiyor:
        #   "kiamol/ch05-pi"                     -> "kiamol/ch05-pi:latest"
        #   "kindest/node:v1.20.2@sha256:8f7e.." -> "kindest/node@sha256:8f7e.."
        # Lab dosyalarinda ise ilk yazim duruyor. Basarili aynalamalar
        # normallesmis adla kaydedilince referanslari guncelleyen betik
        # dosyalarda o adi arayip bulamiyor; 18 imaj (kiamol'un tamami ve
        # kindest/node dahil) sessizce Docker Hub'da kaliyordu.
        print("%s\t%s\t%s" % (source_for_copy(line), target(line), line))
