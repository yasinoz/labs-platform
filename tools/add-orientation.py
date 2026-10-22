#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Her laba "Bu lab nasil isliyor" bolumu ekler.

NEDEN: lablar dogru yaziliyor ama OKUMA KURALINI hicbir yerde
soylemiyor. Daha once bu isi hic yapmamis bir ogrenci sunlari
bilmiyor:

  - 📋 isareti "simdi sirasi sende" demek; altindaki ok cevabi
    sakliyor. Ogrenci oku hemen aciyor, kendi denemiyor ve lab
    kopyala-yapistir egzersizine donuyor.
  - Komutlarin nereye yazilacagi. "Terminal" diyoruz ama Windows'ta
    hangi terminal, hangi klasor belirsiz.
  - ">" ile baslayan satirlar ACIKLAMA, komut degil. Ogrenciler
    bunlari da kopyalamaya calisiyor.
  - Takilinca sirayla ne yapilacagi (hints -> solution).

Bolum laba ozgu bilgi tasimiyor; bilerek boyle - her labda ayni
yerde, ayni sozlerle duruyor ki ogrenci bir kez ogrenip gecsin.
Baslik seviyesi H2 ve isaretle sarili, yani betik tekrar
calistirilabilir.

Calistirma:
  python _platform/tools/add-orientation.py            # uygula
  python _platform/tools/add-orientation.py --dry-run  # ne degisecek
"""
import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRACKS = ("DevSecOps", "Docker", "Kubernetes", "Observability")

MARK = "<!-- orientation:auto -->"
END = "<!-- /orientation:auto -->"
PREREQS = "<!-- prereqs:auto -->"

EN = """## How this lab works

Read this once - every lab in this track follows the same rules.

**Where you type the commands.** Open a terminal and go to the folder where you
cloned this repository. On Windows use **PowerShell** (search for it in the
Start menu), on macOS or Linux use **Terminal**. Every path in this lab is
written from the repository root, so stay there unless a step says otherwise.

**Lines starting with `>` are explanations, not commands.** Don't paste them.
Only the text inside grey code boxes gets typed.

**The 📋 sign means it's your turn.** When you see it, try the step yourself
first. Underneath it there is a collapsed **"Not sure how?"** arrow with the
answer - open it *after* you have tried, not before. The labs are written this
way on purpose: you remember what you worked out, not what you pasted.

**If a command fails, that is normal.** Some steps fail deliberately to show
you what the error looks like. Read the sentence above the command before you
assume something is broken.

**When you get stuck**, in this order:

1. Re-read the paragraph above the command - the answer is usually there.
2. Open the **"Not sure how?"** arrow.
3. Open `hints.md` for a nudge.
4. Open `solution.md` for the full answer. Using it is fine; copying it without
   reading is not.

**When you finish**, run the **Cleanup** section at the bottom. Labs share
ports and container names, so leftovers from one lab break the next one."""

TR = """## Bu lab nasıl işliyor

Bunu bir kez okuyun - bu eğitimdeki her lab aynı kurallarla yazıldı.

**Komutları nereye yazacaksınız.** Bir terminal açın ve bu depoyu kopyaladığınız
klasöre gidin. Windows'ta **PowerShell** kullanın (Başlat menüsünde aratın),
macOS veya Linux'ta **Terminal**. Labdaki bütün yollar depo kökünden yazıldı,
yani bir adım aksini söylemedikçe orada kalın.

**`>` ile başlayan satırlar açıklamadır, komut değildir.** Onları yapıştırmayın.
Yalnızca gri kod kutularının içindeki metin yazılır.

**📋 işareti "sıra sizde" demektir.** Onu gördüğünüzde adımı önce kendiniz
deneyin. Hemen altında cevabı saklayan kapalı bir **"Nasıl yapılır?"** oku var;
onu denedikten *sonra* açın, önce değil. Lablar bilerek böyle yazıldı: kendi
çözdüğünüz şeyi hatırlarsınız, yapıştırdığınızı değil.

**Bir komut hata verirse bu normal olabilir.** Bazı adımlar hatanın nasıl
göründüğünü göstermek için bilerek başarısız olur. Bir şeyin bozuk olduğuna
karar vermeden önce komutun üstündeki cümleyi okuyun.

**Takılırsanız** şu sırayla:

1. Komutun üstündeki paragrafı tekrar okuyun - cevap genelde oradadır.
2. **"Nasıl yapılır?"** okunu açın.
3. `hints.md` dosyasını açın, küçük bir yönlendirme verir.
4. `solution.md` dosyasını açın, tam cevap orada. Kullanmak serbest; okumadan
   kopyalamak değil.

**Bitirdiğinizde** en alttaki **Temizlik** bölümünü çalıştırın. Lablar aynı
portları ve container adlarını paylaşıyor; birinden kalan artık diğerini bozar."""

BLOCK = re.compile(re.escape(MARK) + r".*?" + re.escape(END) + r"\n*", re.S)
H1 = re.compile(r"^#\s+.+$", re.M)


def lab_readmes():
    """Yalnizca MANIFEST'te lab olarak gecen README'ler.

    Dizini yurumek yanlis dosyalara dokunuyordu: lablarin icindeki ornek
    uygulamalar ucuncu taraf kutuphaneler tasiyor ve onlarin da kendi
    README dosyalari var (ornegin compose-build icindeki open-iconic CSS
    kutuphanesi). Manifest gercek lab listesini tutuyor.
    """
    import json

    for track in TRACKS:
        mpath = os.path.join(ROOT, track, "manifest.json")
        if not os.path.isfile(mpath):
            continue
        m = json.load(io.open(mpath, encoding="utf-8"))
        for section in m.get("sections", []):
            for lab in section.get("labs", []):
                for lang, docs in (lab.get("docs") or {}).items():
                    readme = docs.get("readme")
                    if not readme:
                        continue
                    p = os.path.join(ROOT, track, readme.replace("/", os.sep))
                    if os.path.isfile(p):
                        yield p


def apply(path, dry):
    text = io.open(path, encoding="utf-8").read()
    tr = path.endswith(".tr.md")
    body = (TR if tr else EN)
    block = "%s\n%s\n%s\n" % (MARK, body, END)

    # Zaten varsa GUNCELLE (metin degistiyse yenisi gecsin).
    if MARK in text:
        new = BLOCK.sub(block + "\n", text, count=1)
        return ("guncellendi", new) if new != text else ("ayni", text)

    # Yerlestirme: prereqs blogunun HEMEN ONUNE. Prereqs yoksa H1'den
    # sonraki giris paragraflarinin ardina.
    if PREREQS in text:
        new = text.replace(PREREQS, block + "\n" + PREREQS, 1)
        return "eklendi", new

    m = H1.search(text)
    if not m:
        return "H1 yok", text
    # H1'den sonraki ilk bos satirdan sonra giris var; ilk "## " basligi
    # bulup onune koyuyoruz, yoksa sona.
    nxt = re.search(r"^##\s+", text[m.end():], re.M)
    pos = m.end() + nxt.start() if nxt else len(text)
    new = text[:pos] + block + "\n" + text[pos:]
    return "eklendi", new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    counts = {}
    for path in sorted(lab_readmes()):
        what, new = apply(path, args.dry_run)
        counts[what] = counts.get(what, 0) + 1
        if what in ("eklendi", "guncellendi") and not args.dry_run:
            io.open(path, "w", encoding="utf-8", newline="\n").write(new)
        if what == "H1 yok":
            print("  ! %s" % os.path.relpath(path, ROOT))

    for k in sorted(counts):
        print("%-12s %d" % (k, counts[k]))
    if args.dry_run:
        print("\n--dry-run: dosya yazilmadi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
