#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Her laba "Takilirsaniz" bolumu ekler.

NEDEN: lablar ne yapilacagini anlatiyor ama BIR SEY TERS GIDERSE ne
yapilacagini anlatmiyordu. Ders sirasinda kaybedilen zamanin cogu
burada; ogrenci hatayi okuyup ne demek oldugunu bilemiyor.

Buradaki hatalar uydurulmadi: 77 labin tamami calistirilarak test
edilirken GERCEKTEN alinan hatalar. Her biri icin sebebi ve cikis
yolu yaziyor.

Bolum "## Cleanup" / "## Temizlik" basliginin HEMEN ONUNE giriyor:
ogrenci takildiginda once bunu, cozemezse temizleyip bastan
baslamayi goruyor.

Calistirma:
  python _platform/tools/add-troubleshooting.py            # uygula
  python _platform/tools/add-troubleshooting.py --dry-run
"""
import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRACKS = ("DevSecOps", "Docker", "Kubernetes", "Observability")
MARK = "<!-- troubleshooting:auto -->"

DOCKER_EN = """## If something goes wrong

**`Cannot connect to the Docker daemon`** - Docker Desktop is not running.
Start it and wait until the whale icon stops animating.

**`port is already allocated`** - a container from an earlier lab is still
holding that port. See what is running with `docker ps`, then remove the old
container with `docker rm -f <name>`.

**`The container name "/..." is already in use`** - same cause, same fix:
`docker rm -f <name>`, then run the command again.

**`unable to prepare context: path ... not found`** on a build - you are in the
wrong folder. Every command in this lab assumes you are at the root of this
repository.

**A `docker run` that prints usage text instead of working** - some commands in
this lab are meant to fail, to show you what a wrong argument looks like. Read
the text around the command before assuming it is broken.

Still stuck? The **Cleanup** section below resets everything, so you can start
the lab again from a clean machine.
"""

DOCKER_TR = """## Takılırsanız

**`Cannot connect to the Docker daemon`** - Docker Desktop çalışmıyor.
Başlatın ve balina simgesi hareket etmeyi bırakana kadar bekleyin.

**`port is already allocated`** - önceki bir labdan kalan konteyner o portu
hâlâ tutuyor. `docker ps` ile neyin çalıştığına bakın, eskisini
`docker rm -f <ad>` ile kaldırın.

**`The container name "/..." is already in use`** - aynı sebep, aynı çözüm:
`docker rm -f <ad>` deyip komutu tekrar çalıştırın.

**Build sırasında `unable to prepare context: path ... not found`** - yanlış
dizindesiniz. Bu labdaki her komut deponun kök dizininde olduğunuzu varsayıyor.

**Çalışmak yerine kullanım metni basan `docker run`** - bu labdaki bazı
komutlar, yanlış argümanın nasıl göründüğünü göstermek için kasıtlı olarak
başarısız oluyor. Bozuk sanmadan önce komutun çevresindeki açıklamayı okuyun.

Hâlâ takılıysanız: aşağıdaki **Cleanup** bölümü her şeyi sıfırlıyor, labı
temiz bir makineyle baştan yapabilirsiniz.
"""

K8S_EN = """## If something goes wrong

**`The connection to the server ... was refused`** - the cluster is not
running. Enable Kubernetes in Docker Desktop and wait for it to start.

**`provided port is already allocated`** - a Service from an earlier lab still
holds that NodePort. Find it with `kubectl get svc -A` and delete the namespace
that lab created.

**`failed calling webhook ... service not found`** - leftovers from the
**admission** lab are blocking the API server, and you will not be able to
create anything, not even a namespace. That lab's Cleanup section has the two
commands that remove the webhook configurations.

**Pod stuck in `ContainerCreating` or `Pending`** - usually the image is still
downloading, which can take a few minutes the first time. Check with
`kubectl describe pod <name>` and read the **Events** at the bottom: they say
exactly what the Pod is waiting for.

**Pod in `CrashLoopBackOff`** - the container starts and exits. The reason is
in its logs: `kubectl logs <name>`. Add `--previous` to see the run before the
last restart.

Still stuck? The **Cleanup** section below resets everything, so you can start
the lab again from a clean cluster.
"""

K8S_TR = """## Takılırsanız

**`The connection to the server ... was refused`** - küme çalışmıyor. Docker
Desktop'ta Kubernetes'i açın ve başlamasını bekleyin.

**`provided port is already allocated`** - önceki bir labdan kalan Service o
NodePort'u hâlâ tutuyor. `kubectl get svc -A` ile bulun ve o labın oluşturduğu
namespace'i silin.

**`failed calling webhook ... service not found`** - **admission** labından
kalanlar API sunucusunu engelliyor; hiçbir şey oluşturamazsınız, namespace
bile. O labın Cleanup bölümünde webhook yapılandırmalarını kaldıran iki komut
var.

**Pod `ContainerCreating` ya da `Pending`de takılı** - genellikle imaj hâlâ
iniyor; ilk seferde birkaç dakika sürebilir. `kubectl describe pod <ad>` ile
bakın ve en alttaki **Events** bölümünü okuyun: pod'un neyi beklediğini tam
olarak söylüyor.

**Pod `CrashLoopBackOff`de** - konteyner başlayıp çıkıyor. Sebep günlüklerinde:
`kubectl logs <ad>`. Son yeniden başlatmadan önceki çalıştırmayı görmek için
`--previous` ekleyin.

Hâlâ takılıysanız: aşağıdaki **Cleanup** bölümü her şeyi sıfırlıyor, labı
temiz bir kümeyle baştan yapabilirsiniz.
"""


def block(requires, tr):
    parts = []
    if "docker" in requires:
        parts.append(DOCKER_TR if tr else DOCKER_EN)
    if "kubernetes" in requires:
        # Iki bolum birden olmasin: Kubernetes labinda Docker bolumu
        # gereksiz gurultu, k8s bolumu zaten kapsiyor.
        parts = [K8S_TR if tr else K8S_EN]
    return MARK + "\n" + "\n".join(parts) + "\n"


def process(path, dry):
    s = io.open(path, encoding="utf-8").read()
    if MARK in s:
        return "zaten var"
    m = re.match(r"^---\n(.*?)\n---\n", s, re.S)
    if not m:
        return "frontmatter yok"
    req = re.search(r"^requires:\s*\[(.*?)\]", m.group(1), re.M)
    if not req:
        return "requires yok"
    requires = [x.strip() for x in req.group(1).split(",")]
    tr = path.endswith(".tr.md")

    rest = s[m.end():]
    # Cleanup basliginin hemen onune
    c = re.search(r"^##\s+(Cleanup|Temizlik)\b", rest, re.M | re.I)
    at = c.start() if c else len(rest)
    new = rest[:at] + block(requires, tr) + "\n" + rest[at:]
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
