# WordPress Eklentisi — Kurulum

`sudo2go-labs` eklentisi, lab dökümanlarını GitHub repolarından **canlı çekip**
sitenizde EN/TR olarak yayınlar. WordPress'e hiçbir lab metni kopyalanmaz:
tek doğruluk kaynağı repodur.

## Neden bu yaklaşım

Alternatif, 200+ markdown dosyasını WordPress sayfalarına kopyalamaktı. O
yolda ders ortasında bir hatayı düzelttiğinizde iki yerde düzeltmeniz gerekir
ve ikisi kaçınılmaz olarak birbirinden ayrışır. Burada repoya push ettiğiniz
düzeltme, önbellek süresi kadar sonra sitede canlı olur (ya da yönetim
ekranındaki tek düğmeyle hemen).

## Kurulum

### 1. Eklentiyi yükleyin

ZIP dosyası `_platform/wordpress/sudo2go-labs.zip` olarak hazır. Yeniden
üretmek gerekirse:

```bash
python _platform/wordpress/make-zip.py
```

> `zip` komutu yerine bu betik kullanılıyor: Windows PowerShell'in
> `Compress-Archive` komutu ZIP girdilerini ters bölü ile yazıyor ve Linux
> sunucuda bu, adında ters bölü olan tek bir dosyaya dönüşüp eklentiyi
> sessizce bozuyor. Betik düz bölü kullandığını doğrulayıp çıkıyor.

**En kısa yol — WordPress yönetim paneli:**

WordPress yönetimi → **Eklentiler → Yeni ekle → Eklenti yükle** → ZIP'i seçin
→ **Şimdi yükle** → **Etkinleştir**.

<details>
  <summary>Alternatif: cPanel Dosya Yöneticisi</summary>

WordPress paneline giremiyorsanız veya yükleme boyut sınırına takılıyorsanız:

1. cPanel → **Dosya Yöneticisi** (File Manager)
2. Sitenin kök dizinine gidin (genellikle `public_html`), sonra
   `wp-content/plugins/`
3. **Yükle** (Upload) → `sudo2go-labs.zip`
4. Yükleme bitince dosyaya sağ tıklayıp **Ayıkla** (Extract)
5. ZIP'i silin — `wp-content/plugins/sudo2go-labs/` klasörü kalmalı
6. WordPress yönetimi → **Eklentiler** → `sudo2go Labs` satırında
   **Etkinleştir**

Ayıklama sonrası klasör yapısı şöyle olmalı:

```
wp-content/plugins/sudo2go-labs/
├── sudo2go-labs.php
├── assets/
│   ├── labs.css
│   └── labs.js
└── includes/
    ├── class-client.php
    └── class-markdown.php
```

`sudo2go-labs/sudo2go-labs/` gibi iç içe bir klasör oluştuysa bir seviye
yukarı taşıyın; WordPress eklentiyi aksi halde görmez.

</details>

<details>
  <summary>Alternatif: WP-CLI (cPanel Terminal veya SSH gerekir)</summary>

> Bu yol cPanel'de **Terminal** erişimi ya da SSH gerektiriyor; paylaşımlı
> hosting paketlerinin çoğunda bu kapalı. Console erişiminiz yoksa yukarıdaki
> iki yoldan birini kullanın — ikisi de yalnızca panel üzerinden çalışır.

```bash
cd ~/public_html
wp plugin install /home/yasinoz/sudo2go-labs.zip --activate
wp option patch update sudo2go_labs_options page_slug labs
wp rewrite flush
```

Yol ve kullanıcı adı sizin hesabınıza göre değişir.

</details>

### 2. Lab sayfasını oluşturun

**Sayfalar → Yeni ekle**:

- Başlık: `Laboratuvarlar` (istediğiniz gibi)
- Kalıcı bağlantı (slug): `labs` — eklenti ayarındaki slug ile **aynı** olmalı
- İçerik: tek bir blok, içinde sadece kısa kod:

```
[sudo2go_labs]
```

> **Kısa kod bloğunu kullanın.** WordPress içerikteki düz tırnakları
> tipografik tırnağa çeviriyor (`wptexturize`). Paragraf bloğuna parametreli
> bir kısa kod yazarsanız `lang="tr"` sessizce `lang=“tr”` olabiliyor ve
> parametre yok sayılıyor. Eklenti 1.1.6'dan beri bunu tolere ediyor, ama
> **Kısa kod** bloğu yine de en güvenlisi.

Sayfayı yayınlayın. Tüm alt sayfalar (`/labs/tr/devsecops/jenkins` gibi) bu
tek sayfa üzerinden çalışır — her lab için ayrı WordPress sayfası açmanız
gerekmez.

### 3. Ayarları yapın — **genellikle gerekmez**

Eklenti varsayılan olarak doğru değerlerle geliyor: slug `labs`, varsayılan dil
`tr`, dört track `yasinoz/*` repolarına bakıyor. Yukarıdaki iki adımı
yaptıysanız site çalışır durumda olmalı.

Aşağıdaki tabloya yalnızca bir şeyi değiştirmek isterseniz bakın:

**Ayarlar → sudo2go Labs**:

| Alan | Değer |
|---|---|
| Sayfa slug | `labs` (2. adımdaki slug ile aynı) |
| Track listesi | Her satırda `slug\|owner\|repo\|branch` |
| Varsayılan dil | `tr` |
| Önbellek süresi | `600` (ders sırasında `60` yapın) |
| GitHub token | Boş bırakın (repolar genel) |

Varsayılan track listesi:

```
devsecops|yasinoz|devsecops|main
docker|yasinoz|docker|main
kubernetes|yasinoz|kubernetes|main
observability|yasinoz|observability|main
```

Kaydettikten sonra kalıcı bağlantılar otomatik yenilenir. Çalışmazsa
**Ayarlar → Kalıcı bağlantılar** sayfasını bir kez açıp kaydedin (WordPress'in
rewrite kurallarını yenilemesi için standart adım).

## URL yapısı

```
/labs/                                  tüm track'ler
/labs/tr/                               tüm track'ler (TR)
/labs/tr/devsecops/                     DevSecOps lab listesi
/labs/tr/devsecops/jenkins/             lab dökümanı
/labs/tr/devsecops/jenkins/hints/       ipuçları
/labs/tr/devsecops/jenkins/solution/    çözüm
/labs/en/devsecops/prometheus/metrics/  iki seviyeli lab slug'ı da çalışır
```

Rewrite kuralları henüz yazılmadıysa sorgu dizesi de çalışır:
`/labs/?s2g_lang=tr&s2g_track=devsecops&s2g_lab=jenkins`

## yasinoz.me icin ortam notlari

Site uzerinde yapilan kontroller (2026-10-20):

| Kontrol | Sonuc |
|---|---|
| WordPress | 7.1.3, Cloudflare arkasinda, LiteSpeed sunucu |
| Guzel kalici baglantilar | **Acik** (`/wp-json/` 200 donuyor) — eklentinin rewrite kurallari calisir |
| `/labs/` yolu | Bos (404) — baska bir sey tarafindan kullanilmiyor |
| GTranslate | `url_structure: "none"` — JavaScript widget modu, URL oneki **uretmiyor** (`/tr/` 404). `/labs/tr/...` ile cakisma yok |
| Dis HTTPS cikisi | Jetpack, Site Kit ve GTranslate CDN calisiyor — sunucunun dis dunyaya HTTPS cikisi var, GitHub'a erisim de beklenir |

### Onbellek: uc katman var, dikkat

Istek sirayla **Cloudflare -> LiteSpeed sayfa onbellegi -> WordPress** uzerinden
geciyor. Eklentinin kendi onbellegi (transient, varsayilan 600 sn) bunlarin
en altinda. Yani repoya push ettiginiz bir duzeltme, en yavas katman kadar
gecikmeyle gorunur.

Ders sirasinda duzeltme yapacaksaniz `/labs/*` yolunu sayfa onbelleginden
cikarin:

- **LiteSpeed Cache** eklentisi varsa: _Cache > Excludes > Do Not Cache URIs_
  alanina `/labs` yazin
- **Cloudflare**: Rules > Cache Rules ile `URI Path starts with /labs` icin
  _Bypass cache_ kurali ekleyin (ya da Development Mode'u gecici acin)
- Eklentinin kendi onbellegini **Ayarlar > sudo2go Labs > Onbellegi temizle**
  ile her zaman hemen bosaltabilirsiniz

Ders disinda uc katmanin da acik olmasi iyi: lab sayfalari statik metin
oldugu icin onbellekten servis edilmeleri siteyi hizlandirir.

### GTranslate ile birlikte

GTranslate sayfayi istemci tarafinda makine cevirisiyle degistiriyor. Lab
sayfalarinda zaten **insan cevirisi** TR metin sunuluyor, dolayisiyla
`/labs/tr/...` sayfalarinda GTranslate'i kullanmaya gerek yok. Ziyaretci
widget'tan ceviri secerse Turkce metin bir kez daha makine cevirisinden
gecebilir; isterseniz GTranslate ayarlarindan `/labs` yolunu haric tutun.

## Davranış notları

- **Dil yedeği.** Bir lab TR'ye çevrilmemişse İngilizcesi gösterilir ve
  öğrenciye bunun çeviri olmadığı açıkça yazılır. Liste ekranında `sadece EN`
  etiketi görünür. Çeviri durumu `manifest.json`'dan okunur; dosya yoksa o dil
  yayınlanmaz, yani "çevrildi" diye işaretlenip aslında çevrilmemiş bir lab
  yayına çıkamaz.
- **Beta etiketi.** `status: updated` olmayan lablar beta olarak işaretlenir.
  Bu alan "modernize edildi ama uçtan uca test edilmedi" demektir.
- **Önbellek.** Her dosya ayrı transient'ta tutulur. GitHub erişilemezse hata
  60 saniye negatif önbelleğe alınır; her sayfa yüklemesinde tekrar denenmez.
- **Göreli bağlantılar.** Lab içindeki `./infra/compose.yaml` gibi bağlantılar
  GitHub'a, başka bir lab dökümanına giden bağlantılar ise sitedeki lab
  sayfasına yönlendirilir.
- **Ham HTML.** Lablar ipuçları için `<details><summary>` kullanıyor; bu yapı
  korunur. `wp_kses` ile script/iframe/`on*` temizlenir.

## Doğrulanan ve doğrulanmayan kısımlar

**Doğrulandı** (CI'da, `.github/workflows/wordpress-plugin.yml`):

- Üç PHP dosyasının tamamı **PHP 7.4, 8.2 ve 8.4**'te `php -l` sözdizimi
  kontrolünden geçiyor. (Eklenti `Requires PHP: 7.4` diyor; en eski
  desteklenen sürümde de en güncelinde de ayrıştığı teyit edildi.)
- Kısa açma etiketi (`<?`) yok — sunucuda `short_open_tag` kapalıysa PHP
  kodunun ham metin olarak basılmasının klasik sebebi.
- Dosyalar BOM ile başlamıyor — "headers already sent" ve beyaz ekranın
  diğer klasik sebebi.
- Eklenti başlığı alanları ve metin alanı tutarlı.

**Doğrulanmadı:** eklenti canlı bir WordPress üzerinde **çalıştırılmadı**.
Sözdizimi doğru olması, çalışma zamanı davranışının doğru olduğunu
göstermiyor — kalıcı bağlantı kuralları, kısa kod çıktısı ve markdown
render'ı gerçek bir kurulumda görülmeli.

İlk kurulumda şu sırayla doğrulayın:

1. Eklenti etkinleşiyor mu (beyaz ekran yoksa PHP ayrıştırma sorunu yok)
2. `/labs/` track kartlarını listeliyor mu (GitHub erişimi + manifest okuma)
3. Bir lab açılıyor mu (markdown render)
4. Kod bloğundaki kopyala düğmesi çalışıyor mu

Sorun olursa `WP_DEBUG` açıp `wp-content/debug.log`'a bakın.
