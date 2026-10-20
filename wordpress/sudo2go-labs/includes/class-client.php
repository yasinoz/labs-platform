<?php
/**
 * GitHub'dan lab icerigi cekme + onbellekleme.
 *
 * Tek dogruluk kaynagi repodur: WordPress'e hicbir lab metni kopyalanmaz.
 * Repoya push edilen bir duzeltme, onbellek suresi kadar sonra sitede canli
 * olur (veya yonetim ekranindaki "onbellegi temizle" ile hemen).
 *
 * @package Sudo2Go_Labs
 */

defined( 'ABSPATH' ) || exit;

class Sudo2Go_Client {

	const CACHE_PREFIX = 's2g_labs_';

	/** @var array Track yapilandirmasi. */
	private $track;

	/** @var int Onbellek suresi (saniye). */
	private $ttl;

	public function __construct( array $track, $ttl = 600 ) {
		$this->track = $track;
		$this->ttl   = max( 60, (int) $ttl );
	}

	private function raw_base() {
		return sprintf(
			'https://raw.githubusercontent.com/%s/%s/%s',
			rawurlencode( $this->track['owner'] ),
			rawurlencode( $this->track['repo'] ),
			rawurlencode( $this->track['branch'] )
		);
	}

	public function blob_base() {
		return sprintf(
			'https://github.com/%s/%s/blob/%s',
			rawurlencode( $this->track['owner'] ),
			rawurlencode( $this->track['repo'] ),
			rawurlencode( $this->track['branch'] )
		);
	}

	public function tree_base() {
		return sprintf(
			'https://github.com/%s/%s/tree/%s',
			rawurlencode( $this->track['owner'] ),
			rawurlencode( $this->track['repo'] ),
			rawurlencode( $this->track['branch'] )
		);
	}

	public function clone_url() {
		return sprintf( 'https://github.com/%s/%s.git', $this->track['owner'], $this->track['repo'] );
	}

	private function cache_key( $path ) {
		return self::CACHE_PREFIX . md5( $this->raw_base() . '|' . $path );
	}

	/**
	 * Uzun omurlu yedek kopyanin anahtari.
	 *
	 * Her basarili cekimde icerik buraya da yaziliyor. GitHub yavaslarsa ya
	 * da erisilemezse ogrenciye hata kutusu yerine son bilinen iyi kopya
	 * gosteriliyor - ders ortasinda bir ag hiccup'i labi bos bir sayfaya
	 * cevirmesin diye.
	 */
	private function backup_key( $path ) {
		return self::CACHE_PREFIX . 'bak_' . md5( $this->raw_base() . '|' . $path );
	}

	/**
	 * Repodan bir dosyayi getirir. Hata halinde WP_Error doner.
	 *
	 * @param string $path Repo koku icindeki yol, ornek: labs/jenkins/README.md
	 * @return string|WP_Error
	 */
	public function get_file( $path ) {
		$path = ltrim( str_replace( array( '..', "\0" ), '', $path ), '/' );
		$key  = $this->cache_key( $path );

		$cached = get_transient( $key );
		if ( false !== $cached ) {
			return is_array( $cached ) && isset( $cached['error'] )
				? new WP_Error( 's2g_cached_error', $cached['error'] )
				: $cached;
		}

		$args = array(
			// 20 sn: paylasimli hosting'den GitHub'a ilk cekim yavas olabiliyor.
			// (Canlida 10 sn'de zaman asimina ugrayan bir istek gorduk.)
			'timeout'     => 20,
			'redirection' => 3,
			'user-agent'  => 'sudo2go-labs/1.1 (+WordPress)',
			'headers'     => array( 'Accept' => 'text/plain' ),
		);

		$token = Sudo2Go_Labs::option( 'github_token' );
		if ( $token ) {
			// Ozel repo veya yuksek istek hacmi icin. Genel repoda gerekmez.
			$args['headers']['Authorization'] = 'Bearer ' . $token;
		}

		$url = $this->raw_base() . '/' . $path;

		// Zaman asimi gecici bir durum; bir kez daha deniyoruz. 404 gibi
		// kalici hatalarda tekrar denemenin anlami yok, o yuzden yalnizca
		// baglanti hatalarinda.
		$response = wp_remote_get( $url, $args );
		if ( is_wp_error( $response ) ) {
			$response = wp_remote_get( $url, $args );
		}

		if ( is_wp_error( $response ) ) {
			return $this->fallback( $key, $path, $response->get_error_message(), false );
		}

		$code = (int) wp_remote_retrieve_response_code( $response );
		if ( 200 !== $code ) {
			$msg = sprintf(
				/* translators: 1: HTTP kodu, 2: dosya yolu */
				__( 'GitHub %1$d dondu: %2$s', 'sudo2go-labs' ),
				$code,
				$path
			);
			// 404 kalici sayilir (dosya gercekten yok): yedege donmuyoruz ve
			// daha uzun sure negatif onbellege aliyoruz.
			return $this->fallback( $key, $path, $msg, 404 === $code );
		}

		$body = wp_remote_retrieve_body( $response );
		set_transient( $key, $body, $this->ttl );
		// Son bilinen iyi kopya: bir hafta. GitHub erisilemezse bu kullanilir.
		set_transient( $this->backup_key( $path ), $body, WEEK_IN_SECONDS );
		return $body;
	}

	/**
	 * Cekim basarisiz oldugunda ne doneceGini belirler.
	 *
	 * Once son bilinen iyi kopyaya bakiyoruz: GitHub yavaslarsa ogrenci
	 * bos bir hata kutusu degil (biraz eski olabilecek) lab metnini goruyor.
	 * Yedek yoksa hatayi donuyoruz ve kisa sureli negatif onbellege aliyoruz
	 * ki her sayfa yuklemesi yeniden beklemesin.
	 *
	 * @param string $key       Normal onbellek anahtari.
	 * @param string $path      Repo icindeki yol.
	 * @param string $message   Hata mesaji.
	 * @param bool   $permanent 404 gibi kalici hata mi (yedege donulmez).
	 * @return string|WP_Error
	 */
	private function fallback( $key, $path, $message, $permanent ) {
		if ( ! $permanent ) {
			$backup = get_transient( $this->backup_key( $path ) );
			if ( is_string( $backup ) && '' !== $backup ) {
				// Yedegi kisa sure normal onbellege de koyuyoruz: ayni istek
				// saniyeler icinde tekrar gelirse yine beklemesin.
				set_transient( $key, $backup, 120 );
				return $backup;
			}
		}
		set_transient( $key, array( 'error' => $message ), $permanent ? 300 : 60 );
		return new WP_Error( 's2g_fetch_failed', $message );
	}

	/**
	 * manifest.json'u cozumlenmis dizi olarak getirir.
	 *
	 * @return array|WP_Error
	 */
	public function get_manifest() {
		$raw = $this->get_file( 'manifest.json' );
		if ( is_wp_error( $raw ) ) {
			return $raw;
		}
		$data = json_decode( $raw, true );
		if ( ! is_array( $data ) || empty( $data['sections'] ) ) {
			return new WP_Error(
				's2g_bad_manifest',
				__( 'manifest.json okunamadi veya bos.', 'sudo2go-labs' )
			);
		}
		return $data;
	}

	/**
	 * Manifest icinde bir lab bulur.
	 *
	 * @return array|null ['lab' => array, 'section' => array]
	 */
	public static function find_lab( array $manifest, $slug ) {
		foreach ( $manifest['sections'] as $section ) {
			foreach ( $section['labs'] as $lab ) {
				if ( $lab['slug'] === $slug ) {
					return array(
						'lab'     => $lab,
						'section' => $section,
					);
				}
			}
		}
		return null;
	}

	/** Bu track'e ait tum onbellek kayitlarini siler. */
	public function flush() {
		return self::flush_all();
	}

	/** Eklentinin tum onbellegini siler (transient tablosundan dogrudan). */
	public static function flush_all() {
		global $wpdb;
		$like    = $wpdb->esc_like( '_transient_' . self::CACHE_PREFIX ) . '%';
		$timeout = $wpdb->esc_like( '_transient_timeout_' . self::CACHE_PREFIX ) . '%';
		$deleted = $wpdb->query(
			$wpdb->prepare(
				"DELETE FROM {$wpdb->options} WHERE option_name LIKE %s OR option_name LIKE %s",
				$like,
				$timeout
			)
		);
		wp_cache_flush();
		return (int) $deleted;
	}
}
