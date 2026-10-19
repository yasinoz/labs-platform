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

`sudo2go-labs` klasörünü ZIP'leyip WordPress'e yükleyin:

```bash
cd _platform/wordpress && zip -r sudo2go-labs.zip sudo2go-labs
```

WordPress yönetimi → **Eklentiler → Yeni ekle → Eklenti yükle** → ZIP'i seçin
→ **Etkinleştir**.

> FTP/SSH erişiminiz varsa klasörü doğrudan `wp-content/plugins/` içine
> kopyalayabilirsiniz.

### 2. Lab sayfasını oluşturun

**Sayfalar → Yeni ekle**:

- Başlık: `Laboratuvarlar` (istediğiniz gibi)
- Kalıcı bağlantı (slug): `labs` — eklenti ayarındaki slug ile **aynı** olmalı
- İçerik: tek bir blok, içinde sadece kısa kod:

```
[sudo2go_labs]
```

Sayfayı yayınlayın. Tüm alt sayfalar (`/labs/tr/devsecops/jenkins` gibi) bu
tek sayfa üzerinden çalışır — her lab için ayrı WordPress sayfası açmanız
gerekmez.

### 3. Ayarları yapın

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
