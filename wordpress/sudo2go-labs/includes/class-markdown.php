<?php
/**
 * Lab dokumanlari icin odakli Markdown render edici.
 *
 * Neden hazir kutuphane degil: lab dokumanlari Markdown'in dar ve TUTARLI bir
 * altkumesini kullaniyor (basliklar, kod blogu, liste, tablo, alinti, link,
 * ham HTML <details> bloklari). Bu altkume icin 200 satir PHP, eklentiye
 * vendor dizini ve guncelleme yuku getirmeden yeterli.
 *
 * Ham HTML bilincli olarak GECIRILIR: lablar ipucu bloklarinda
 * <details><summary> kullaniyor ve bu yapi korunmali. Kaynak kendi
 * GitHub repomuz oldugu icin guvenilir; yine de script/iframe/on* etiketleri
 * temizlenir.
 *
 * @package Sudo2Go_Labs
 */

defined( 'ABSPATH' ) || exit;

class Sudo2Go_Markdown {

	/** @var array<int,array{level:int,text:string,id:string}> */
	private $headings = array();

	/** @var string Goreli baglantilarin cozulecegi taban (repo icindeki dizin). */
	private $link_base = '';

	/** @var callable|null Goreli baglanti yeniden yazici. */
	private $link_filter = null;

	public function set_link_filter( $base, callable $filter ) {
		$this->link_base   = $base;
		$this->link_filter = $filter;
	}

	public function get_headings() {
		return $this->headings;
	}

	/**
	 * Frontmatter blogunu ayirir.
	 *
	 * @return array{0:array,1:string} [frontmatter, govde]
	 */
	public static function split_frontmatter( $text ) {
		$text = preg_replace( "/\r\n?/", "\n", (string) $text );
		if ( 0 !== strpos( $text, "---\n" ) ) {
			return array( array(), $text );
		}
		$end = strpos( $text, "\n---", 3 );
		if ( false === $end ) {
			return array( array(), $text );
		}
		$raw  = substr( $text, 4, $end - 3 );
		$body = ltrim( substr( $text, $end + 4 ), "\n" );
		$meta = array();
		foreach ( explode( "\n", $raw ) as $line ) {
			if ( ! preg_match( '/^([a-z_]+):\s*(.*)$/i', trim( $line ), $m ) ) {
				continue;
			}
			$key = strtolower( $m[1] );
			$val = trim( $m[2] );
			if ( preg_match( '/^\[(.*)\]$/', $val, $lm ) ) {
				$val = array_values( array_filter( array_map( 'trim', explode( ',', $lm[1] ) ) ) );
			} else {
				$val = trim( $val, '"\'' );
			}
			$meta[ $key ] = $val;
		}
		return array( $meta, $body );
	}

	/** @var int Ic ice render derinligi - basliklari yalnizca en ustte sifirlar. */
	private $depth = 0;

	public function render( $markdown ) {
		// HATA DUZELTMESI: render() ozyinelemeli cagriliyor (alinti bloklari ve
		// ic ice listeler icin). Basliklari her cagrida sifirlarsak, dokumanin
		// sonundaki bir alinti blogu o ana kadar toplanmis TUM basliklari
		// siliyor ve icerik tablosu hic cikmiyordu. Yalnizca en ust seviyedeki
		// cagri sifirliyor.
		if ( 0 === $this->depth ) {
			$this->headings = array();
		}
		$this->depth++;
		try {
			return $this->render_blocks( $markdown );
		} finally {
			$this->depth--;
		}
	}

	private function render_blocks( $markdown ) {
		$text           = preg_replace( "/\r\n?/", "\n", (string) $markdown );
		$lines          = explode( "\n", $text );
		$out            = array();
		$i              = 0;
		$count          = count( $lines );

		while ( $i < $count ) {
			$line = $lines[ $i ];

			// --- cit ile kapatilmis kod blogu -------------------------------
			if ( preg_match( '/^\s*(`{3,}|~{3,})\s*([a-zA-Z0-9_+-]*)\s*$/', $line, $m ) ) {
				$fence = $m[1];
				$lang  = $m[2];
				$buf   = array();
				$i++;
				while ( $i < $count && ! preg_match( '/^\s*' . preg_quote( substr( $fence, 0, 1 ), '/' ) . '{' . strlen( $fence ) . ',}\s*$/', $lines[ $i ] ) ) {
					$buf[] = $lines[ $i ];
					$i++;
				}
				$i++; // kapanis citi
				$out[] = $this->code_block( implode( "\n", $buf ), $lang );
				continue;
			}

			// --- ham HTML blogu (details, summary, img, br ...) -------------
			if ( preg_match( '/^\s*<\/?([a-zA-Z][a-zA-Z0-9]*)/', $line, $m ) ) {
				$buf = array();
				while ( $i < $count && '' !== trim( $lines[ $i ] ) ) {
					$buf[] = $lines[ $i ];
					$i++;
				}
				$out[] = $this->sanitize_html( implode( "\n", $buf ) );
				continue;
			}

			// --- baslik -----------------------------------------------------
			if ( preg_match( '/^(#{1,6})\s+(.*)$/', $line, $m ) ) {
				$level = strlen( $m[1] );
				$plain = trim( wp_strip_all_tags( $this->inline( $m[2] ) ) );
				$id    = $this->slug( $plain );
				if ( $level <= 3 ) {
					$this->headings[] = array(
						'level' => $level,
						'text'  => $plain,
						'id'    => $id,
					);
				}
				$out[] = sprintf(
					'<h%1$d id="%2$s" class="s2g-h"><a class="s2g-anchor" href="#%2$s" aria-hidden="true">#</a>%3$s</h%1$d>',
					$level,
					esc_attr( $id ),
					$this->inline( $m[2] )
				);
				$i++;
				continue;
			}

			// --- yatay cizgi ------------------------------------------------
			if ( preg_match( '/^\s*(\*\s*\*\s*\*|-\s*-\s*-|_\s*_\s*_)[\s*\-_]*$/', $line ) ) {
				$out[] = '<hr class="s2g-hr" />';
				$i++;
				continue;
			}

			// --- tablo ------------------------------------------------------
			if ( false !== strpos( $line, '|' ) && isset( $lines[ $i + 1 ] )
				&& preg_match( '/^\s*\|?[\s:|-]+\|[\s:|-]*$/', $lines[ $i + 1 ] ) ) {
				$rows = array();
				while ( $i < $count && false !== strpos( $lines[ $i ], '|' ) && '' !== trim( $lines[ $i ] ) ) {
					$rows[] = $lines[ $i ];
					$i++;
				}
				$out[] = $this->table( $rows );
				continue;
			}

			// --- alinti -----------------------------------------------------
			if ( preg_match( '/^\s*>\s?(.*)$/', $line ) ) {
				$buf = array();
				while ( $i < $count && preg_match( '/^\s*>\s?(.*)$/', $lines[ $i ], $m ) ) {
					$buf[] = $m[1];
					$i++;
				}
				$out[] = '<blockquote class="s2g-note">' . $this->render( implode( "\n", $buf ) ) . '</blockquote>';
				continue;
			}

			// --- liste ------------------------------------------------------
			if ( preg_match( '/^(\s*)([-*+]|\d+[.)])\s+/', $line, $m ) ) {
				$block = array();
				while ( $i < $count && ( '' !== trim( $lines[ $i ] ) )
					&& ( preg_match( '/^(\s*)([-*+]|\d+[.)])\s+/', $lines[ $i ] )
						|| preg_match( '/^\s{2,}\S/', $lines[ $i ] ) ) ) {
					$block[] = $lines[ $i ];
					$i++;
				}
				$ordered = (bool) preg_match( '/^\s*\d+[.)]/', $block[0] );
				$out[]   = $this->list_block( $block, $ordered );
				continue;
			}

			// --- bos satir --------------------------------------------------
			if ( '' === trim( $line ) ) {
				$i++;
				continue;
			}

			// --- paragraf ---------------------------------------------------
			$buf = array();
			while ( $i < $count && '' !== trim( $lines[ $i ] )
				&& ! preg_match( '/^(#{1,6}\s|\s*>|\s*(`{3,}|~{3,})|\s*([-*+]|\d+[.)])\s)/', $lines[ $i ] )
				&& ! preg_match( '/^\s*<\/?[a-zA-Z]/', $lines[ $i ] ) ) {
				$buf[] = $lines[ $i ];
				$i++;
			}
			if ( $buf ) {
				$out[] = '<p>' . $this->inline( implode( "\n", $buf ) ) . '</p>';
			} else {
				$i++;
			}
		}

		return implode( "\n", $out );
	}

	private function code_block( $code, $lang ) {
		$label = $lang ? $lang : 'shell';
		return sprintf(
			'<div class="s2g-code" data-lang="%s"><button type="button" class="s2g-copy" aria-label="%s">%s</button><pre><code class="language-%s">%s</code></pre></div>',
			esc_attr( $label ),
			esc_attr__( 'Kopyala', 'sudo2go-labs' ),
			esc_html__( 'Kopyala', 'sudo2go-labs' ),
			esc_attr( $label ),
			esc_html( $code )
		);
	}

	private function table( $rows ) {
		$cells = function ( $row ) {
			$row = trim( $row );
			$row = preg_replace( '/^\|/', '', $row );
			$row = preg_replace( '/\|$/', '', $row );
			return array_map( 'trim', explode( '|', $row ) );
		};
		$head = $cells( array_shift( $rows ) );
		array_shift( $rows ); // ayirici satir
		$html = '<div class="s2g-tablewrap"><table class="s2g-table"><thead><tr>';
		foreach ( $head as $h ) {
			$html .= '<th>' . $this->inline( $h ) . '</th>';
		}
		$html .= '</tr></thead><tbody>';
		foreach ( $rows as $row ) {
			$html .= '<tr>';
			foreach ( $cells( $row ) as $c ) {
				$html .= '<td>' . $this->inline( $c ) . '</td>';
			}
			$html .= '</tr>';
		}
		return $html . '</tbody></table></div>';
	}

	private function list_block( $lines, $ordered ) {
		$tag   = $ordered ? 'ol' : 'ul';
		$html  = '<' . $tag . ' class="s2g-list">';
		$items = array();
		$cur   = null;
		foreach ( $lines as $line ) {
			if ( preg_match( '/^(\s*)([-*+]|\d+[.)])\s+(.*)$/', $line, $m ) ) {
				if ( null !== $cur ) {
					$items[] = $cur;
				}
				$cur = array(
					'indent' => strlen( $m[1] ),
					'text'   => $m[3],
					'sub'    => array(),
				);
			} elseif ( null !== $cur ) {
				$cur['sub'][] = ltrim( $line );
			}
		}
		if ( null !== $cur ) {
			$items[] = $cur;
		}
		$base = $items ? min( wp_list_pluck( $items, 'indent' ) ) : 0;
		$open = false;
		foreach ( $items as $it ) {
			$body = $this->inline( $it['text'] );
			if ( $it['sub'] ) {
				$body .= $this->render( implode( "\n", $it['sub'] ) );
			}
			if ( $it['indent'] > $base ) {
				if ( ! $open ) {
					$html .= '<' . $tag . ' class="s2g-list">';
					$open  = true;
				}
				$html .= '<li>' . $body . '</li>';
				continue;
			}
			if ( $open ) {
				$html .= '</' . $tag . '>';
				$open  = false;
			}
			$html .= '<li>' . $body . '</li>';
		}
		if ( $open ) {
			$html .= '</' . $tag . '>';
		}
		return $html . '</' . $tag . '>';
	}

	/** Satir ici bicimlendirme. Sira onemli: once kod, sonra geri kalani. */
	private function inline( $text ) {
		$placeholders = array();
		// `kod` - icine baska kural uygulanmamali
		$text = preg_replace_callback(
			'/`([^`]+)`/',
			function ( $m ) use ( &$placeholders ) {
				$key                  = "\x00" . count( $placeholders ) . "\x00";
				$placeholders[ $key ] = '<code class="s2g-ic">' . esc_html( $m[1] ) . '</code>';
				return $key;
			},
			$text
		);

		// Ham satir ici HTML etiketlerini de koru (<br/>, <summary>...)
		$text = preg_replace_callback(
			'/<\/?[a-zA-Z][^<>]*>/',
			function ( $m ) use ( &$placeholders ) {
				$key                  = "\x00" . count( $placeholders ) . "\x00";
				$placeholders[ $key ] = $this->sanitize_html( $m[0] );
				return $key;
			},
			$text
		);

		$text = esc_html( $text );

		// resim ![alt](src)
		$text = preg_replace_callback(
			'/!\[([^\]]*)\]\(([^)\s]+)\)/',
			function ( $m ) {
				return sprintf(
					'<img class="s2g-img" src="%s" alt="%s" loading="lazy" />',
					esc_url( $this->resolve_link( $m[2], true ) ),
					esc_attr( $m[1] )
				);
			},
			$text
		);

		// baglanti [metin](hedef)
		$text = preg_replace_callback(
			'/\[([^\]]+)\]\(([^)\s]+)\)/',
			function ( $m ) {
				$href     = $this->resolve_link( $m[2], false );
				$external = (bool) preg_match( '#^https?://#i', $href );
				return sprintf(
					'<a href="%s"%s>%s</a>',
					esc_url( $href ),
					$external ? ' target="_blank" rel="noopener noreferrer"' : '',
					$m[1]
				);
			},
			$text
		);

		$text = preg_replace( '/\*\*([^*]+)\*\*/', '<strong>$1</strong>', $text );
		$text = preg_replace( '/(?<![\w*])\*([^*\n]+)\*(?![\w*])/', '<em>$1</em>', $text );
		$text = preg_replace( '/(?<![\w_])_([^_\n]+)_(?![\w_])/', '<em>$1</em>', $text );

		return strtr( $text, $placeholders );
	}

	private function resolve_link( $target, $is_image ) {
		if ( preg_match( '#^(https?:|mailto:|#)#i', $target ) || 0 === strpos( $target, '#' ) ) {
			return $target;
		}
		if ( is_callable( $this->link_filter ) ) {
			return call_user_func( $this->link_filter, $target, $this->link_base, $is_image );
		}
		return $target;
	}

	/**
	 * Ham HTML'i temizler: yapisal etiketler gecer, calistirilabilir olanlar gitmez.
	 */
	private function sanitize_html( $html ) {
		$allowed = array(
			'details' => array( 'open' => true, 'class' => true ),
			'summary' => array( 'class' => true ),
			'br'      => array(),
			'hr'      => array(),
			'b'       => array(),
			'strong'  => array(),
			'i'       => array(),
			'em'      => array(),
			'code'    => array( 'class' => true ),
			'pre'     => array( 'class' => true ),
			'p'       => array( 'class' => true ),
			'div'     => array( 'class' => true ),
			'span'    => array( 'class' => true ),
			'ul'      => array( 'class' => true ),
			'ol'      => array( 'class' => true ),
			'li'      => array( 'class' => true ),
			'a'       => array( 'href' => true, 'title' => true, 'target' => true, 'rel' => true ),
			'img'     => array( 'src' => true, 'alt' => true, 'width' => true, 'height' => true, 'loading' => true, 'class' => true ),
			'table'   => array( 'class' => true ),
			'thead'   => array(),
			'tbody'   => array(),
			'tr'      => array(),
			'th'      => array(),
			'td'      => array(),
			'blockquote' => array( 'class' => true ),
			'h1' => array( 'id' => true ), 'h2' => array( 'id' => true ),
			'h3' => array( 'id' => true ), 'h4' => array( 'id' => true ),
			'h5' => array( 'id' => true ), 'h6' => array( 'id' => true ),
		);
		return wp_kses( $html, $allowed );
	}

	private function slug( $text ) {
		$slug = sanitize_title( $text );
		return $slug ? $slug : 'bolum';
	}
}
