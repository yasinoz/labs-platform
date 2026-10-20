"""Yayinlanan lab sitesini uctan uca dogrular.

Kullanim:
    python verify-site.py [https://site-adresi]

Kimlik bilgisi kullanmaz - yalnizca herkese acik HTTP istekleri. Her istek
taze bir onbellek anahtari kullanir, boylece onbelleklenmis bir yaniti
"calisiyor" sanmaz.

Beklentiler yasinoz.me kurulumuna gore yazildi: cikplak /labs/ varsayilan
dili (orada EN) kullanir, /labs/tr/ ve /labs/en/ URL ile dil belirtir.
Baska bir sitede calistiracaksaniz CHECKS listesindeki beklentileri o
sitenin ayarlarina gore guncelleyin.
"""
import re
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "https://yasinoz.me"
UA = "Mozilla/5.0 (compatible; sudo2go-labs-verify/1.1)"
CB = "?cb=111"


import random

def get(path):
    sep = "&" if "?" in path else "?"
    url = BASE + path + sep + "cb=%d" % random.randrange(10**9)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as exc:
        return 0, "HATA: %s" % exc


CHECKS = [
    ("/labs/", "Giris - varsayilan dil EN (site dili EN, kasitli)", [
        ("DevSecOps Labs", "EN track basligi - ayar boyle istendi"),
        (">19 labs<", "EN sayi bicimi"),
        ("Pick a track", "EN giris metni"),
    ]),
    ("/labs/tr/", "Giris - TR (URL ile)", [
        ("DevSecOps Laboratuvarlar", "TR track basligi"),
        (">19 lab<", "TR sayi bicimi"),
        ("Bir track secin", "TR giris metni"),
    ]),
    ("/labs/en/", "Giris - EN", [
        ("DevSecOps Labs", "EN track basligi"),
        (">19 labs<", "EN sayi bicimi"),
    ]),
    ("/labs/tr/devsecops/", "DevSecOps listesi (TR)", [
        ("Jenkins ile Otomasyon", "TR lab basligi"),
        ("Gozlemlenebilirlik".replace("o", "ö").replace("G", "G"), "TR bolum basligi"),
        ("45 dk", "sure etiketi"),
        ("git clone https://github.com/yasinoz/devsecops.git", "klonlama komutu"),
    ]),
    ("/labs/tr/devsecops/jenkins/", "Jenkins (TR)", [
        ("s2g-toc", "ICERIK TABLOSU  <-- 1.1.1 duzeltmesi"),
        ("Bu sayfada", "TR icerik tablosu basligi"),
        ("Jenkins ile Otomasyon", "H1"),
        ("gitea admin user create", "Gitea komutu"),
        ("Takıldınız mı", "TR details summary"),
        ("s2g-prevnext", "onceki/sonraki"),
    ]),
    ("/labs/tr/devsecops/jenkins/hints/", "Jenkins ipuclari (TR)", [
        ("Triggers", "ipucu icerigi"),
        ("kopyalamanın bir yolunu", "TR ipucu metni"),
    ]),
    ("/labs/tr/devsecops/jenkins/solution/", "Jenkins cozumu (TR)", [
        ("Poll SCM", "cozum icerigi"),
        ("HelloWorkd", "yazim hatasi ornegi"),
    ]),
    ("/labs/tr/devsecops/container-security/", "Container guvenligi (TR, en son cevrilen)", [
        ("Container Güvenliği", "TR H1"),
        ("adıyla", "Service adlandirilmis port notu"),
    ]),
    ("/labs/tr/docker/containers/", "EN'e dusme", [
        ("s2g-notice", "bilgilendirme kutusu"),
        ("cevrilmedi", "ceviri olmadigi soyleniyor (eklenti metni ASCII)"),
        ("Running Containers", "EN icerik"),
    ]),
    ("/labs/en/kubernetes/troubleshooting/", "Kubernetes derin rota (EN)", [
        ("s2g-body", "lab govdesi"),
    ]),
]


def main():
    fails = 0
    for path, label, markers in CHECKS:
        status, body = get(path)
        print("\n%s %s   (%s, %d KB)" % (
            "OK  " if status == 200 else "HATA", path, label, len(body) / 1024))
        if status != 200:
            fails += 1
            print("     HTTP %s" % status)
            continue
        for marker, why in markers:
            found = marker in body
            if not found:
                fails += 1
            print("       %s %-34s %s" % ("+" if found else "!", marker[:34], why))

    print("\n--- icerik tablosu ayrintisi ---")
    status, body = get("/labs/tr/devsecops/jenkins/")
    if status == 200:
        toc = re.search(r'<details class="s2g-toc">(.*?)</details>', body, re.S)
        if toc:
            items = re.findall(r'<li class="s2g-toc-l(\d)"><a href="#([^"]+)">([^<]+)</a>', toc.group(1))
            print("  toc girdisi: %d" % len(items))
            for lvl, anchor, text in items[:12]:
                print("    h%s  %s" % (lvl, text[:52]))
        else:
            print("  toc BLOGU YOK")
            fails += 1

    print("\n=== %s ===" % ("TUM KONTROLLER GECTI" if not fails else "%d kontrol basarisiz" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
