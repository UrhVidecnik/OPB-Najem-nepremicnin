"""
============================================================================
 OPB – Najem nepremičnin
 Datoteka: app.py

 PREDSTAVITVENI NIVO – spletna aplikacija (ogrodje Bottle).

 ZAGON:
     python app.py
     -> odpri http://localhost:8080

 KAKO DELUJE
   Vsaka funkcija spodaj je ena STRAN. Nad njo je dekorator, ki pove,
   na kateri naslov se odziva:
       @get('/oglasi')   -> uporabnik odpre stran (klik na povezavo)
       @post('/oglasi')  -> uporabnik odda obrazec (klik na gumb)

   Funkcija vrne template(...) = zgeneriran HTML, ki ga brskalnik prikaže.

 PRAVILO NIVOJEV
   app.py NIKOLI ne piše SQL in se NIKOLI ne pogovarja z bazo neposredno.
   Vse gre prek Service -> Repository -> PostgreSQL.
============================================================================
"""

import os
from functools import wraps

from Data.repository import DB_NAME, DB_USER, JE_PISALNI_DOSTOP
from Presentation.bottleext import (
    get,
    post,
    redirect,
    request,
    response,
    run,
    static_file,
    template,
    template_uporabnik,
    url,
)
from Services.auth_service import AuthService
from Services.service import PRIVZETO_NA_STRAN, Service

# ── Nastavitve ──────────────────────────────────────────────────────────────

SERVER_PORT = int(os.environ.get("BOTTLE_PORT", 8080))
RELOADER = os.environ.get("BOTTLE_RELOADER", "True").lower() in ("1", "true", "yes")

# Servisa ustvarimo enkrat ob zagonu (vsak ima svojo povezavo z bazo).
service = Service()
auth = AuthService()


# ── Dekoratorja za omejevanje dostopa ───────────────────────────────────────

def zahtevaj_prijavo(f):
    """Stran je dostopna samo prijavljenim uporabnikom.

    Dekorator je funkcija, ki ovije drugo funkcijo. Tu preverimo piškotek
    'uporabnik'; če ga ni, namesto strani prikažemo obrazec za prijavo.
    @wraps ohrani ime in dokumentacijo izvirne funkcije (Bottle to potrebuje
    za razlikovanje poti).
    """
    @wraps(f)
    def ovita(*args, **kwargs):
        if not request.get_cookie("uporabnik"):
            return template(
                "prijava.html", uporabnik=None, vloga=None,
                napaka="Za to stran je potrebna prijava.",
                naslednja=request.fullpath,
            )
        return f(*args, **kwargs)
    return ovita


def zahtevaj_admina(f):
    """Stran je dostopna samo uporabnikom z vlogo 'admin'."""
    @wraps(f)
    def ovita(*args, **kwargs):
        if not request.get_cookie("uporabnik"):
            return template("prijava.html", uporabnik=None, vloga=None,
                            napaka="Za to stran je potrebna prijava.",
                            naslednja=request.fullpath)
        if request.get_cookie("vloga") != "admin":
            return template_uporabnik(
                "napaka.html", naslov="Ni dovoljenja",
                sporocilo="Za to dejanje potrebuješ skrbniške (admin) pravice.",
            )
        return f(*args, **kwargs)
    return ovita


# ── Statične datoteke (CSS) ─────────────────────────────────────────────────

@get("/static/<filepath:path>")
def staticne_datoteke(filepath):
    """Postreže CSS in druge statične datoteke iz Presentation/static."""
    return static_file(filepath, root="Presentation/static")


# ── Domača stran ────────────────────────────────────────────────────────────

@get("/")
def domaca_stran():
    """Pregled: nekaj številk in najdražji/najcenejši oglasi."""
    statistika = service.statistika()
    izbor = service.najdrazji_najcenejsi(koliko=5)
    po_regijah = service.statistika_po_regijah(min_oglasov=10)[:8]

    return template_uporabnik(
        "domaca_stran.html",
        statistika=statistika,
        najdrazji=izbor["najdrazji"],
        najcenejsi=izbor["najcenejsi"],
        po_regijah=po_regijah,
        stevilo_regij=len(service.regije()),
        stevilo_lokacij=len(service.lokacije()),
    )


# ── Seznam oglasov z iskanjem, filtri in paginacijo ─────────────────────────

@get("/oglasi")
def seznam_oglasov():
    """Glavna stran aplikacije: filtriranje in brskanje po oglasih."""
    # 1) Iz parametrov URL-ja sestavimo filtre (Service poskrbi za pretvorbe).
    filtri = service.sestavi_filtre(request.query)

    # 2) Katero stran hoče uporabnik.
    stran = Service.v_int(request.query.get("stran")) or 1
    na_stran = Service.v_int(request.query.get("na_stran")) or PRIVZETO_NA_STRAN

    # 3) Podatke poberemo iz baze.
    rezultat = service.stran_oglasov(filtri, stran=stran, na_stran=na_stran)

    # 4) Šifranti za spustne sezname v obrazcu.
    return template_uporabnik(
        "oglasi.html",
        rezultat=rezultat,
        filtri=filtri,
        vrste=service.vrste(),
        regije=service.regije(),
        viri=service.viri(),
        na_stran=na_stran,
    )


# ── Podrobnosti enega oglasa ────────────────────────────────────────────────

@get("/oglas/<id_oglasa:int>")
def podrobnosti_oglasa(id_oglasa):
    """Stran s podrobnostmi. `<id_oglasa:int>` pomeni, da Bottle
    del poti samodejno pretvori v celo število."""
    oglas = service.dobi_oglas(id_oglasa)
    if oglas is None:
        response.status = 404
        return template_uporabnik(
            "napaka.html", naslov="Oglas ne obstaja",
            sporocilo=f"Oglasa s številko {id_oglasa} ni v bazi.",
        )

    # Podobni oglasi: ista regija, cena ±30 %.
    from Data.models import OglasFiltriDTO
    podobni = []
    if oglas.lokacija.id_regije:
        podobni_filtri = OglasFiltriDTO(
            id_regije=oglas.lokacija.id_regije,
            cena_min=float(oglas.oglas.cena) * 0.7,
            cena_max=float(oglas.oglas.cena) * 1.3,
            urejanje="cena_asc",
        )
        podobni = [
            o for o in service.stran_oglasov(podobni_filtri, 1, 7).oglasi
            if o.oglas.id_oglasa != id_oglasa
        ][:6]

    return template_uporabnik("oglas.html", o=oglas, podobni=podobni)


# ── Statistika ──────────────────────────────────────────────────────────────

@get("/statistika")
def stran_statistika():
    """Analiza podatkov: agregati, razpredelnica po regijah, histogram cen."""
    filtri = service.sestavi_filtre(request.query)

    statistika = service.statistika(filtri)
    po_regijah = service.statistika_po_regijah(filtri, min_oglasov=5)
    po_vrstah = service.statistika_po_vrstah(filtri)
    histogram = service.porazdelitev_cen(filtri, sirina_razreda=250)

    # Za stolpčni diagram v HTML potrebujemo najvišji stolpec,
    # da lahko višine izrazimo v odstotkih.
    najvecji = max((h["stevilo"] for h in histogram), default=1)

    return template_uporabnik(
        "statistika.html",
        statistika=statistika,
        po_regijah=po_regijah,
        po_vrstah=po_vrstah,
        histogram=histogram,
        najvecji=najvecji,
        filtri=filtri,
        vrste=service.vrste(),
        regije=service.regije(),
    )


# ── Dodajanje oglasa ────────────────────────────────────────────────────────

@get("/dodaj")
@zahtevaj_prijavo
def obrazec_dodaj():
    """Prikaže prazen obrazec za nov oglas."""
    return template_uporabnik(
        "dodaj_oglas.html",
        vrste=service.vrste(), regije=service.regije(), viri=service.viri(),
        napaka=None, podatki={},
    )


@post("/dodaj")
@zahtevaj_prijavo
def shrani_nov_oglas():
    """Sprejme oddani obrazec in shrani nov oglas."""
    f = request.forms

    # POZOR: redirect() v Bottle deluje tako, da VRŽE izjemo HTTPResponse.
    # Če bi ga poklicali znotraj try/except Exception, bi našo preusmeritev
    # ujel except in namesto preusmeritve prikazal "napako" brez sporočila.
    # Zato v try samo shranimo, preusmerimo pa šele za njim.
    nov_id = None
    try:
        nov = service.dodaj_oglas(
            naslov=f.getunicode("naslov"),
            cena=Service.v_float(f.getunicode("cena")),
            m2=Service.v_float(f.getunicode("m2")),
            id_vrste=Service.v_int(f.getunicode("id_vrste")),
            id_vira=Service.v_int(f.getunicode("id_vira")),
            id_regije=Service.v_int(f.getunicode("id_regije")),
            obcina=f.getunicode("obcina"),
            naselje=f.getunicode("naselje"),
            url_oglasa=f.getunicode("url_oglasa"),
            opis=f.getunicode("opis"),
            leto_gradnje=Service.v_int(f.getunicode("leto_gradnje")),
            stevilo_sob=Service.v_float(f.getunicode("stevilo_sob")),
            stevilo_sob_opis=f.getunicode("stevilo_sob_opis"),
            nadstropje=f.getunicode("nadstropje"),
        )
        nov_id = nov.oglas.id_oglasa

    except ValueError as e:
        # Napako pokažemo nad obrazcem in vrnemo ŽE VPISANE podatke,
        # da uporabniku ni treba vsega tipkati znova.
        return template_uporabnik(
            "dodaj_oglas.html",
            vrste=service.vrste(), regije=service.regije(), viri=service.viri(),
            napaka=str(e), podatki=dict(f.decode()),
        )
    except Exception as e:
        service.repository.conn.rollback()
        return template_uporabnik(
            "dodaj_oglas.html",
            vrste=service.vrste(), regije=service.regije(), viri=service.viri(),
            napaka=f"Napaka pri shranjevanju: {e}", podatki=dict(f.decode()),
        )

    # Vzorec POST -> Redirect -> GET: brez preusmeritve bi osvežitev strani
    # (F5) oglas vnesla še enkrat.
    redirect(url(f"/oglas/{nov_id}"))


# ── Urejanje oglasa ─────────────────────────────────────────────────────────

@get("/uredi/<id_oglasa:int>")
@zahtevaj_prijavo
def obrazec_uredi(id_oglasa):
    oglas = service.dobi_oglas(id_oglasa)
    if oglas is None:
        response.status = 404
        return template_uporabnik("napaka.html", naslov="Oglas ne obstaja",
                                  sporocilo=f"Oglasa {id_oglasa} ni v bazi.")
    return template_uporabnik("uredi_oglas.html", o=oglas, napaka=None)


@post("/uredi/<id_oglasa:int>")
@zahtevaj_prijavo
def shrani_urejen_oglas(id_oglasa):
    f = request.forms
    try:
        service.posodobi_oglas(
            id_oglasa=id_oglasa,
            naslov=f.getunicode("naslov"),
            cena=Service.v_float(f.getunicode("cena")),
            m2=Service.v_float(f.getunicode("m2")),
            leto_gradnje=Service.v_int(f.getunicode("leto_gradnje")),
            stevilo_sob=Service.v_float(f.getunicode("stevilo_sob")),
            nadstropje=f.getunicode("nadstropje"),
            opis=f.getunicode("opis"),
            url_oglasa=f.getunicode("url_oglasa"),
        )
    except ValueError as e:
        return template_uporabnik("uredi_oglas.html",
                                  o=service.dobi_oglas(id_oglasa), napaka=str(e))

    # redirect() šele zunaj try (glej razlago pri /dodaj).
    redirect(url(f"/oglas/{id_oglasa}"))


# ── Brisanje oglasa (samo admin) ────────────────────────────────────────────

@post("/izbrisi/<id_oglasa:int>")
@zahtevaj_admina
def izbrisi_oglas(id_oglasa):
    """Brisanje je @post in ne @get namenoma: povezave (GET) brskalniki
    in roboti predhodno nalagajo, kar bi lahko pobrisalo oglase."""
    service.izbrisi_oglas(id_oglasa)
    redirect(url("/oglasi"))


# ── Prijava, registracija, odjava ───────────────────────────────────────────

@get("/prijava")
def obrazec_prijava():
    return template("prijava.html", uporabnik=None, vloga=None,
                    napaka=None, naslednja=request.query.get("naslednja"))


@post("/prijava")
def izvedi_prijavo():
    uporabnisko_ime = request.forms.getunicode("uporabnisko_ime")
    geslo = request.forms.getunicode("geslo")
    naslednja = request.forms.getunicode("naslednja")

    uporabnik = auth.prijavi(uporabnisko_ime, geslo)
    if uporabnik is None:
        return template("prijava.html", uporabnik=None, vloga=None,
                        napaka="Napačno uporabniško ime ali geslo.",
                        naslednja=naslednja)

    # Piškotka za ime in vlogo. max_age=8h; path='/', da veljata povsod.
    response.set_cookie("uporabnik", uporabnik.uporabnisko_ime,
                        path="/", max_age=8 * 3600)
    response.set_cookie("vloga", uporabnik.vloga, path="/", max_age=8 * 3600)

    redirect(url(naslednja if naslednja and naslednja.startswith("/") else "/"))


@get("/registracija")
def obrazec_registracija():
    return template("registracija.html", uporabnik=None, vloga=None,
                    napaka=None, vpisano_ime="")


@post("/registracija")
def izvedi_registracijo():
    ime = request.forms.getunicode("uporabnisko_ime")
    geslo = request.forms.getunicode("geslo")
    geslo2 = request.forms.getunicode("geslo_ponovno")

    try:
        auth.registriraj(ime, geslo, geslo2)
    except ValueError as e:
        return template("registracija.html", uporabnik=None, vloga=None,
                        napaka=str(e), vpisano_ime=ime or "")
    except Exception as e:
        auth.repository.conn.rollback()
        return template("registracija.html", uporabnik=None, vloga=None,
                        napaka=f"Registracija ni uspela: {e}", vpisano_ime=ime or "")

    # Po uspešni registraciji uporabnika kar prijavimo.
    response.set_cookie("uporabnik", ime.strip(), path="/", max_age=8 * 3600)
    response.set_cookie("vloga", "uporabnik", path="/", max_age=8 * 3600)
    redirect(url("/"))


@get("/odjava")
def odjava():
    response.delete_cookie("uporabnik", path="/")
    response.delete_cookie("vloga", path="/")
    redirect(url("/"))


# ── Zagon ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 66)
    print(" OPB – Najem nepremičnin")
    print(f" Baza:      {DB_NAME} (uporabnik: {DB_USER})")
    print(f" Dostop:    {'branje in pisanje' if JE_PISALNI_DOSTOP else 'samo branje'}")
    print(f" Naslov:    http://localhost:{SERVER_PORT}")
    print("=" * 66)
    run(host="0.0.0.0", port=SERVER_PORT, reloader=RELOADER, debug=True)
