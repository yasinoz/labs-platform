<?php
/**
 * Plugin Name:       sudo2go Labs
 * Plugin URI:        https://github.com/yasinoz
 * Description:       DevOps / DevSecOps lab dokumanlarini GitHub repolarindan canli cekip EN/TR olarak yayinlar. Tek dogruluk kaynagi repodur; WordPress'e icerik kopyalanmaz.
 * Version:           1.1.7
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            Mehmet Yasin Ozkasapoglu
 * Text Domain:       sudo2go-labs
 *
 * @package Sudo2Go_Labs
 */

defined( 'ABSPATH' ) || exit;

define( 'SUDO2GO_LABS_VERSION', '1.1.7' );
define( 'SUDO2GO_LABS_DIR', plugin_dir_path( __FILE__ ) );
define( 'SUDO2GO_LABS_URL', plugin_dir_url( __FILE__ ) );

require_once SUDO2GO_LABS_DIR . 'includes/class-markdown.php';
require_once SUDO2GO_LABS_DIR . 'includes/class-client.php';

class Sudo2Go_Labs {

	const OPTION    = 'sudo2go_labs_options';
	const LANGS     = array( 'en', 'tr' );
	const QUERY_VARS = array( 's2g_lang', 's2g_track', 's2g_lab', 's2g_doc' );

	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'init', array( $this, 'register_rewrites' ) );
		add_filter( 'query_vars', array( $this, 'register_query_vars' ) );
		add_shortcode( 'sudo2go_labs', array( $this, 'shortcode' ) );
		add_action( 'wp_enqueue_scripts', array( $this, 'enqueue' ) );
		add_action( 'admin_menu', array( $this, 'admin_menu' ) );
		add_action( 'admin_init', array( $this, 'admin_init' ) );
		add_action( 'admin_post_s2g_flush', array( $this, 'handle_flush' ) );
		add_filter( 'document_title_parts', array( $this, 'filter_title' ) );
	}

	/* --------------------------------------------------------------- ayarlar */

	public static function defaults() {
		return array(
			'page_slug'    => 'labs',
			'cache_ttl'    => 600,
			'github_token' => '',
			'default_lang' => 'tr',
			'tracks'       => "devsecops|yasinoz|devsecops|main\n"
							. "docker|yasinoz|docker|main\n"
							. "kubernetes|yasinoz|kubernetes|main\n"
							. "observability|yasinoz|observability|main",
		);
	}

	public static function option( $key ) {
		$opts = wp_parse_args( (array) get_option( self::OPTION, array() ), self::defaults() );

		// wp_parse_args BOS DIZGIYI gecerli bir deger sayiyor, dolayisiyla
		// veritabaninda bos kalmis bir alan varsayilani ezebiliyor. Bos degeri
		// eksik sayip varsayilana donuyoruz - aksi halde ornegin bos bir
		// default_lang, dil secimini sessizce ingilizceye dusuruyordu.
		if ( ! isset( $opts[ $key ] ) || '' === $opts[ $key ] ) {
			$defaults = self::defaults();
			return isset( $defaults[ $key ] ) ? $defaults[ $key ] : null;
		}
		return $opts[ $key ];
	}

	/**
	 * Kisa kod parametresini editorun ona yaptigi seylerden arindirir.
	 *
	 * Icerik editorleri parametre degerini birden fazla sekilde bozabiliyor:
	 *   lang="tr"        istenen
	 *   lang=“tr”        wptexturize duz tirnagi tipografik tirnaga cevirir
	 *   lang=&quot;tr&quot;  tirnaklar HTML varligi olarak saklanir
	 * Ikinci ve ucuncu durumda kisa kod ayristiricisi degeri tirnaklarla
	 * birlikte veriyor ve parametre sessizce yok sayiliyordu.
	 *
	 * Once HTML varliklarini cozuyoruz, sonra harf/rakam disini atiyoruz.
	 * Beklenen degerler listesi verildiyse ve sonuc hala tutmuyorsa,
	 * dizgi icinde gecen ilk beklenen degeri ariyoruz - '&quot;tr&quot;'
	 * harf suzgecinden 'quottrquot' olarak cikiyor ve icinde 'tr' var.
	 *
	 * @param mixed    $value    Kisa koddan gelen ham deger.
	 * @param string[] $expected Izin verilen degerler (opsiyonel).
	 */
	private static function clean_att( $value, array $expected = array() ) {
		$value = html_entity_decode( (string) $value, ENT_QUOTES, 'UTF-8' );
		$value = strtolower( $value );
		$clean = preg_replace( '/[^a-z0-9_-]/', '', $value );

		if ( ! $expected || in_array( $clean, $expected, true ) ) {
			return $clean;
		}
		foreach ( $expected as $candidate ) {
			if ( false !== strpos( $clean, $candidate ) ) {
				return $candidate;
			}
		}
		return $clean;
	}

	/**
	 * Lab sayfasinin yolu - ic ice sayfalari destekler.
	 *
	 * Tek segment ('labs') kadar cok segment ('course-list/labs') de
	 * kabul edilir. Sitenin kendi bilgi mimarisine uymak icin: egitim
	 * icerigi /course-list/ altinda topluysa lab sayfasinin da oraya
	 * girmesi dogal olur.
	 *
	 * Her segment ayri ayri sanitize_title()'dan gecer; boylece butun
	 * yolu tek seferde sanitize edip bolu isaretlerini kaybetmiyoruz
	 * ('course-list/labs' -> 'course-listlabs' hatasi).
	 *
	 * @return string Bolu ile ayrilmis yol, bastan ve sondan bolusuz.
	 */
	public static function page_path() {
		$raw = (string) self::option( 'page_slug' );
		$parts = array();
		foreach ( explode( '/', $raw ) as $segment ) {
			$segment = sanitize_title( $segment );
			if ( '' !== $segment ) {
				$parts[] = $segment;
			}
		}
		return implode( '/', $parts );
	}

	/**
	 * Yapilandirilmis track'leri cozumler.
	 *
	 * Satir bicimi: slug|owner|repo|branch
	 *
	 * @return array<string,array>
	 */
	public static function tracks() {
		$out = array();
		foreach ( preg_split( '/\R/', (string) self::option( 'tracks' ) ) as $line ) {
			$line = trim( $line );
			if ( '' === $line || 0 === strpos( $line, '#' ) ) {
				continue;
			}
			$parts = array_map( 'trim', explode( '|', $line ) );
			if ( count( $parts ) < 3 ) {
				continue;
			}
			$slug = sanitize_key( $parts[0] );
			$out[ $slug ] = array(
				'slug'   => $slug,
				'owner'  => $parts[1],
				'repo'   => $parts[2],
				'branch' => isset( $parts[3] ) && $parts[3] ? $parts[3] : 'main',
			);
		}
		return $out;
	}

	/* ------------------------------------------------------------ yonlendirme */

	public function register_query_vars( $vars ) {
		return array_merge( $vars, self::QUERY_VARS );
	}

	public function register_rewrites() {
		// Ic ice sayfa yolu da olabilir: 'labs' ya da 'course-list/labs'.
		// pagename sorgu degiskeni zaten tam yolu bekliyor, dolayisiyla
		// ikisi de ayni sekilde calisiyor.
		$slug = self::page_path();
		if ( ! $slug ) {
			return;
		}
		$langs = implode( '|', self::LANGS );

		// /labs/tr/devsecops/jenkins/hints
		add_rewrite_rule(
			'^' . $slug . '/(' . $langs . ')/([^/]+)/([^/]+(?:/[^/]+)?)/(hints|solution)/?$',
			'index.php?pagename=' . $slug . '&s2g_lang=$matches[1]&s2g_track=$matches[2]&s2g_lab=$matches[3]&s2g_doc=$matches[4]',
			'top'
		);
		// /labs/tr/devsecops/prometheus/metrics  (iki seviyeli lab slug'i)
		add_rewrite_rule(
			'^' . $slug . '/(' . $langs . ')/([^/]+)/([^/]+(?:/[^/]+)?)/?$',
			'index.php?pagename=' . $slug . '&s2g_lang=$matches[1]&s2g_track=$matches[2]&s2g_lab=$matches[3]',
			'top'
		);
		// /labs/tr/devsecops
		add_rewrite_rule(
			'^' . $slug . '/(' . $langs . ')/([^/]+)/?$',
			'index.php?pagename=' . $slug . '&s2g_lang=$matches[1]&s2g_track=$matches[2]',
			'top'
		);
		// /labs/tr
		add_rewrite_rule(
			'^' . $slug . '/(' . $langs . ')/?$',
			'index.php?pagename=' . $slug . '&s2g_lang=$matches[1]',
			'top'
		);
	}

	private function current( $var, $fallback = '' ) {
		$val = get_query_var( $var );
		if ( '' === $val || null === $val ) {
			// Rewrite kurallari henuz yazilmamissa sorgu dizesi de calissin.
			$val = isset( $_GET[ $var ] ) ? sanitize_text_field( wp_unslash( $_GET[ $var ] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		}
		return '' !== $val ? $val : $fallback;
	}

	private function lang() {
		$lang = $this->current( 's2g_lang', self::option( 'default_lang' ) );
		if ( in_array( $lang, self::LANGS, true ) ) {
			return $lang;
		}
		// Gecersiz ya da bos deger geldiginde sabit 'en' yerine YAPILANDIRILMIS
		// varsayilana donuyoruz. Eski hali, ayar bozuksa siteyi sessizce
		// ingilizceye dusuruyordu - Turkce varsayilanli bir sitede yanlis.
		$fallback = self::defaults()['default_lang'];
		return in_array( $fallback, self::LANGS, true ) ? $fallback : 'en';
	}

	public function url( $lang = null, $track = null, $lab = null, $doc = null ) {
		$slug = self::page_path();
		$path = array( $slug );
		if ( $lang ) {
			$path[] = $lang;
		}
		if ( $track ) {
			$path[] = $track;
		}
		if ( $lab ) {
			$path[] = $lab;
		}
		if ( $doc ) {
			$path[] = $doc;
		}
		return home_url( '/' . implode( '/', $path ) . '/' );
	}

	/* ---------------------------------------------------------------- varliklar */

	public function enqueue() {
		if ( ! is_page() ) {
			return;
		}
		wp_enqueue_style( 'sudo2go-labs', SUDO2GO_LABS_URL . 'assets/labs.css', array(), SUDO2GO_LABS_VERSION );
		wp_enqueue_script( 'sudo2go-labs', SUDO2GO_LABS_URL . 'assets/labs.js', array(), SUDO2GO_LABS_VERSION, true );
		wp_localize_script(
			'sudo2go-labs',
			'S2G_LABS',
			array(
				'copied' => __( 'Kopyalandi', 'sudo2go-labs' ),
				'copy'   => __( 'Kopyala', 'sudo2go-labs' ),
			)
		);
	}

	public function filter_title( $parts ) {
		$lab = $this->current( 's2g_lab' );
		if ( $lab ) {
			$parts['title'] = ucwords( str_replace( array( '-', '/' ), array( ' ', ' / ' ), $lab ) );
		}
		return $parts;
	}

	/* ---------------------------------------------------------------- cikti */

	public function shortcode( $atts ) {
		$atts = shortcode_atts( array( 'track' => '', 'lang' => '' ), $atts, 'sudo2go_labs' );

		// Kisa kod parametrelerini temizle.
		//
		// WordPress icerikteki duz tirnaklari tipografik tirnaga ceviriyor
		// (wptexturize). Sonucta lang="tr" yerine lang=“tr” kalabiliyor ve
		// kisa kod ayristiricisi degeri tirnaklarla birlikte, yani “tr”
		// olarak veriyor; gecerli dil listesinde bulunamadigi icin parametre
		// sessizce yok sayiliyordu. Harf disi her seyi atarak bunu
		// tolere ediyoruz - yazim tirnagi, bosluk, gizli karakter farketmez.
		$atts['lang']  = self::clean_att( $atts['lang'], self::LANGS );
		$atts['track'] = self::clean_att( $atts['track'] );

		// Dil onceligi: URL > kisa kod parametresi > ayar.
		//
		// Onceki hali kisa kod parametresini URL'nin ONUNE koyuyordu; yani
		// [sudo2go_labs lang="tr"] yazildiginda /labs/en/... rotalari da
		// turkce geliyordu ve dil secici ise yaramiyordu. Kisa kod parametresi
		// bir VARSAYILAN olmali, URL her zaman kazanmali.
		$url_lang = $this->current( 's2g_lang', '' );
		if ( in_array( $url_lang, self::LANGS, true ) ) {
			$lang = $url_lang;
		} elseif ( $atts['lang'] && in_array( $atts['lang'], self::LANGS, true ) ) {
			$lang = $atts['lang'];
		} else {
			$lang = $this->lang();
		}
		$track = $atts['track'] ? sanitize_key( $atts['track'] ) : sanitize_key( $this->current( 's2g_track' ) );
		$lab   = $this->current( 's2g_lab' );
		$doc   = $this->current( 's2g_doc' );

		$tracks = self::tracks();

		if ( ! $track || ! isset( $tracks[ $track ] ) ) {
			return $this->view_home( $lang, $tracks );
		}

		$client   = new Sudo2Go_Client( $tracks[ $track ], (int) self::option( 'cache_ttl' ) );
		$manifest = $client->get_manifest();
		if ( is_wp_error( $manifest ) ) {
			return $this->error_box( $manifest->get_error_message(), $track );
		}

		if ( $lab ) {
			return $this->view_lab( $lang, $track, $lab, $doc, $manifest, $client );
		}
		return $this->view_track( $lang, $track, $manifest, $client );
	}

	private function t( $lang, $en, $tr ) {
		return 'tr' === $lang ? $tr : $en;
	}

	private function pick( $map, $lang, $fallback = '' ) {
		if ( ! is_array( $map ) ) {
			return $fallback;
		}
		if ( ! empty( $map[ $lang ] ) ) {
			return $map[ $lang ];
		}
		return ! empty( $map['en'] ) ? $map['en'] : $fallback;
	}

	private function lang_switch( $lang, $track = null, $lab = null, $doc = null, $available = null ) {
		$html = '<div class="s2g-langs">';
		foreach ( self::LANGS as $code ) {
			$label  = strtoupper( $code );
			$active = $code === $lang ? ' s2g-on' : '';
			$missing = ( is_array( $available ) && ! in_array( $code, $available, true ) ) ? ' s2g-missing' : '';
			$html  .= sprintf(
				'<a class="s2g-lang%s%s" href="%s" hreflang="%s">%s</a>',
				esc_attr( $active ),
				esc_attr( $missing ),
				esc_url( $this->url( $code, $track, $lab, $doc ) ),
				esc_attr( $code ),
				esc_html( $label )
			);
		}
		return $html . '</div>';
	}

	/** Tum track'leri listeleyen giris ekrani. */
	private function view_home( $lang, $tracks ) {
		$html  = '<div class="s2g">';
		$html .= $this->lang_switch( $lang );
		$html .= '<h1 class="s2g-title">' . esc_html( $this->t( $lang, 'Hands-on Labs', 'Uygulamali Laboratuvarlar' ) ) . '</h1>';
		$html .= '<p class="s2g-lede">' . esc_html( $this->t(
			$lang,
			'Pick a track. Every lab runs on your own machine with Docker - no cloud account needed.',
			'Bir track secin. Her lab kendi makinenizde Docker ile calisir - bulut hesabi gerekmez.'
		) ) . '</p>';
		$html .= '<div class="s2g-grid">';
		foreach ( $tracks as $slug => $track ) {
			$client   = new Sudo2Go_Client( $track, (int) self::option( 'cache_ttl' ) );
			$manifest = $client->get_manifest();
			$title    = $slug;
			$summary  = '';
			$count    = null;
			if ( ! is_wp_error( $manifest ) ) {
				$title   = $this->pick( $manifest['track']['titles'] ?? array(), $lang, $slug );
				$summary = $this->pick( $manifest['track']['summaries'] ?? array(), $lang, '' );
				$count   = isset( $manifest['stats']['total'] ) ? (int) $manifest['stats']['total'] : null;
			} else {
				// Manifest cekilemedi: kart ham slug ile ciziliyor. Bu bozuk
				// cikti sayfa onbellegine girmesin, yoksa gecici bir aksaklik
				// kalici hale geliyor.
				$this->prevent_caching();
			}
			$html .= sprintf(
				'<a class="s2g-card" href="%s"><h2>%s</h2><p>%s</p>%s</a>',
				esc_url( $this->url( $lang, $slug ) ),
				esc_html( $title ),
				esc_html( $summary ),
				null === $count ? '' : '<span class="s2g-count">' . sprintf(
					/* translators: %d: lab sayisi */
					esc_html( $this->t( $lang, '%d labs', '%d lab' ) ),
					$count
				) . '</span>'
			);
		}
		return $html . '</div></div>';
	}

	/** Bir track'in lab listesi. */
	private function view_track( $lang, $track, $manifest, Sudo2Go_Client $client ) {
		$title   = $this->pick( $manifest['track']['titles'] ?? array(), $lang, $track );
		$summary = $this->pick( $manifest['track']['summaries'] ?? array(), $lang, '' );

		$html  = '<div class="s2g">';
		$html .= $this->lang_switch( $lang, $track, null, null, $manifest['languages'] ?? null );
		$html .= '<nav class="s2g-crumbs"><a href="' . esc_url( $this->url( $lang ) ) . '">'
			. esc_html( $this->t( $lang, 'Labs', 'Laboratuvarlar' ) ) . '</a> / <span>'
			. esc_html( $title ) . '</span></nav>';
		$html .= '<h1 class="s2g-title">' . esc_html( $title ) . '</h1>';
		$html .= '<p class="s2g-lede">' . esc_html( $summary ) . '</p>';

		// Ogrenci icin ilk adim: repoyu klonla
		$html .= '<div class="s2g-start"><h2>' . esc_html( $this->t( $lang, 'Before you start', 'Baslamadan once' ) ) . '</h2>';
		$html .= '<p>' . esc_html( $this->t(
			$lang,
			'Clone the repo so you have all the lab files locally:',
			'Lab dosyalarinin tamamini yerelde bulundurmak icin repoyu klonlayin:'
		) ) . '</p>';
		$html .= '<div class="s2g-code" data-lang="shell"><button type="button" class="s2g-copy">'
			. esc_html__( 'Kopyala', 'sudo2go-labs' ) . '</button><pre><code>git clone '
			. esc_html( $client->clone_url() ) . '</code></pre></div>';
		if ( ! empty( $manifest['setup'][ $lang ] ) ) {
			$html .= '<p><a class="s2g-btn" href="' . esc_url( $client->blob_base() . '/' . $manifest['setup'][ $lang ] ) . '" target="_blank" rel="noopener noreferrer">'
				. esc_html( $this->t( $lang, 'Environment setup guide', 'Ortam kurulum kilavuzu' ) ) . '</a></p>';
		}
		$html .= '</div>';

		foreach ( $manifest['sections'] as $section ) {
			$html .= '<section class="s2g-section"><h2>' . esc_html( $this->pick( $section['titles'], $lang, $section['slug'] ) ) . '</h2>';
			$sum   = $this->pick( $section['summaries'] ?? array(), $lang, '' );
			if ( $sum ) {
				$html .= '<p class="s2g-secsum">' . esc_html( $sum ) . '</p>';
			}
			$html .= '<ol class="s2g-labs">';
			foreach ( $section['labs'] as $lab ) {
				$has    = in_array( $lang, (array) ( $lab['langs'] ?? array() ), true );
				$ltitle = $this->pick( $lab['titles'], $lang, $lab['slug'] );
				$badges = '';
				if ( ! empty( $lab['duration'] ) ) {
					$badges .= '<span class="s2g-badge">' . (int) $lab['duration'] . ' dk</span>';
				}
				foreach ( (array) ( $lab['requires'] ?? array() ) as $req ) {
					$badges .= '<span class="s2g-badge s2g-req">' . esc_html( $req ) . '</span>';
				}
				if ( 'updated' !== ( $lab['status'] ?? '' ) ) {
					$badges .= '<span class="s2g-badge s2g-beta">' . esc_html( $this->t( $lang, 'beta', 'beta' ) ) . '</span>';
				}
				if ( ! $has ) {
					$badges .= '<span class="s2g-badge s2g-en">' . esc_html( $this->t( $lang, 'EN only', 'sadece EN' ) ) . '</span>';
				}
				$html .= sprintf(
					'<li><a href="%s"><span class="s2g-labname">%s</span>%s</a></li>',
					esc_url( $this->url( $lang, $track, $lab['slug'] ) ),
					esc_html( $ltitle ),
					$badges
				);
			}
			$html .= '</ol></section>';
		}

		$html .= '<p class="s2g-src">' . sprintf(
			/* translators: %s: GitHub baglantisi */
			esc_html( $this->t( $lang, 'Source: %s', 'Kaynak: %s' ) ),
			'<a href="' . esc_url( $client->tree_base() ) . '" target="_blank" rel="noopener noreferrer">GitHub</a>'
		) . '</p>';

		return $html . '</div>';
	}

	/** Tek lab sayfasi. */
	private function view_lab( $lang, $track, $lab_slug, $doc, $manifest, Sudo2Go_Client $client ) {
		$found = Sudo2Go_Client::find_lab( $manifest, $lab_slug );
		if ( ! $found ) {
			return $this->error_box(
				sprintf(
					/* translators: %s: lab slug */
					__( 'Lab bulunamadi: %s', 'sudo2go-labs' ),
					esc_html( $lab_slug )
				),
				$track
			);
		}
		$lab     = $found['lab'];
		$section = $found['section'];
		$langs   = (array) ( $lab['langs'] ?? array( 'en' ) );

		// Istenen dilde yoksa EN'e dus ve bunu ogrenciye SOYLE.
		$use_lang = in_array( $lang, $langs, true ) ? $lang : 'en';
		$kind     = in_array( $doc, array( 'hints', 'solution' ), true ) ? $doc : 'readme';

		$docs = $lab['docs'][ $use_lang ] ?? array();
		if ( empty( $docs[ $kind ] ) ) {
			$kind = 'readme';
		}
		if ( empty( $docs[ $kind ] ) ) {
			return $this->error_box( __( 'Bu lab icin dokuman bulunamadi.', 'sudo2go-labs' ), $track );
		}

		$raw = $client->get_file( $docs[ $kind ] );
		if ( is_wp_error( $raw ) ) {
			return $this->error_box( $raw->get_error_message(), $track );
		}

		list( $meta, $body ) = Sudo2Go_Markdown::split_frontmatter( $raw );

		$md       = new Sudo2Go_Markdown();
		$lab_dir  = $lab['path'];
		$md->set_link_filter(
			$lab_dir,
			function ( $target, $base, $is_image ) use ( $client, $lang, $track, $manifest ) {
				return $this->rewrite_link( $target, $base, $is_image, $client, $lang, $track, $manifest );
			}
		);
		$content  = $md->render( $body );
		$headings = $md->get_headings();

		$title = $this->pick( $lab['titles'], $use_lang, $meta['title'] ?? $lab_slug );

		$html  = '<div class="s2g s2g-lab">';
		$html .= $this->lang_switch( $lang, $track, $lab_slug, $doc, $langs );
		$html .= '<nav class="s2g-crumbs">';
		$html .= '<a href="' . esc_url( $this->url( $lang ) ) . '">' . esc_html( $this->t( $lang, 'Labs', 'Laboratuvarlar' ) ) . '</a> / ';
		$html .= '<a href="' . esc_url( $this->url( $lang, $track ) ) . '">' . esc_html( $this->pick( $manifest['track']['titles'] ?? array(), $lang, $track ) ) . '</a> / ';
		$html .= '<span>' . esc_html( $this->pick( $section['titles'], $lang, $section['slug'] ) ) . '</span>';
		$html .= '</nav>';

		if ( $use_lang !== $lang ) {
			$html .= '<div class="s2g-notice">' . esc_html( $this->t(
				$lang,
				'This lab has not been translated yet - showing the English version.',
				'Bu lab henuz cevrilmedi - Ingilizce surumu gosteriliyor.'
			) ) . '</div>';
		}
		if ( 'updated' !== ( $lab['status'] ?? '' ) ) {
			$html .= '<div class="s2g-notice s2g-beta-note">' . esc_html( $this->t(
				$lang,
				'This lab has been modernised but not yet verified end to end. Tell us if something breaks.',
				'Bu lab modernize edildi ama ucтan uca dogrulanmadi. Takilirsaniz bize bildirin.'
			) ) . '</div>';
		}

		$html .= '<h1 class="s2g-title">' . esc_html( $title ) . '</h1>';

		// Lab ust bilgi cubugu
		$html .= '<div class="s2g-meta">';
		if ( ! empty( $lab['duration'] ) ) {
			$html .= '<span class="s2g-badge">' . (int) $lab['duration'] . ' dk</span>';
		}
		foreach ( (array) ( $lab['requires'] ?? array() ) as $req ) {
			$html .= '<span class="s2g-badge s2g-req">' . esc_html( $req ) . '</span>';
		}
		$html .= '<a class="s2g-ghlink" href="' . esc_url( $client->blob_base() . '/' . $docs[ $kind ] ) . '" target="_blank" rel="noopener noreferrer">'
			. esc_html( $this->t( $lang, 'View on GitHub', 'GitHub\'da gor' ) ) . '</a>';
		$html .= '</div>';

		// Dokuman sekmeleri: lab / ipucu / cozum
		$tabs = array(
			'readme'   => $this->t( $lang, 'Lab', 'Lab' ),
			'hints'    => $this->t( $lang, 'Hints', 'Ipuclari' ),
			'solution' => $this->t( $lang, 'Solution', 'Cozum' ),
		);
		$html .= '<div class="s2g-tabs">';
		foreach ( $tabs as $key => $label ) {
			if ( empty( $docs[ $key ] ) ) {
				continue;
			}
			$href = $this->url( $lang, $track, $lab_slug, 'readme' === $key ? null : $key );
			$html .= sprintf(
				'<a class="s2g-tab%s" href="%s">%s</a>',
				$key === $kind ? ' s2g-on' : '',
				esc_url( $href ),
				esc_html( $label )
			);
		}
		$html .= '</div>';

		if ( count( $headings ) > 2 ) {
			$html .= '<details class="s2g-toc"><summary>' . esc_html( $this->t( $lang, 'On this page', 'Bu sayfada' ) ) . '</summary><ul>';
			foreach ( $headings as $h ) {
				$html .= sprintf(
					'<li class="s2g-toc-l%d"><a href="#%s">%s</a></li>',
					(int) $h['level'],
					esc_attr( $h['id'] ),
					esc_html( $h['text'] )
				);
			}
			$html .= '</ul></details>';
		}

		$html .= '<article class="s2g-body">' . $content . '</article>';
		$html .= $this->lab_nav( $lang, $track, $lab_slug, $manifest );

		return $html . '</div>';
	}

	/** Onceki / sonraki lab baglantilari. */
	private function lab_nav( $lang, $track, $current, $manifest ) {
		$flat = array();
		foreach ( $manifest['sections'] as $section ) {
			foreach ( $section['labs'] as $lab ) {
				$flat[] = $lab;
			}
		}
		$idx = null;
		foreach ( $flat as $i => $lab ) {
			if ( $lab['slug'] === $current ) {
				$idx = $i;
				break;
			}
		}
		if ( null === $idx ) {
			return '';
		}
		$html = '<nav class="s2g-prevnext">';
		if ( $idx > 0 ) {
			$prev  = $flat[ $idx - 1 ];
			$html .= '<a class="s2g-prev" href="' . esc_url( $this->url( $lang, $track, $prev['slug'] ) ) . '"><span>'
				. esc_html( $this->t( $lang, 'Previous', 'Onceki' ) ) . '</span>'
				. esc_html( $this->pick( $prev['titles'], $lang, $prev['slug'] ) ) . '</a>';
		}
		if ( $idx < count( $flat ) - 1 ) {
			$next  = $flat[ $idx + 1 ];
			$html .= '<a class="s2g-next" href="' . esc_url( $this->url( $lang, $track, $next['slug'] ) ) . '"><span>'
				. esc_html( $this->t( $lang, 'Next', 'Sonraki' ) ) . '</span>'
				. esc_html( $this->pick( $next['titles'], $lang, $next['slug'] ) ) . '</a>';
		}
		return $html . '</nav>';
	}

	/**
	 * Markdown icindeki goreli baglantilari cozer.
	 *
	 * - Baska bir lab dokumani  -> WordPress lab sayfasi
	 * - Lab varligi (yaml, Dockerfile, kaynak) -> GitHub blob
	 * - Resim -> GitHub raw
	 */
	private function rewrite_link( $target, $base, $is_image, Sudo2Go_Client $client, $lang, $track, $manifest ) {
		$path = $target;
		// Goreli yolu repo koku bazina normalize et
		if ( 0 !== strpos( $path, '/' ) ) {
			$path = $base . '/' . $path;
		}
		$path = ltrim( $path, '/' );
		$segments = array();
		foreach ( explode( '/', $path ) as $seg ) {
			if ( '.' === $seg || '' === $seg ) {
				continue;
			}
			if ( '..' === $seg ) {
				array_pop( $segments );
				continue;
			}
			$segments[] = $seg;
		}
		$path = implode( '/', $segments );

		if ( $is_image ) {
			$tracks = self::tracks();
			if ( ! isset( $tracks[ $track ] ) ) {
				return $client->blob_base() . '/' . $path;
			}
			$cfg = $tracks[ $track ];
			return sprintf(
				'https://raw.githubusercontent.com/%s/%s/%s/%s',
				rawurlencode( $cfg['owner'] ),
				rawurlencode( $cfg['repo'] ),
				rawurlencode( $cfg['branch'] ),
				$path
			);
		}

		// Baska bir lab dokumanina mi gidiyor?
		if ( preg_match( '#^labs/(.+?)/(README|hints|solution)(\.tr)?\.md$#', $path, $m ) ) {
			$slug = $m[1];
			$kind = strtolower( $m[2] );
			if ( Sudo2Go_Client::find_lab( $manifest, $slug ) ) {
				return $this->url( $lang, $track, $slug, 'readme' === $kind ? null : $kind );
			}
		}
		// Kurulum dokumani
		if ( preg_match( '#^setup/README(\.tr)?\.md$#', $path ) ) {
			return $client->blob_base() . '/' . $path;
		}

		return $client->blob_base() . '/' . $path;
	}

	/**
	 * Hata ciktisinin sayfa onbellegine ALINMASINI engeller.
	 *
	 * Canlida gorulen senaryo: GitHub'a yapilan tek bir istek zaman asimina
	 * ugradi, eklenti hata kutusu bastirdi ve LiteSpeed o sayfayi
	 * max-age=604800 ile onbellege aldi. Yani bir haftalik gecici bir aksaklik
	 * kalici bir "Lab icerigi yuklenemedi" sayfasina dondu.
	 *
	 * DONOTCACHEPAGE sabitini LiteSpeed, W3 Total Cache, WP Super Cache ve
	 * WP Rocket taniyor; istek sonunda tamponu saklamaya karar verirken
	 * bakiyorlar, dolayisiyla kisa kod icinde tanimlamak yeterli.
	 */
	private function prevent_caching() {
		if ( ! defined( 'DONOTCACHEPAGE' ) ) {
			define( 'DONOTCACHEPAGE', true );
		}
		// LiteSpeed'in kendi kontrolu - eklenti aktifse daha kesin.
		do_action( 'litespeed_control_set_nocache', 'sudo2go-labs: icerik cekilemedi' );
		if ( ! headers_sent() ) {
			nocache_headers();
		}
	}

	private function error_box( $message, $track = '' ) {
		$this->prevent_caching();
		$html  = '<div class="s2g"><div class="s2g-error">';
		$html .= '<strong>' . esc_html__( 'Lab icerigi yuklenemedi.', 'sudo2go-labs' ) . '</strong>';
		$html .= '<p>' . esc_html( $message ) . '</p>';
		if ( current_user_can( 'manage_options' ) ) {
			$html .= '<p class="s2g-hint">' . esc_html__(
				'Yonetici notu: repo/branch adlarini ve manifest.json varligini kontrol edin. Ayarlar > sudo2go Labs.',
				'sudo2go-labs'
			) . '</p>';
		}
		return $html . '</div></div>';
	}

	/* ------------------------------------------------------------- yonetim */

	public function admin_menu() {
		add_options_page(
			__( 'sudo2go Labs', 'sudo2go-labs' ),
			__( 'sudo2go Labs', 'sudo2go-labs' ),
			'manage_options',
			'sudo2go-labs',
			array( $this, 'settings_page' )
		);
	}

	public function admin_init() {
		register_setting(
			'sudo2go_labs',
			self::OPTION,
			array(
				'type'              => 'array',
				'sanitize_callback' => array( $this, 'sanitize_options' ),
				'default'           => self::defaults(),
			)
		);
	}

	public function sanitize_options( $input ) {
		$out                 = self::defaults();
		// Ic ice yol destegi: her segmenti ayri ayri sanitize ediyoruz,
		// yoksa 'course-list/labs' tek parcaya cokup bolu kayboluyor.
		$raw_slug = (string) ( $input['page_slug'] ?? 'labs' );
		$segments = array();
		foreach ( explode( '/', $raw_slug ) as $segment ) {
			$segment = sanitize_title( $segment );
			if ( '' !== $segment ) {
				$segments[] = $segment;
			}
		}
		$out['page_slug'] = $segments ? implode( '/', $segments ) : 'labs';
		$out['cache_ttl']    = max( 60, (int) ( $input['cache_ttl'] ?? 600 ) );
		$out['github_token'] = sanitize_text_field( $input['github_token'] ?? '' );
		$lang                = $input['default_lang'] ?? 'tr';
		$out['default_lang'] = in_array( $lang, self::LANGS, true ) ? $lang : 'tr';
		$out['tracks']       = sanitize_textarea_field( $input['tracks'] ?? $out['tracks'] );
		// Yonlendirme kurallari slug degistiginde yenilenmeli.
		add_action( 'shutdown', 'flush_rewrite_rules' );
		return $out;
	}

	public function handle_flush() {
		if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 's2g_flush' ) ) {
			wp_die( esc_html__( 'Yetkisiz islem.', 'sudo2go-labs' ) );
		}
		$n = Sudo2Go_Client::flush_all();
		flush_rewrite_rules();
		wp_safe_redirect(
			add_query_arg(
				array( 'page' => 'sudo2go-labs', 's2g_flushed' => $n ),
				admin_url( 'options-general.php' )
			)
		);
		exit;
	}

	public function settings_page() {
		// option() uzerinden okuyoruz: bos ya da gecersiz degerleri varsayilana
		// cevirir. Dogrudan wp_parse_args kullanildiginda, veritabaninda bos
		// kalmis bir default_lang hicbir <option>'i secili yapmiyor ve tarayici
		// ILK secenegi (EN) seciyordu - kaydedilince de 'en' olarak kaliciydi.
		$opts = array();
		foreach ( self::defaults() as $key => $unused ) {
			$opts[ $key ] = self::option( $key );
		}
		?>
		<div class="wrap">
			<h1><?php esc_html_e( 'sudo2go Labs', 'sudo2go-labs' ); ?></h1>

			<?php if ( isset( $_GET['s2g_flushed'] ) ) : // phpcs:ignore WordPress.Security.NonceVerification.Recommended ?>
				<div class="notice notice-success is-dismissible"><p>
					<?php
					printf(
						/* translators: %d: silinen kayit sayisi */
						esc_html__( 'Onbellek temizlendi (%d kayit) ve yonlendirme kurallari yenilendi.', 'sudo2go-labs' ),
						(int) $_GET['s2g_flushed'] // phpcs:ignore WordPress.Security.NonceVerification.Recommended
					);
					?>
				</p></div>
			<?php endif; ?>

			<form method="post" action="options.php">
				<?php settings_fields( 'sudo2go_labs' ); ?>
				<table class="form-table" role="presentation">
					<tr>
						<th scope="row"><label for="s2g_page_slug"><?php esc_html_e( 'Sayfa slug', 'sudo2go-labs' ); ?></label></th>
						<td>
							<input name="<?php echo esc_attr( self::OPTION ); ?>[page_slug]" id="s2g_page_slug" type="text"
								value="<?php echo esc_attr( $opts['page_slug'] ); ?>" class="regular-text" />
							<p class="description">
								<?php esc_html_e( 'Bu yolda bir WordPress sayfasi olusturun ve icine [sudo2go_labs] kisa kodunu koyun. Sayfa olmadan hicbir sey gorunmez.', 'sudo2go-labs' ); ?>
								<br />
								<?php esc_html_e( 'Ic ice sayfa da olur: ornegin course-list/labs. O durumda labs sayfasini course-list sayfasinin alt sayfasi yapin.', 'sudo2go-labs' ); ?>
							</p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="s2g_tracks"><?php esc_html_e( 'Track listesi', 'sudo2go-labs' ); ?></label></th>
						<td>
							<textarea name="<?php echo esc_attr( self::OPTION ); ?>[tracks]" id="s2g_tracks" rows="6" class="large-text code"><?php echo esc_textarea( $opts['tracks'] ); ?></textarea>
							<p class="description"><code>slug|owner|repo|branch</code> &mdash; her satirda bir track.</p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="s2g_lang"><?php esc_html_e( 'Varsayilan dil', 'sudo2go-labs' ); ?></label></th>
						<td>
							<select name="<?php echo esc_attr( self::OPTION ); ?>[default_lang]" id="s2g_lang">
								<?php foreach ( self::LANGS as $code ) : ?>
									<option value="<?php echo esc_attr( $code ); ?>" <?php selected( $opts['default_lang'], $code ); ?>><?php echo esc_html( strtoupper( $code ) ); ?></option>
								<?php endforeach; ?>
							</select>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="s2g_ttl"><?php esc_html_e( 'Onbellek suresi (saniye)', 'sudo2go-labs' ); ?></label></th>
						<td>
							<input name="<?php echo esc_attr( self::OPTION ); ?>[cache_ttl]" id="s2g_ttl" type="number" min="60" step="60"
								value="<?php echo esc_attr( $opts['cache_ttl'] ); ?>" class="small-text" />
							<p class="description"><?php esc_html_e( 'Ders sirasinda duzeltme yapacaksaniz 60 yapin; normalde 600 yeterli.', 'sudo2go-labs' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="s2g_token"><?php esc_html_e( 'GitHub token (opsiyonel)', 'sudo2go-labs' ); ?></label></th>
						<td>
							<input name="<?php echo esc_attr( self::OPTION ); ?>[github_token]" id="s2g_token" type="password" autocomplete="new-password"
								value="<?php echo esc_attr( $opts['github_token'] ); ?>" class="regular-text" />
							<p class="description"><?php esc_html_e( 'Yalnizca ozel repo kullaniyorsaniz gerekir. Genel repolarda bos birakin.', 'sudo2go-labs' ); ?></p>
						</td>
					</tr>
				</table>
				<?php submit_button(); ?>
			</form>

			<hr />
			<h2><?php esc_html_e( 'Tanilama', 'sudo2go-labs' ); ?></h2>
			<p class="description">
				<?php esc_html_e( 'Ayarlarin veritabaninda GERCEKTEN ne oldugunu ve eklentinin bunlari nasil cozdugunu gosterir. Bir ayar beklediginiz gibi davranmiyorsa buraya bakin.', 'sudo2go-labs' ); ?>
			</p>
			<?php
			$raw = get_option( self::OPTION, null );
			$rows = array(
				__( 'Secenek satiri veritabaninda', 'sudo2go-labs' ) => ( null === $raw ? __( 'YOK (varsayilanlar kullaniliyor)', 'sudo2go-labs' ) : __( 'var', 'sudo2go-labs' ) ),
				'default_lang ' . __( '(saklanan ham deger)', 'sudo2go-labs' ) => ( is_array( $raw ) && array_key_exists( 'default_lang', $raw )
					? "'" . $raw['default_lang'] . "'"
					: __( 'ayarlanmamis', 'sudo2go-labs' ) ),
				'default_lang ' . __( '(cozulen)', 'sudo2go-labs' ) => "'" . self::option( 'default_lang' ) . "'",
				__( 'Dil URL\'de yokken kullanilan', 'sudo2go-labs' ) => "'" . $this->lang() . "'",
				__( 'Sayfa yolu (cozulen)', 'sudo2go-labs' ) => '/' . self::page_path() . '/',
				__( 'Lab sayfasi var mi', 'sudo2go-labs' ) => ( get_page_by_path( self::page_path() ) ? __( 'var', 'sudo2go-labs' ) : __( 'YOK - kisa kodu tasiyan sayfayi olusturun', 'sudo2go-labs' ) ),
				__( 'Kalici nesne onbellegi', 'sudo2go-labs' ) => ( wp_using_ext_object_cache() ? __( 'AKTIF - ayar degisikligi gorunmuyorsa bunu da temizleyin', 'sudo2go-labs' ) : __( 'yok', 'sudo2go-labs' ) ),
			);
			?>
			<table class="widefat striped" style="max-width:48rem">
				<tbody>
				<?php foreach ( $rows as $label => $value ) : ?>
					<tr>
						<td style="width:18rem"><strong><?php echo esc_html( $label ); ?></strong></td>
						<td><code><?php echo esc_html( $value ); ?></code></td>
					</tr>
				<?php endforeach; ?>
				</tbody>
			</table>

			<hr />
			<h2><?php esc_html_e( 'Onbellek', 'sudo2go-labs' ); ?></h2>
			<p><?php esc_html_e( 'Repoya yeni bir duzeltme push ettiyseniz ve sitede hemen gormek istiyorsaniz:', 'sudo2go-labs' ); ?></p>
			<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
				<input type="hidden" name="action" value="s2g_flush" />
				<?php wp_nonce_field( 's2g_flush' ); ?>
				<?php submit_button( __( 'Onbellegi temizle', 'sudo2go-labs' ), 'secondary', 'submit', false ); ?>
			</form>
		</div>
		<?php
	}
}

Sudo2Go_Labs::instance();

register_activation_hook( __FILE__, 'flush_rewrite_rules' );
register_deactivation_hook( __FILE__, 'flush_rewrite_rules' );
