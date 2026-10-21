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

# KASITLI BOZUK imajlar: troubleshooting lablarinin ogretmek istedigi
# hatanin kendisi. Dogru adlar "courselabs/rng-web" ve "kiamol/ch05-pi";
# buradaki yanlis adlari ogrencinin bulup duzeltmesi gerekiyor - iki labin
# da solution.md'si hatayi "the image name is incorrect" diye acikliyor.
# Docker Hub'da yoklar, yani aynalanacak bir sey de yok; listeye girerlerse
# aynalama is akisi her calismada bunlarda hata veriyor.
INTENTIONALLY_BROKEN = {
    "courselabs/rng-website:21.05",   # Docker/labs/troubleshooting
    "kiamol/ch05-pi-app",             # Kubernetes/labs/troubleshooting
}

# GHCR'a AYNALANAMAYAN imajlar: Docker'in sema v1 manifestiyle yayinlanmis
# cok eski imajlar. GHCR sema v1'i kabul etmiyor ("DENIED: invalid manifest
# type") ve crane manifesti donusturmuyor - index'i OLDUGU GIBI kopyalamak
# isin tanimi, cevirmek cok mimarili destegi bozardi. Bu imajlar Docker
# Hub'dan cekilmeye devam ediyor; tarama lablarinda birer kez cekildikleri
# icin hiz siniri acisindan onemsizler.
CANNOT_MIRROR = {
    "nginx:1.7",   # 2014; labs/scanning'de CVE gostermek icin kasitli eski
}

# "docker run -p 8010:80 nginx" gibi komutlarda bayraklarin DEGERLERI
# imaj sanilmasin diye: bu bayraklardan sonraki token atlanir.
VALUE_FLAGS = {
    "-p", "--publish", "-v", "--volume", "-e", "--env", "--name", "--network",
    "--net", "-u", "--user", "-w", "--workdir", "--restart", "--entrypoint",
    "--mount", "--label", "-l", "--add-host", "--env-file", "--memory", "-m",
    "--cpus", "--link", "--device", "--health-cmd", "--platform", "--pull",
}


def lab_scope(path):
    """Bir yolun ait oldugu LAB koku.

    Derleme tespiti dizin degil LAB bazinda yapilmali: golden-images
    labinda altin imajlar labs/golden-images/library altinda derlenip
    labs/golden-images/apps altinda "FROM courselabs/java:jre-26.10" ile
    kullaniliyor. Dizin bazli karsilastirma bunu "baska yerde cekiliyor"
    sanip Docker Hub'da hic var olmayan bir imaji aynalama listesine
    koyuyordu.

    Lab bazinda bakmak ayni labin icindeki derle-ve-kullan kalibini
    dogru goruyor, ama Observability/src'de derlenip labs/* altinda
    Hub'dan cekilen imajlari (prometheus, grafana, jaeger,
    node-exporter) ayri tutmaya devam ediyor - onlar gercekten
    aynalanmali.
    """
    parts = path.split("/")
    for i, seg in enumerate(parts):
        if seg in ("labs", "hackathon") and i + 1 < len(parts):
            return "/".join(parts[:i + 2])
    return "/".join(parts[:2])


def unmirror_map():
    """GHCR ayna adresi -> referansin Docker Hub'daki ozgun yazimi.

    NEDEN: use-mirror.py lab dosyalarindaki adresleri GHCR'a cevirdikten
    sonra bu betik ayni dosyalari tarayinca ghcr.io adreslerini "Docker
    Hub disi registry" sayip atliyor ve liste 83 imajdan 28'e dusuyordu.
    Daralmis listeyi itmek hem aynalamayi hem referans guncellemeyi
    birlikte bozar: aynalama kaydi kuculur, kaydi kullanan betik geri
    kalan imajlari taniyamaz hale gelir. Kaydi ters cevirip adresleri
    ozgun hallerine donduruyoruz; boylece tarama, referanslarin aynaya
    cevrilmis olup olmamasindan BAGIMSIZ ayni sonucu veriyor.

    Bir GHCR adresine birden fazla ozgun yazim dusebiliyor
    ("kiamol/ch05-pi" ile "docker.io/kiamol/ch05-pi:latest" ayni hedefe
    gidiyor). Ikisi de ayni aynaya cevrildigi icin hangisinin secildigi
    sonucu degistirmiyor; belirleyici olsun diye en kisasi aliniyor.
    """
    path = ROOT / "_platform" / "mirror" / "mirrored.txt"
    out = {}
    if not path.exists():
        return out
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        src, dst = (x.strip() for x in line.split("\t", 1))
        if dst not in out or len(src) < len(out[dst]):
            out[dst] = src
    return out


def strip_block_scalars(text):
    """YAML blok skalerlerinin ICERIGINI bosaltir.

    "artifacthub.io/images: |" altindaki satirlar YAML yapisi degil, duz
    METIN. Vendor'lanmis Helm chart'larinin ArtifactHub notlarinda orada
    "image: docker.io/bitpoke/mysql-operator:latest" gibi satirlar
    geciyor; bu adresler hicbir zaman cekilmiyor - chart'in gercek
    imajlari values.yaml'dan geliyor ve o ":latest" etiketlerinin Docker
    Hub'da karsiligi yok. Regex bunlari gercek imaj sanip aynalama
    listesine koyuyordu, dolayisiyla 4 bitpoke imaji her calismada hata
    veriyordu.

    Satirlar silinmiyor, bosaltiliyor: satir numaralari korunuyor.
    """
    out, skip_at = [], None
    for line in text.splitlines():
        indent = len(line) - len(line.lstrip())
        if skip_at is not None:
            if line.strip() and indent <= skip_at:
                skip_at = None
            else:
                out.append("")
                continue
        out.append(line)
        if re.search(r":\s*[|>][-+0-9]*\s*$", line):
            skip_at = indent
    return "\n".join(out)


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


def docker_build_tags(text):
    """README'de "docker build -t X" ile URETILEN imaj adlari.

    Bunlar lab sirasinda ogrencinin kendi makinesinde derleniyor; Docker
    Hub'da karsiliklari yok. Aynalama listesine girerlerse is akisi var
    olmayan bir seyi kopyalamaya calisip basarisiz oluyor - ilk calistirmada
    "simple:test", "courselabs/app-1:v2" ve "rng-api:21.05" tam olarak bu
    yuzden hata verdi.
    """
    out = set()
    for m in re.finditer(r"docker\s+(?:buildx\s+)?build\s+([^\n`]*)", text, re.I):
        toks = m.group(1).split()
        for i, t in enumerate(toks):
            if t in ("-t", "--tag") and i + 1 < len(toks):
                out.add(toks[i + 1].strip("\"'"))
            elif t.startswith("--tag="):
                out.add(t.split("=", 1)[1].strip("\"'"))
    return out


def compose_services(text):
    """compose dosyasindan {servis: (image, build_var_mi)} cikarir.

    Servis adlari YALNIZCA "services:" altindaki ilk girinti
    seviyesinde aranir. Girinti araligina bakmak yetmiyordu: ic ice
    anahtarlar (networks, environment ve ag adlari) servis saniliyor,
    "build:" de bir servis adi gibi yakalanip has_build hic
    isaretlenmiyordu.
    """
    out = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines) and not re.match(r"^services:\s*$", lines[i]):
        i += 1
    if i >= len(lines):
        return {}
    i += 1

    svc_indent = None
    cur = None
    for line in lines[i:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            break  # services blogu bitti
        if svc_indent is None:
            svc_indent = indent
        if indent == svc_indent:
            m = re.match(r"^\s*([A-Za-z0-9._-]+):\s*$", line)
            cur = m.group(1) if m else None
            if cur:
                out.setdefault(cur, [None, False])
            continue
        if cur is None:
            continue
        m = re.match(r"^\s+(image|build):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.groups()
        if key == "image":
            out[cur][0] = val.strip().strip("\"'")
        else:
            out[cur][1] = True
    return {k: tuple(v) for k, v in out.items()}


def built_images(compose_by_dir):
    """Yerelde derlenen imajlar -> {imaj: derlendigi dizinler}.

    DIZIN BAZINDA donuyor, cunku ayni ad bir yerde derlenip baska yerde
    Docker Hub'dan CEKILEBILIYOR. Observability/src/compose.yml dort
    imaji (prometheus, grafana, jaeger, node-exporter) hem "image:" hem
    "build:" ile tanimliyor; lablar ise ayni adlari 32 dosyada Hub'dan
    cekiyor. "Bir yerde derleniyorsa her yerde atla" kurali bu dort agir
    imaji - hiz siniri acisindan en onemlilerini - aynalama disinda
    birakiyordu.

    COMPOSE OVERRIDE KALIBI: core.yml "image: rng-api:21.05" diyor ama
    "build:" ayri bir dosyada (build.yml) ve ikisi
    "-f core.yml -f build.yml" ile birlikte kullaniliyor. Dosya bazli
    bakmak bunu goremiyordu ve bu imajlar aynalama listesine girip
    "var olmayan imaj" hatasi veriyordu. Servis adi uzerinden AYNI
    DIZINDEKI tum compose dosyalari birlestiriliyor.
    """
    built = {}
    for d, services_list in compose_by_dir.items():
        imgs = {}
        builds = set()
        for services in services_list:
            for name, (img, has_build) in services.items():
                if img:
                    imgs.setdefault(name, set()).add(img)
                if has_build:
                    builds.add(name)
        # Bir servis override dosyalarinda FARKLI imaj adlari tasiyabiliyor
        # (core.yml "rng-api:21.05", docker-compose.yml "rng-api:21.05-local").
        # Servis derleniyorsa o adlarin HEPSI yerelde uretiliyor demektir;
        # yalnizca ilkini almak digerlerini aynalama listesinde birakiyordu.
        for name in builds:
            for img in imgs.get(name, set()):
                built.setdefault(img, set()).add(d)
    return built


def collect():
    found = {}
    built_in = {}        # imaj -> derlendigi dizinler (repo koku gore)
    compose_by_dir = {}
    unmirror = unmirror_map()

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
            reldir = p.parent.relative_to(ROOT).as_posix()
            name = p.name

            # Tum compose dosyalari (override'lar dahil) dizin bazinda
            # toplaniyor; "build:" ayri dosyada olabiliyor.
            if name.endswith((".yml", ".yaml")):
                # Blok skaler icerigi YAML yapisi degil; imaj aramasindan
                # once bosaltiliyor.
                text = strip_block_scalars(text)
                if "services:" in text:
                    # Derlenen imaj adlari da ozgun hallerine donuyor,
                    # yoksa "derleniyor" tespiti taranan adla eslesmez.
                    compose_by_dir.setdefault(reldir, []).append({
                        k: (unmirror.get(img, img), has_build)
                        for k, (img, has_build) in compose_services(text).items()
                    })

            if name.endswith(".md"):
                for tag in docker_build_tags(text):
                    built_in.setdefault(tag, set()).add(reldir)
                for img in docker_cmd_images(text):
                    found.setdefault(unmirror.get(img, img), set()).add(rel)
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
                found.setdefault(unmirror.get(img, img), set()).add(rel)
    for img, dirs in built_images(compose_by_dir).items():
        built_in.setdefault(img, set()).update(dirs)
    return found, built_in


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    args = ap.parse_args()

    found, built = collect()
    keep, skipped = [], []
    for img in sorted(found):
        # Yalnizca imajin gectigi HER yer onu derleyen bir dizinse atla.
        # Bir yerde derlenip baska yerde Hub'dan cekilen imajlar (bkz.
        # built_images) aynalanmali: cekildikleri yer hiz sinirina tabi.
        build_labs = {lab_scope(d) for d in built.get(img, set())}
        pulled_elsewhere = any(
            lab_scope(f) not in build_labs for f in found[img])
        if build_labs and not pulled_elsewhere:
            skipped.append((img, "lab icinde derleniyor"))
        elif img in INTENTIONALLY_BROKEN:
            skipped.append((img, "kasitli bozuk - troubleshooting labi"))
        elif img in CANNOT_MIRROR:
            skipped.append((img, "sema v1 manifest - GHCR kabul etmiyor"))
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
