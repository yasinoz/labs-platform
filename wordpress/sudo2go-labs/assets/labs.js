/* sudo2go Labs - kod blogu kopyalama.
 *
 * Tek is: ogrenci komutu elle secmek zorunda kalmasin. Derste en cok zaman
 * kaybedilen yer, uzun komutun yanlis kopyalanmasi.
 */
( function () {
	'use strict';

	var L = window.S2G_LABS || { copy: 'Kopyala', copied: 'Kopyalandi' };

	function textOf( wrapper ) {
		var code = wrapper.querySelector( 'code' );
		return code ? code.innerText.replace( /\n+$/, '' ) : '';
	}

	function flash( button ) {
		button.textContent = L.copied;
		button.classList.add( 's2g-done' );
		window.setTimeout( function () {
			button.textContent = L.copy;
			button.classList.remove( 's2g-done' );
		}, 1600 );
	}

	function fallbackCopy( text ) {
		var area = document.createElement( 'textarea' );
		area.value = text;
		area.setAttribute( 'readonly', '' );
		area.style.position = 'fixed';
		area.style.opacity = '0';
		document.body.appendChild( area );
		area.select();
		var ok = false;
		try {
			ok = document.execCommand( 'copy' );
		} catch ( e ) {
			ok = false;
		}
		document.body.removeChild( area );
		return ok;
	}

	document.addEventListener( 'click', function ( event ) {
		var button = event.target.closest ? event.target.closest( '.s2g-copy' ) : null;
		if ( ! button ) {
			return;
		}
		event.preventDefault();
		var wrapper = button.closest( '.s2g-code' );
		if ( ! wrapper ) {
			return;
		}
		var text = textOf( wrapper );
		if ( ! text ) {
			return;
		}
		// navigator.clipboard yalnizca guvenli baglamda (HTTPS) var.
		if ( navigator.clipboard && window.isSecureContext ) {
			navigator.clipboard.writeText( text ).then(
				function () {
					flash( button );
				},
				function () {
					if ( fallbackCopy( text ) ) {
						flash( button );
					}
				}
			);
			return;
		}
		if ( fallbackCopy( text ) ) {
			flash( button );
		}
	} );
}() );
