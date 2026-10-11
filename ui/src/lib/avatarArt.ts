/**
 * Desenhos PROPRIOS dos avatares (nenhum personagem de terceiros). Fundo preto: no holograma o escuro some e o claro vira luz.
 * Contraste alto de proposito: bordas e olhos bem claros, miolos escuros.
 */

export const ROBOT_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><defs>
<radialGradient id="shell" cx="38%" cy="28%" r="80%"><stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#b7bec6"/><stop offset="1" stop-color="#4b525a"/></radialGradient>
<linearGradient id="metal" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6c737b"/><stop offset=".5" stop-color="#e9edf0"/><stop offset="1" stop-color="#5a6169"/></linearGradient>
<linearGradient id="visor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a2026"/><stop offset="1" stop-color="#000"/></linearGradient>
<radialGradient id="eye" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#fff"/><stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter></defs>
<rect width="512" height="512" fill="#000"/>
<!-- antena -->
<path d="M256 98 V58" stroke="url(#metal)" stroke-width="10" stroke-linecap="round"/>
<circle cx="256" cy="46" r="17" fill="url(#shell)"/><circle cx="256" cy="46" r="7" fill="#000" opacity=".55"/><circle cx="256" cy="46" r="26" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="3"/>
<!-- orelhas -->
<g><rect x="84" y="176" width="42" height="104" rx="18" fill="url(#metal)"/><rect x="96" y="196" width="18" height="64" rx="9" fill="#000" opacity=".6"/><circle cx="105" cy="228" r="5" fill="#fff"/>
<rect x="386" y="176" width="42" height="104" rx="18" fill="url(#metal)"/><rect x="398" y="196" width="18" height="64" rx="9" fill="#000" opacity=".6"/><circle cx="407" cy="228" r="5" fill="#fff"/></g>
<!-- cabeca -->
<path d="M256 92 C176 92 124 112 120 188 L120 262 C120 322 160 358 256 358 C352 358 392 322 392 262 L392 188 C388 112 336 92 256 92Z" fill="url(#shell)"/>
<path d="M150 150 C190 118 322 118 362 150" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" opacity=".85"/>
<path d="M256 98 V150" stroke="#000" stroke-width="4" opacity=".4"/>
<path d="M132 300 C150 338 196 350 256 350 C316 350 362 338 380 300" fill="none" stroke="#000" stroke-width="3" opacity=".35"/>
<!-- visor -->
<rect x="148" y="168" width="216" height="112" rx="46" fill="url(#visor)"/>
<rect x="148" y="168" width="216" height="112" rx="46" fill="none" stroke="#fff" stroke-width="4" opacity=".75"/>
<rect x="160" y="180" width="192" height="88" rx="38" fill="none" stroke="#fff" stroke-width="1.5" opacity=".25"/>
<!-- olhos -->
<g filter="url(#glow)" opacity=".9"><ellipse cx="206" cy="224" rx="26" ry="22" fill="#fff"/><ellipse cx="306" cy="224" rx="26" ry="22" fill="#fff"/></g>
<ellipse cx="206" cy="224" rx="25" ry="21" fill="url(#eye)"/><ellipse cx="306" cy="224" rx="25" ry="21" fill="url(#eye)"/>
<ellipse cx="206" cy="224" rx="13" ry="12" fill="#fff"/><ellipse cx="306" cy="224" rx="13" ry="12" fill="#fff"/>
<circle cx="199" cy="217" r="4" fill="#000" opacity=".35"/><circle cx="299" cy="217" r="4" fill="#000" opacity=".35"/>
<!-- boca de luzes -->
<rect x="196" y="300" width="120" height="16" rx="8" fill="#000" opacity=".8"/>
<g fill="#fff"><circle cx="214" cy="308" r="4"/><circle cx="235" cy="308" r="4"/><circle cx="256" cy="308" r="5"/><circle cx="277" cy="308" r="4"/><circle cx="298" cy="308" r="4"/></g>
<!-- pescoco e ombros -->
<rect x="214" y="352" width="84" height="40" rx="10" fill="url(#metal)"/>
<g stroke="#000" stroke-width="3" opacity=".5"><path d="M218 364 H294"/><path d="M218 376 H294"/></g>
<path d="M70 486 C78 424 130 392 196 388 H316 C382 392 434 424 442 486 Z" fill="url(#shell)"/>
<path d="M120 402 C150 392 180 388 196 388" stroke="#fff" stroke-width="5" fill="none" opacity=".8" stroke-linecap="round"/>
<circle cx="256" cy="436" r="24" fill="#000" opacity=".7"/><circle cx="256" cy="436" r="24" fill="none" stroke="#fff" stroke-width="3"/><circle cx="256" cy="436" r="10" fill="#fff"/>
<path d="M150 462 H206 M306 462 H362" stroke="#000" stroke-width="4" opacity=".4" stroke-linecap="round"/>
</svg>`

export const SHIELD_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><defs>
<linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".5" stop-color="#aab1b9"/><stop offset="1" stop-color="#545b63"/></linearGradient>
<linearGradient id="face" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a4148"/><stop offset="1" stop-color="#0b0e11"/></linearGradient>
<radialGradient id="core" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#fff"/><stop offset=".6" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter></defs>
<rect width="512" height="512" fill="#000"/>
<!-- aro externo -->
<path d="M256 30 L430 92 C432 262 386 384 256 486 C126 384 80 262 82 92 Z" fill="url(#rim)"/>
<!-- face -->
<path d="M256 56 L408 110 C410 256 370 366 256 458 C142 366 102 256 104 110 Z" fill="url(#face)"/>
<path d="M256 56 L408 110 C410 256 370 366 256 458 C142 366 102 256 104 110 Z" fill="none" stroke="#fff" stroke-width="3" opacity=".55"/>
<!-- faixa diagonal de luz no aro -->
<path d="M98 120 L256 44 L414 120" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".9"/>
<!-- circuitos -->
<g stroke="#fff" stroke-width="3" fill="none" opacity=".7" stroke-linecap="round" stroke-linejoin="round">
<path d="M256 120 V168"/><path d="M256 302 V402"/>
<path d="M170 235 H132 L120 220"/><path d="M342 235 H380 L392 220"/>
<path d="M190 168 L152 140"/><path d="M322 168 L360 140"/>
<path d="M190 300 L160 340 H140"/><path d="M322 300 L352 340 H372"/>
</g>
<g fill="#fff"><circle cx="256" cy="120" r="6"/><circle cx="120" cy="220" r="5"/><circle cx="392" cy="220" r="5"/><circle cx="152" cy="140" r="5"/><circle cx="360" cy="140" r="5"/><circle cx="140" cy="340" r="5"/><circle cx="372" cy="340" r="5"/><circle cx="256" cy="402" r="6"/></g>
<!-- hexagono central -->
<g filter="url(#blur)" opacity=".85"><circle cx="256" cy="235" r="46" fill="#fff"/></g>
<path d="M256 160 L322 198 V272 L256 310 L190 272 V198 Z" fill="#06080a" stroke="#fff" stroke-width="5"/>
<path d="M256 178 L306 207 V263 L256 292 L206 263 V207 Z" fill="none" stroke="#fff" stroke-width="2" opacity=".5"/>
<!-- letra J estilizada (marca propria do Jefrey) -->
<path d="M270 198 V250 C270 266 262 272 250 272 C240 272 233 266 231 256" fill="none" stroke="#fff" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="256" cy="235" r="62" fill="url(#core)" opacity=".18"/>
</svg>`
