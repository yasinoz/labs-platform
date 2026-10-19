# Lab Repo Yapısı (dört track için ortak sözleşme)

## Tasarım kararı: tek varlık ağacı, iki dil

Lab dosyaları (compose, Dockerfile, YAML manifest, kaynak kod) **dil-nötrdür**
ve tek kopya halinde tutulur. Yalnızca markdown dökümanlar iki dillidir.

```
labs/jenkins/
├── README.md          ← EN anlatım
├── README.tr.md       ← TR anlatım
├── hints.md
├── hints.tr.md
├── solution.md
├── solution.tr.md
└── infra/
    └── compose.yaml   ← tek kopya, her iki dil de bunu çalıştırır
```

Neden `en/` + `tr/` klasörleri değil:

1. Döküman içindeki göreli bağlantılar (`./infra/compose.yaml`) GitHub web
   arayüzünde ve klonlanmış repoda **her iki dilde de** doğru çalışır.
2. Öğrenci tek `git clone` ile her şeyi alır; dil seçimi okuma anında olur.
3. En önemlisi: TR ve EN labları **birebir aynı kodu** çalıştırır. Varlık
   ağacı ikizlenirse biri düzeltilip diğeri unutulur — upstream'de düzeltmeye
   çalıştığımız hatanın aynısı.

## Zorunlu kök dosyalar

| Dosya | Amaç |
|---|---|
| `index.md` / `index.tr.md` | Track ana sayfası, lab listesi |
| `manifest.json` | Makine okunur lab dizini — WordPress bunu okur |
| `LICENSE` | CC BY-SA 4.0 (upstream ile aynı olmak **zorunda**) |
| `ATTRIBUTION.md` | Upstream atfı — lisans gereği |
| `setup/README.md` + `.tr.md` | Ortam kurulumu |
| `VERSIONS.yaml` | `_platform/VERSIONS.yaml`'dan kopyalanır (CI senkronlar) |

## Markdown frontmatter

Her lab README'si frontmatter ile başlar; `manifest.json` bundan üretilir:

```yaml
---
title: Automation with Jenkins
lang: en
slug: jenkins
section: cicd
order: 1
duration: 45
requires: [docker]
status: updated          # updated | needs-review | upstream
upstream: labs/jenkins   # upstream'deki karşılığı (izlenebilirlik)
---
```

`status` alanı önemlidir:
- `upstream` — henüz dokunulmadı, 2021 hâli
- `needs-review` — modernize edildi ama canlı test edilmedi
- `updated` — modernize edildi **ve** uçtan uca çalıştırıldı

WordPress bu alanı okur; `updated` olmayan lablar "beta" etiketiyle gösterilir.

## Bölüm (section) tanımları

`sections.yaml` kökte durur, iki dilde başlık taşır:

```yaml
- slug: cicd
  titles: { en: "CI/CD Pipeline", tr: "CI/CD Pipeline" }
  order: 1
```
