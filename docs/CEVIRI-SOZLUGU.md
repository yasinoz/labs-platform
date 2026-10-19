# TR Çeviri Sözlüğü ve Üslup Kılavuzu

Dört track, ~74 lab, yüzlerce dosya. Tutarlılık olmazsa öğrenci aynı kavramı
üç farklı isimle görür ve kafası karışır. Bu dosya bağlayıcıdır.

## 1. Temel ilke: teknik terim çevrilmez, açıklanır

Terminalde yazılan hiçbir şey çevrilmez. Komutlar, bayraklar, dosya adları,
ortam değişkenleri, arayüz etiketleri İngilizce kalır. Çevrilen şey
**anlatım**dır.

> ❌ "Konteyner imajını inşa etmek için `docker inşa et` komutunu çalıştırın"
> ✅ "İmajı derlemek için `docker build` komutunu çalıştırın"

Arayüz etiketleri İngilizce kalır çünkü öğrenci ekranda İngilizce görecek.
İlk geçtiği yerde parantezle Türkçesi verilir:

> Sol menüden _Manage Jenkins_ (Jenkins yönetimi) bölümüne girin.

## 2. Terim tablosu

| İngilizce | Türkçe kullanım | Not |
|---|---|---|
| container | container | "Konteyner" de kabul; **repo içinde tek biçim: container** |
| image | imaj | "görüntü" ASLA kullanılmaz |
| registry | registry | "kayıt defteri" kullanılmaz |
| repository (git) | depo | |
| repository (image) | repository | imaj deposu bağlamında İngilizce |
| tag | etiket | `docker tag` komutu olarak geçiyorsa İngilizce |
| build (fiil) | derlemek / build almak | |
| build (isim, CI) | build | "yapı" kullanılmaz |
| pipeline | pipeline | "boru hattı" ASLA |
| stage (pipeline) | aşama | `stage` bloğu olarak geçerse İngilizce |
| job | job | "iş" kullanılmaz, karışıyor |
| workload | iş yükü | |
| deployment (k8s) | Deployment | Kubernetes nesnesi — İngilizce ve büyük harf |
| deployment (eylem) | dağıtım / yayına alma | |
| deploy (fiil) | dağıtmak / yayına almak | |
| rollout | rollout | |
| rollback | geri alma | |
| cluster | küme | |
| node | düğüm | |
| pod | Pod | k8s nesnesi |
| service | Service | k8s nesnesi; genel anlamda "servis" |
| namespace | namespace | "isim alanı" kullanılmaz |
| secret | Secret | k8s nesnesi; genel anlamda "sır/gizli bilgi" |
| volume | volume | "birim/hacim" ASLA |
| mount (fiil) | bağlamak | |
| scrape (prometheus) | toplama / scrape | ilk geçişte "veri toplama (scrape)" |
| metric | metrik | |
| dashboard | dashboard | "gösterge panosu" ilk geçişte parantezde |
| panel | panel | |
| query | sorgu | |
| log | log | "kayıt/günlük" kullanılmaz |
| trace | iz / trace | ilk geçişte "dağıtık iz (trace)" |
| span | span | |
| scanning | tarama | |
| vulnerability | güvenlik açığı | |
| finding | bulgu | |
| severity | önem derecesi | CRITICAL/HIGH vb. İngilizce |
| static analysis | statik analiz | |
| policy | politika | |
| admission controller | admission controller | parantezde "kabul denetleyici" |
| golden image | altın imaj | |
| hardening | sıkılaştırma | |
| least privilege | en az yetki | |
| supply chain | tedarik zinciri | |
| multi-stage build | çok aşamalı build | |
| layer | katman | |
| cache | önbellek | `--no-cache` gibi bayraklar İngilizce |
| host | host | "ana makine" kullanılmaz |
| endpoint | uç nokta | |
| credential | kimlik bilgisi | |
| commit | commit | |
| push / pull | push / pull | "itmek/çekmek" ASLA |
| branch | dal / branch | git komutu bağlamında branch |
| merge | merge | |
| lab | lab | "laboratuvar" sadece başlıklarda |
| exercise | alıştırma | |
| hint | ipucu | |
| solution | çözüm | |
| prerequisite | ön koşul | |

## 3. Üslup

- **Hitap: "siz" (çoğul/resmî).** "Çalıştırın", "açın", "göreceksiniz".
  Upstream İngilizce metin "we'll" diyor; Türkçede "şimdi ... edeceğiz" ya da
  doğrudan emir kipi kullanılır.
- **Kısa cümle.** Upstream'in uzun İngilizce cümleleri bölünür.
- Lab içinde öğrencinin yapacağı görevler 📋 ile başlar — bu işaret korunur.
- `<details><summary>` blokları korunur, `summary` metni çevrilir:
  - "Not sure?" → "Takıldınız mı?"
  - "Not sure how?" → "Nasıl yapılacağını bilmiyor musunuz?"
  - "Need a hint?" → "İpucu ister misiniz?"
- Alıntı blokları (`>`) öğretmen notudur, korunur ve çevrilir.
- Kod bloklarının içi **asla** çevrilmez; yalnızca kod içi `# yorum`lar çevrilir.
- Dış bağlantılar İngilizce kaynağa gider; Türkçe karşılığı varsa eklenir.

## 4. Çevrilmeyecek bölümler

- Komutlar, çıktı örnekleri, dosya/dizin adları
- `Reference` / `References` bölümündeki bağlantı başlıkları
- Ürün adları (Jenkins, Trivy, Prometheus...)
- Kaynak kod ve manifest içerikleri (yalnızca yorum satırları çevrilir)

## 5. Başlık kalıpları

| Bölüm (EN) | Bölüm (TR) |
|---|---|
| Reference / References | Kaynaklar |
| Lab | Lab |
| Hints | İpuçları |
| Solution | Çözüm |
| Cleanup | Temizlik |
| Pre-reqs / Prerequisites | Ön Koşullar |
| What's next | Sırada ne var |
| Credits | Emeği Geçenler |
