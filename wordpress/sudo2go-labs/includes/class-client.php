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
			'timeout'    => 12,
			'user-agent' => 'sudo2go-labs/1.0 (+WordPress)',
			'headers'    => array( 'Accept' => 'text/plain' ),
		);

		$token = Sudo2Go_Labs::option( 'github_token' );
		if ( $token ) {
			// Ozel repo veya yuksek istek hacmi icin. Genel repoda gerekmez.
			$args['headers']['Authorization'] = 'Bearer ' . $token;
		}

		$response = wp_remote_get( $this->raw_base() . '/' . $path, $args );

		if ( is_wp_error( $response ) ) {
			// Kisa sureli negatif onbellek: her sayfa yuklemesinde tekrar denemeyelim.
			set_transient( $key, array( 'error' => $response->get_error_message() ), 60 );
			return $response;
		}

		$code = (int) wp_remote_retrieve_response_code( $response );
		if ( 200 !== $code ) {
			$msg = sprintf(
				/* translators: 1: HTTP kodu, 2: dosya yolu */
				__( 'GitHub %1$d dondu: %2$s', 'sudo2go-labs' ),
				$code,
				$path
			);
			set_transient( $key, array( 'error' => $msg ), 404 === $code ? 300 : 60 );
			return new WP_Error( 's2g_http_' . $code, $msg );
		}

		$body = wp_remote_retrieve_body( $response );
		set_transient( $key, $body, $this->ttl );
		return $body;
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
