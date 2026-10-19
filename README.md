# labs-platform

`sudo2go` eğitim laboratuvarlarının ortak altyapısı: sürüm matrisi, doğrulama
araçları ve WordPress eklentisi.

Lab içeriği burada **değil**. İçerik track repolarında:

| Track | Repo | Lab |
|---|---|---|
| DevSecOps | [yasinoz/devsecops](https://github.com/yasinoz/devsecops) | 19 |
| Docker | [yasinoz/docker](https://github.com/yasinoz/docker) | 12 |
| Kubernetes | [yasinoz/kubernetes](https://github.com/yasinoz/kubernetes) | 29 |
| Gözlemlenebilirlik | [yasinoz/observability](https://github.com/yasinoz/observability) | 15 |

Hepsi [courselabs](https://github.com/courselabs) çalışmalarından türetildi ve
CC BY-SA 4.0 ile dağıtılıyor. Atıf her repoda `ATTRIBUTION.md` dosyasında.

> Bu repo **public**: track repolarındaki CI iş akışları araçları buradan
> `actions/checkout` ile alıyor ve bu, token gerektirmeden yalnızca public
> repoda çalışıyor. Burada gizli bilgi yok.

## Neden ortak bir katman

Dört repo, ~75 lab, iki dil. Sürüm bilgisi her repoya kopyalanırsa ilk
güncellemede ayrışır. Burada tek doğruluk kaynağı var:

```
VERSIONS.yaml         hangi bileşen hangi sürümde, NEDEN ve eskisi neydi
rewrites.yaml         mekanik yeniden yazma kuralları (veri, kod değil)
manifests.yaml        vendor'lanmış kurulum manifestleri ve kaynak URL'leri
lint-exceptions.yaml  istisnalar — her biri gerekçesiyle
```

## Araçlar

Hiçbir bağımlılık yok — PyYAML bile. Eğitmen laptopunda ve CI'da `pip install`
gerekmesin diye YAML'in kullandığımız alt kümesi için kendi okuyucumuz var
(`tools/miniyaml.py`).

```bash
# Dersi bozan sorunları ara (çıkış kodu: hata varsa 1)
python tools/lab-lint.py ../devsecops

# Mekanik düzeltmeleri uygula — ÖNCE deneme çalıştırması
python tools/modernize.py ../devsecops --dry-run
python tools/modernize.py ../devsecops --apply

# manifest.json + index tablolarını üret
python tools/make-manifest.py ../devsecops --write-frontmatter

# Vendor'lanmış kurulum manifestlerini güncel sürümle değiştir
python tools/fetch-manifests.py --repo-root .. --apply

# Kırık göreli bağlantıları onar
python tools/fix-links.py ../devsecops --apply
```

### lab-lint.py neyi yakalar

| Kontrol | Ne arar |
|---|---|
| `compose` | `docker-compose` (v1) çağrıları — v1 EOL, Docker Desktop ile gelmiyor |
| `pins` | Pinlenmemiş imaj (`:latest` veya etiketsiz) — ders tekrar edilebilir olmalı |
| `stale` | `VERSIONS.yaml`'da eski olarak işaretli referanslar |
| `links` | Kırık göreli bağlantı |
| `frontmatter` | Eksik/geçersiz frontmatter |
| `i18n` | TR karşılığı olmayan döküman (çeviri ilerleme takibi) |
| `parity` | TR dökümanda EN'e göre düşen adım/kod bloğu/`<details>` |

Araç Helm chart dizinlerini (`Chart.yaml` içeren) ve kustomize `images:`
dönüştürücüsünün yer tutucularını tanır; oralarda pin araması yanlış alarm
üretirdi.

### Neden fikirsiz

`modernize.py` **tahmin yapmaz**: yalnızca `rewrites.yaml` ve `VERSIONS.yaml`
içindeki tam eşleşmeleri değiştirir. Vendor'lanmış kurulum manifestlerine
(ArgoCD, Gatekeeper, cert-manager, Calico) dokunmaz ve "komple yenilenmeli"
diye raporlar — çünkü böyle bir dosyada sadece imaj etiketini değiştirmek
çalışan bir kurulum vermez, sessizce bozulan bir kurulum verir. Yarı yamalı
manifest, açıkça eski olandan daha kötüdür.

## WordPress eklentisi

`wordpress/sudo2go-labs/` — lab dökümanlarını GitHub'dan canlı çekip EN/TR
olarak yayınlar. Kurulum: [wordpress/KURULUM.md](wordpress/KURULUM.md).

Tek doğruluk kaynağı repodur; WordPress'e içerik kopyalanmaz. Repoya push
edilen düzeltme, önbellek süresi kadar sonra sitede canlı olur.

## Dökümanlar

- [docs/REPO-YAPISI.md](docs/REPO-YAPISI.md) — iki dilli repo sözleşmesi,
  frontmatter şeması, `status` alanının anlamı
- [docs/CEVIRI-SOZLUGU.md](docs/CEVIRI-SOZLUGU.md) — TR terim tablosu ve üslup
  kılavuzu. **Çeviri yaparken bağlayıcıdır**; tutarlılık olmazsa öğrenci aynı
  kavramı üç farklı isimle görür.

## Sürüm matrisini güncellemek

```bash
# 1. VERSIONS.yaml'da yeni sürümü yaz, eskisini 'was:' olarak bırak
# 2. Varyantlar için rewrites.yaml'a kural ekle
# 3. Her repoda uygula
for r in devsecops docker kubernetes observability; do
  python tools/modernize.py "../$r" --apply
  python tools/lab-lint.py "../$r"
done
```

`was:` alanları hem codemod kuralı hem de lint kara listesi üretir: bir sürümü
matriste güncelleyip repoda uygulamayı unutursanız lint yakalar.
