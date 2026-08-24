"""
============================================================================
 OPB – Najem nepremičnin
 Datoteka: Presentation/bottleext.py

 Majhna nadgradnja ogrodja Bottle. Dve stvari, ki ju potrebujemo:

 1) TEMPLATE_PATH
    Bottle predloge privzeto išče v mapi ./views. Naše so v
    ./Presentation/views, zato to pot dodamo na začetek seznama.

 2) url()
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

    Vsaka predloga tako lahko uporabi spremenljivki `uporabnik` in `vloga`
    (npr. za prikaz gumba 'Odjava' ali skritje gumba 'Dodaj oglas').
    """
    kwargs.setdefault("uporabnik", request.get_cookie("uporabnik"))
    kwargs.setdefault("vloga", request.get_cookie("vloga"))
    return template(*args, **kwargs)
