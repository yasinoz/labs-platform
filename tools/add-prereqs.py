#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Her laba "Baslamadan once" bolumu ekler.

NEDEN: lablarin hicbirinde ogrencinin NE GEREKTIGINI ve calisip
calismadigini NASIL ANLAYACAGINI soyleyen bir bolum yoktu. Ders
sirasinda en cok vakit kaybettiren sey bu: ogrenci ilk komutu
calistiriyor, hata aliyor ve sebebi Docker'in kapali olmasi oluyor.

Bolum frontmatter'daki "requires" ve "duration" alanlarindan
uretiliyor, elle yazilmiyor - yeni lab eklendiginde bu betik tekrar
calistirilinca o da kapsanir.

Calistirma:
  python _platform/tools/add-prereqs.py            # uygula
  python _platform/tools/add-prereqs.py --dry-run  # ne degisecek
"""
import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRACKS = ("DevSecOps", "Docker", "Kubernetes", "Observability")

MARK = "<!-- prereqs:auto -->"

DOCKER_EN = """**Docker Desktop** must be running. Check it:

```
docker version
```

A `Server:` section in the output means you are ready. If you get an error
instead, start Docker Desktop and wait until the whale icon stops animating."""

DOCKER_TR = """**Docker Desktop** çalışıyor olmalı. Kontrol edin:

```
docker version
```

Çıktıda bir `Server:` bölümü görüyorsanız hazırsınız. Onun yerine hata
alıyorsanız Docker Desktop'ı başlatın ve balina simgesi hareket etmeyi
bırakana kadar bekleyin."""

K8S_EN = """A **Kubernetes cluster** must be running. Docker Desktop ships one:
*Settings -> Kubernetes -> Enable Kubernetes*. Check it:

```
kubectl get nodes
```

You should see at least one node with `STATUS` of `Ready`. If the command
hangs or errors, the cluster is still starting - give it a minute and try
again."""

K8S_TR = """Bir **Kubernetes kümesi** çalışıyor olmalı. Docker Desktop
bunu içeriyor: *Settings -> Kubernetes -> Enable Kubernetes*. Kontrol edin:

```
kubectl get nodes
```

En az bir düğüm görmelisiniz ve `STATUS` sütunu `Ready` olmalı. Komut
takılır ya da hata verirse küme henüz başlamamıştır; bir dakika bekleyip
tekrar deneyin."""

WHERE_EN = ("> Run every command from the **root of this repository** - the paths in "
            "this lab are written relative to it.")
WHERE_TR = ("> Bütün komutları **deponun kök dizininden** çalıştırın; bu labdaki "
            "yollar ona göre yazıldı.")


HELM_EN = """**Helm** must be installed - it is a separate command line tool, it
does not come with Docker Desktop. Check it:

```
helm version --short
```

A version number like `v3.x.x` means you are ready. If you get
`command not found`, install it first: on Windows `winget install Helm.Helm`,
on macOS `brew install helm`, or follow
[helm.sh/docs/intro/install](https://helm.sh/docs/intro/install/)."""

HELM_TR = """**Helm** kurulu olmali - ayri bir komut satiri araci, Docker
Desktop ile birlikte GELMIYOR. Kontrol edin:

```
helm version --short
```

`v3.x.x` gibi bir surum numarasi goruyorsaniz hazirsiniz. `command not found`
aliyorsaniz once kurun: Windows'ta `winget install Helm.Helm`, macOS'ta
`brew install helm`, ya da
[helm.sh/docs/intro/install](https://helm.sh/docs/intro/install/) adresindeki
adimlar."""

def block(requires, duration, tr):
    parts = []
    head = "## Başlamadan önce" if tr else "## Before you start"
    if duration:
        parts.append("Süre: yaklaşık %s dakika." % duration if tr
                     else "Takes about %s minutes." % duration)
    needs = []
    if "docker" in requires:
        needs.append(DOCKER_TR if tr else DOCKER_EN)
    if "kubernetes" in requires:
        needs.append(K8S_TR if tr else K8S_EN)
    # Helm Docker Desktop ile GELMIYOR; 6 lab helm komutu kullaniyordu
    # ama hicbiri requires alaninda belirtmiyordu, dolayisiyla ogrenci
    # "command not found" ile karsilasip ne yapacagini bilemiyordu.
    if "helm" in requires:
        needs.append(HELM_TR if tr else HELM_EN)
    body = "\n\n".join(parts + needs + [WHERE_TR if tr else WHERE_EN])
    return "%s\n%s\n\n%s\n" % (MARK, head, body)


def process(path, dry):
    s = io.open(path, encoding="utf-8").read()
    existing = MARK in s
    m = re.match(r"^---\n(.*?)\n---\n", s, re.S)
    if not m:
        return "frontmatter yok"
    fm = m.group(1)
    req = re.search(r"^requires:\s*\[(.*?)\]", fm, re.M)
    requires = [x.strip() for x in req.group(1).split(",")] if req else []
    if not requires:
        return "requires yok"
    dur = re.search(r"^duration:\s*(\d+)", fm, re.M)
    tr = path.endswith(".tr.md")

    rest = s[m.end():]
    built = block(requires, dur.group(1) if dur else "", tr)

    if existing:
        # Var olan blogu YENIDEN URET. Onceden yalnizca "yoksa ekle"
        # yapiliyordu; requires alanina yeni bir sey eklendiginde
        # (ornegin helm) blok eskisi gibi kaliyor ve ogrenci eksik
        # on kosulu hic gormuyordu.
        # Blogun SONU: kendi "## Baslamadan once" basligindan SONRA gelen
        # ilk "## " basligi. Yalnizca "(?=\n## )" aramak blogun kendi
        # basliginda duruyor ve blok silinecegine KOPYALANIYORDU.
        pat = re.compile(
            re.escape(MARK) + r"\n##[^\n]*\n.*?(?=\n## )", re.S
        )
        if not pat.search(rest):
            return "blok siniri bulunamadi"
        # Sondaki bos satir KORUNMALI: desen "\n## " oncesinde duruyor,
        # yani yerine konan metin bos satir birakmazsa bir sonraki
        # baslik alinti satirina yapisiyor ve Markdown onu baslik olarak
        # islemeyebiliyor.
        updated = pat.sub(lambda _: built.rstrip("\n") + "\n", rest, count=1)
        if updated == rest:
            return "ayni"
        if not dry:
            io.open(path, "w", encoding="utf-8", newline="\n").write(s[:m.end()] + updated)
        return "guncellendi"

    # Ilk "## " basliginin oncesine yerlestir: giris metninden sonra,
    # ilk teknik bolumden once okunmali.
    h = re.search(r"^## ", rest, re.M)
    at = h.start() if h else len(rest)
    new = rest[:at] + built + "\n" + rest[at:]
    if not dry:
        io.open(path, "w", encoding="utf-8", newline="\n").write(s[:m.end()] + new)
    return "eklendi"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    counts = {}
    for t in TRACKS:
        base = os.path.join(ROOT, t, "labs")
        if not os.path.isdir(base):
            continue
        for lab in sorted(os.listdir(base)):
            for fn in ("README.md", "README.tr.md"):
                p = os.path.join(base, lab, fn)
                if os.path.isfile(p):
                    r = process(p, args.dry_run)
                    counts[r] = counts.get(r, 0) + 1
    for k, v in sorted(counts.items()):
        print("  %-16s %d" % (k, v))


if __name__ == "__main__":
    main()
