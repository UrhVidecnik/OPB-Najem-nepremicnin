"""
============================================================================
 OPB – Najem nepremičnin
 Datoteka: Presentation/bottleext.py

 Majhna nadgradnja ogrodja Bottle. Tri stvari, ki jih potrebujemo:

 1) TEMPLATE_PATH
    Bottle predloge privzeto išče v mapi ./views. Naše so v
    ./Presentation/views, zato to pot dodamo na začetek seznama.

 2) PODPISANI PIŠKOTKI
    Piškotek je navaden zapis v brskalniku uporabnika. Če bi vanj brez
    zaščite zapisali "vloga=admin", bi si lahko vsak z orodji za razvijalce
    sam nastavil "vloga=admin" in dobil pravice za brisanje oglasov.
    Zato piškotke PODPIŠEMO: Bottle jim doda zgoščeno vrednost, izračunano
    s skrivnim ključem, in ob branju podpis preveri. Spremenjen piškotek
    tako ne prestane preverjanja in ga preberemo kot "ni prijavljen".

 3) url()
    Bottle ima svojo funkcijo bottle.url(), ki pa pričakuje IME poti
    (npr. url('index')), ne poti same. Če ji podaš url('/'), vrže
    RouteBuildError. Ker je v predlogah veliko bolj naravno pisati
    url('/oglasi'), naredimo svojo funkcijo, ki dela s POTMI.

    Poleg tega poskrbi za predpono BOTTLE_ROOT. To potrebujemo na
    Binderju, kjer aplikacija ne teče na korenu strežnika, ampak
    nekje pod /user/xy/proxy/8080/ – brez predpone bi bile vse
    povezave na strani polomljene.

 V app.py potem uvozimo vse iz te datoteke namesto neposredno iz bottle.
============================================================================
"""

import os

import bottle
from bottle import (  # noqa: F401  (uvožene, da so na voljo v app.py)
    HTTPError,
    TEMPLATE_PATH,
    abort,
    get,
    post,
    redirect,
    request,
    response,
    run,
    static_file,
)

# Predloge iščemo najprej v naši mapi.
TEMPLATE_PATH.insert(0, "./Presentation/views")

# Predpona poti (prazna pri lokalnem zagonu).
KOREN = os.environ.get("BOTTLE_ROOT", "")

# ── Podpisani piškotki ──────────────────────────────────────────────────────
#
# Skrivni ključ za podpisovanje. V pravem produkcijskem okolju bi bil vedno
# le v okoljski spremenljivki; za šolski projekt je privzeta vrednost tu,
# da aplikacija deluje takoj po kloniranju.
#
# Ko ključ zamenjaš, vsi obstoječi piškotki nehajo veljati in se morajo
# uporabniki znova prijaviti – kar je pravzaprav zaželeno.
SKRIVNI_KLJUC = os.environ.get("SECRET_KEY", "opb-najem-nepremicnin-2026")

# Koliko časa velja prijava (8 ur).
TRAJANJE_PRIJAVE = 8 * 3600


def nastavi_piskotek(ime: str, vrednost: str) -> None:
    """Zapiše PODPISAN piškotek (uporabniško ime, vloga)."""
    response.set_cookie(ime, vrednost, secret=SKRIVNI_KLJUC,
                        path="/", max_age=TRAJANJE_PRIJAVE)


def preberi_piskotek(ime: str):
    """Prebere podpisan piškotek; vrne None, če ga ni ali če je spremenjen.

    bottle vrne False, kadar podpis ne ustreza – to obravnavamo enako
    kot odsotnost piškotka.
    """
    vrednost = request.get_cookie(ime, secret=SKRIVNI_KLJUC)
    return vrednost or None


def pobrisi_piskotek(ime: str) -> None:
    """Odjava: piškotek izbrišemo. Pomembno je, da so parametri (path in
    secret) enaki kot pri nastavljanju, sicer brskalnik piškotka ne poveže
    s prvotnim in ga ne odstrani."""
    response.delete_cookie(ime, secret=SKRIVNI_KLJUC, path="/")


def url(pot: str = "/", **parametri) -> str:
    """Sestavi povezavo iz POTI in neobveznih parametrov poizvedbe.

    Primeri:
        url('/oglasi')                      -> '/oglasi'
        url('/oglasi', stran=2, q='kranj')  -> '/oglasi?stran=2&q=kranj'
        url('/oglas/17')                    -> '/oglas/17'

    Parametri z vrednostjo None ali "" se izpustijo – zato lahko v
    predlogi mirno napišemo url('/oglasi', q=filtri.iskanje), tudi
    kadar filtra ni.
    """
    if not pot.startswith("/"):
        pot = "/" + pot

    polna = KOREN.rstrip("/") + pot if KOREN else pot

    # Prazne parametre odstranimo, ostale pravilno zakodiramo
    # (npr. presledek -> %20, šumnik -> %C4%8D).
    cisti = {}
    for k, v in parametri.items():
        if v is None or v == "":
            continue
        # 1200.0 zapišemo kot 1200 – lepše je v naslovni vrstici.
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        cisti[k] = v

    if cisti:
        from urllib.parse import urlencode
        polna += "?" + urlencode(cisti)

    return polna


def template(*args, **kwargs):
    """bottle.template z vedno pripeto funkcijo url().

    Tako nam v vsaki poti v app.py ni treba pisati url=url.
    """
    kwargs.setdefault("url", url)
    return bottle.template(*args, **kwargs)


def template_uporabnik(*args, **kwargs):
    """Kot template(), a doda še podatke o prijavljenem uporabniku.

    Vsaka predloga tako lahko uporabi spremenljivke:
        uporabnik       – uporabniško ime ali None
        vloga           – 'admin' / 'uporabnik' / None
        pisalni_dostop  – ali povezava z bazo sploh sme UPDATE in DELETE

    `pisalni_dostop` potrebujemo zato, ker se aplikacija v privzetem načinu
    poveže kot 'javnost', ki sme oglase samo brati in dodajati. Gumba
    'Uredi' v takem primeru ne kaže prikazati, saj bi baza spremembo
    tako ali tako zavrnila.
    """
    from Data.repository import JE_PISALNI_DOSTOP

    kwargs.setdefault("uporabnik", preberi_piskotek("uporabnik"))
    kwargs.setdefault("vloga", preberi_piskotek("vloga"))
    kwargs.setdefault("pisalni_dostop", JE_PISALNI_DOSTOP)
    return template(*args, **kwargs)
