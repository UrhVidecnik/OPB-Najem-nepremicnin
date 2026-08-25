"""Testi vseh treh nivojev. Zagon: python testi.py

Napisani so brez pytest, da delujejo takoj po pip install -r requirements.txt.
Testi, ki pišejo v bazo, se preskočijo, če si povezan kot 'javnost'.
"""

import sys
import traceback

from Data.models import (
    Lokacija,
    Nepremicnina,
    Oglas,
    OglasFiltriDTO,
    Regija,
    StranDTO,
)
from Data.repository import JE_PISALNI_DOSTOP, Repository
from Services.auth_service import AuthService
from Services.service import Service

# Števci rezultatov
opravljeni = 0
padli = 0
preskoceni = 0


def test(ime):
    """Dekorator, ki test požene in izpiše rezultat."""
    def dekorator(f):
        global opravljeni, padli
        try:
            f()
            opravljeni += 1
            print(f"  OK      {ime}")
        except AssertionError as e:
            padli += 1
            print(f"  PADEL   {ime}")
            print(f"          -> {e}")
        except Exception:
            padli += 1
            print(f"  NAPAKA  {ime}")
            print("          " + traceback.format_exc().replace("\n", "\n          "))
        return f
    return dekorator


def preskoci(ime, razlog):
    global preskoceni
    preskoceni += 1
    print(f"  PRESKOK {ime}  ({razlog})")


print("=" * 74)
print(" TESTI – OPB Najem nepremičnin")
print("=" * 74)

repo = Repository()
service = Service(repo)
auth = AuthService(repo)


# 1. MODELI (brez baze)
print("\n[1] Podatkovni modeli")


@test("Nepremicnina zavrne m2 <= 0")
def _():
    try:
        Nepremicnina(id_vrste=1, id_lokacije=1, m2=0)
        raise AssertionError("m2=0 bi moral vreči ValueError")
    except ValueError:
        pass


@test("Nepremicnina zavrne nesmiselno leto gradnje")
def _():
    try:
        Nepremicnina(id_vrste=1, id_lokacije=1, m2=50, leto_gradnje=999)
        raise AssertionError("leto 999 bi moralo vreči ValueError")
    except ValueError:
        pass


@test("Nepremicnina sprejme staro, a možno leto (1451)")
def _():
    n = Nepremicnina(id_vrste=1, id_lokacije=1, m2=50, leto_gradnje=1451)
    assert n.leto_gradnje == 1451


@test("Oglas zavrne negativno ceno in prazen naslov")
def _():
    for kwargs in ({"naslov": "X", "cena": -1}, {"naslov": "   ", "cena": 10}):
        try:
            Oglas(**kwargs)
            raise AssertionError(f"{kwargs} bi moral vreči ValueError")
        except ValueError:
            pass


@test("Regija zavrne neznano državo")
def _():
    try:
        Regija(ime_regije="X", drzava="DE")
        raise AssertionError("drzava='DE' bi morala vreči ValueError")
    except ValueError:
        pass


@test("Lokacija.prikaz izpusti prazne dele")
def _():
    l = Lokacija(naselje="Brdo", obcina=None, ime_regije="Ljubljana mesto")
    assert l.prikaz == "Brdo, Ljubljana mesto", l.prikaz
    assert Lokacija().prikaz == "Neznana lokacija"


@test("StranDTO pravilno izračuna število strani")
def _():
    assert StranDTO(skupaj=0,  na_stran=25).stevilo_strani == 1
    assert StranDTO(skupaj=25, na_stran=25).stevilo_strani == 1
    assert StranDTO(skupaj=26, na_stran=25).stevilo_strani == 2
    assert StranDTO(skupaj=51, na_stran=25).stevilo_strani == 3
    s = StranDTO(skupaj=51, na_stran=25, stran=2)
    assert s.ima_prejsnjo and s.ima_naslednjo


# 2. SERVICE – pretvorbe in validacija (brez baze)
print("\n[2] Aplikacijski nivo – pretvorbe in validacija")


@test("v_int / v_float / v_besedilo prenesejo smeti brez sesutja")
def _():
    assert Service.v_int("42") == 42
    assert Service.v_int("") is None
    assert Service.v_int("abc") is None
    assert Service.v_int(None) is None
    assert Service.v_float("1200,50") == 1200.5
    assert Service.v_float("1200.50") == 1200.5
    assert Service.v_float("x") is None
    assert Service.v_besedilo("  test  ") == "test"
    assert Service.v_besedilo("   ") is None


@test("preveri_filtre zamenja min in max, če sta obrnjena")
def _():
    f = OglasFiltriDTO(cena_min=2000, cena_max=500)
    service.preveri_filtre(f)
    assert f.cena_min == 500 and f.cena_max == 2000, (f.cena_min, f.cena_max)


@test("preveri_filtre odstrani negativne vrednosti")
def _():
    f = OglasFiltriDTO(cena_min=-100, m2_min=-5)
    service.preveri_filtre(f)
    assert f.cena_min is None and f.m2_min is None


@test("sestavi_filtre iz slovarja prezre neveljavne vrednosti")
def _():
    f = service.sestavi_filtre({
        "q": "  kranj ", "cena_min": "500", "cena_max": "abc",
        "drzava": "DE", "urejanje": "; DROP TABLE oglas; --",
    })
    assert f.iskanje == "kranj"
    assert f.cena_min == 500
    assert f.cena_max is None
    assert f.drzava is None                  # 'DE' ni dovoljena
    assert f.urejanje == "cena_asc"          # poskus SQL injection zavrnjen


@test("OglasFiltriDTO.je_prazen pravilno zazna prazne filtre")
def _():
    assert OglasFiltriDTO().je_prazen()
    assert not OglasFiltriDTO(cena_min=100).je_prazen()


# 3. REPOSITORY – branje iz baze
print("\n[3] Podatkovni nivo – branje")


@test("Povezava z bazo deluje in tabele obstajajo")
def _():
    with repo._cur() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        tabele = {v["table_name"] for v in cur.fetchall()}
    for t in ("vir", "vrsta_nepremicnine", "regija", "lokacija",
              "nepremicnina", "oglas", "uporabnik"):
        assert t in tabele, f"manjka tabela {t}"


@test("Pogled oglas_pregled obstaja in vrne stolpec cena_na_m2")
def _():
    with repo._cur() as cur:
        cur.execute("SELECT * FROM oglas_pregled LIMIT 1")
        vrstica = cur.fetchone()
    if vrstica is not None:
        assert "cena_na_m2" in vrstica


@test("prestej_oglase vrne nenegativno število")
def _():
    assert repo.prestej_oglase() >= 0


@test("Filtriranje res zoži rezultat")
def _():
    vseh = repo.prestej_oglase()
    if vseh == 0:
        return
    poceni = repo.prestej_oglase(OglasFiltriDTO(cena_max=400))
    assert 0 <= poceni <= vseh, (poceni, vseh)


@test("Filter po državi vrne samo oglase te države")
def _():
    oglasi = repo.seznam_oglasov(OglasFiltriDTO(drzava="HR"), limit=20)
    for o in oglasi:
        assert o.lokacija.drzava == "HR", o.lokacija.drzava


@test("Cenovni filter res spoštuje meje")
def _():
    oglasi = repo.seznam_oglasov(OglasFiltriDTO(cena_min=700, cena_max=900), limit=30)
    for o in oglasi:
        assert 700 <= float(o.oglas.cena) <= 900, o.oglas.cena


@test("Razvrščanje po ceni naraščajoče res narašča")
def _():
    oglasi = repo.seznam_oglasov(OglasFiltriDTO(urejanje="cena_asc"), limit=40)
    cene = [float(o.oglas.cena) for o in oglasi]
    assert cene == sorted(cene), "cene niso urejene naraščajoče"


@test("Paginacija ne podvaja in ne izpušča oglasov")
def _():
    if repo.prestej_oglase() < 30:
        return
    s1 = repo.stran_oglasov(None, stran=1, na_stran=10)
    s2 = repo.stran_oglasov(None, stran=2, na_stran=10)
    idji1 = {o.oglas.id_oglasa for o in s1.oglasi}
    idji2 = {o.oglas.id_oglasa for o in s2.oglasi}
    assert len(idji1) == 10 and len(idji2) == 10
    assert not (idji1 & idji2), "isti oglas se pojavi na obeh straneh"


@test("Previsoka številka strani se popravi na zadnjo")
def _():
    s = repo.stran_oglasov(None, stran=99999, na_stran=25)
    assert s.stran == s.stevilo_strani


@test("Iskanje po ključni besedi vrne samo ustrezne zadetke")
def _():
    oglasi = repo.seznam_oglasov(OglasFiltriDTO(iskanje="Ljubljana"), limit=10)
    for o in oglasi:
        vsebina = " ".join(str(x or "") for x in (
            o.oglas.naslov, o.nepremicnina.opis,
            o.lokacija.naselje, o.lokacija.obcina)).lower()
        assert "ljubljana" in vsebina


@test("Statistika je skladna sama s sabo")
def _():
    s = repo.statistika()
    if s.stevilo_oglasov == 0:
        return
    assert s.minimalna_cena <= s.mediana_cena <= s.maksimalna_cena
    assert s.minimalna_cena <= s.povprecna_cena <= s.maksimalna_cena
    assert s.povprecna_m2 > 0


@test("Statistika s filtrom se ujema s štetjem")
def _():
    f = OglasFiltriDTO(cena_max=800)
    assert repo.statistika(f).stevilo_oglasov == repo.prestej_oglase(f)


@test("Statistika po regijah upošteva HAVING >= min_oglasov")
def _():
    for r in repo.statistika_po_regijah(min_oglasov=5):
        assert r.stevilo_oglasov >= 5


@test("Histogram cen vrne naraščajoče razrede")
def _():
    h = repo.porazdelitev_cen(sirina_razreda=250)
    meje = [x["spodnja_meja"] for x in h]
    assert meje == sorted(meje)


@test("Šifranti niso prazni")
def _():
    if repo.prestej_oglase() == 0:
        return
    assert len(repo.seznam_vrst()) > 0
    assert len(repo.seznam_virov()) > 0
    assert len(repo.seznam_lokacij()) > 0


@test("Uvoz je idempotenten – ni podvojenih zunanjih ID-jev")
def _():
    with repo._cur() as cur:
        cur.execute("""
            SELECT COUNT(*) AS n FROM (
                SELECT id_vira, zunanji_id FROM oglas
                WHERE zunanji_id IS NOT NULL
                GROUP BY id_vira, zunanji_id HAVING COUNT(*) > 1
            ) AS podvojeni
        """)
        assert cur.fetchone()["n"] == 0, "v bazi so podvojeni oglasi"


# 4. PISANJE V BAZO (samo z osebnim dostopom)
print("\n[4] Podatkovni nivo – pisanje")

if not JE_PISALNI_DOSTOP:
    preskoci("vsi testi pisanja", "povezan kot 'javnost' (samo branje)")
else:
    testni_id = None

    @test("dodaj_oglas ustvari oglas z izračunano ceno na m2")
    def _():
        global testni_id
        vrsta = repo.dobi_ali_dodaj_vrsto("TEST-VRSTA")
        vir = repo.dobi_ali_dodaj_vir("TEST-VIR", "https://test.local")
        regija = repo.dobi_ali_dodaj_regijo("TEST-REGIJA", "SI")

        dto = service.dodaj_oglas(
            naslov="TEST oglas – šumniki čšž",
            cena=1000.0, m2=50.0,
            id_vrste=vrsta.id_vrste, id_vira=vir.id_vira,
            id_regije=regija.id_regije, obcina="TEST-OBČINA", naselje="TEST-NASELJE",
            leto_gradnje=2000, stevilo_sob=2.0, nadstropje="3",
            opis="Testni opis.",
        )
        testni_id = dto.oglas.id_oglasa
        assert dto.oglas.id_oglasa is not None
        assert float(dto.cena_na_m2) == 20.0, dto.cena_na_m2
        assert dto.lokacija.naselje == "TEST-NASELJE"

    @test("Service zavrne neveljavne vnose")
    def _():
        vrsta = repo.dobi_ali_dodaj_vrsto("TEST-VRSTA")
        vir = repo.dobi_ali_dodaj_vir("TEST-VIR")
        for kwargs in (
            {"naslov": "", "cena": 100, "m2": 50},
            {"naslov": "X", "cena": -1, "m2": 50},
            {"naslov": "X", "cena": 100, "m2": 0},
            {"naslov": "X", "cena": 100, "m2": 50, "leto_gradnje": 999},
            {"naslov": "X", "cena": 100, "m2": 50, "stevilo_sob": -2},
        ):
            try:
                service.dodaj_oglas(id_vrste=vrsta.id_vrste, id_vira=vir.id_vira, **kwargs)
                raise AssertionError(f"{kwargs} bi moral biti zavrnjen")
            except ValueError:
                pass

    @test("posodobi_oglas res spremeni podatke")
    def _():
        assert testni_id is not None
        dto = service.posodobi_oglas(
            testni_id, naslov="TEST popravljen", cena=1200.0, m2=60.0,
            leto_gradnje=2010, stevilo_sob=3.0, nadstropje="4", opis="Nov opis.",
        )
        assert dto.oglas.naslov == "TEST popravljen"
        assert float(dto.oglas.cena) == 1200.0
        assert float(dto.nepremicnina.m2) == 60.0
        assert float(dto.cena_na_m2) == 20.0

    @test("dobi_ali_dodaj_* je idempotenten (ne podvaja šifrantov)")
    def _():
        a = repo.dobi_ali_dodaj_vrsto("TEST-VRSTA")
        b = repo.dobi_ali_dodaj_vrsto("TEST-VRSTA")
        assert a.id_vrste == b.id_vrste

        r1 = repo.dobi_ali_dodaj_regijo("TEST-REGIJA", "SI")
        r2 = repo.dobi_ali_dodaj_regijo("TEST-REGIJA", "SI")
        assert r1.id_regije == r2.id_regije

        # Ista lokacija z NULL vrednostmi se prav tako ne sme podvojiti.
        l1 = repo.dobi_ali_dodaj_lokacijo(id_regije=r1.id_regije, obcina="TEST-X")
        l2 = repo.dobi_ali_dodaj_lokacijo(id_regije=r1.id_regije, obcina="TEST-X")
        assert l1.id_lokacije == l2.id_lokacije

    @test("Baza zavrne podvojen (id_vira, zunanji_id)")
    def _():
        vir = repo.dobi_ali_dodaj_vir("TEST-VIR")
        vrsta = repo.dobi_ali_dodaj_vrsto("TEST-VRSTA")
        lok = repo.dobi_ali_dodaj_lokacijo(obcina="TEST-DUP")
        n = repo.dodaj_nepremicnino(Nepremicnina(
            id_vrste=vrsta.id_vrste, id_lokacije=lok.id_lokacije, m2=40))
        repo.dodaj_oglas(Oglas(id_vira=vir.id_vira, id_nepremicnine=n.id_nepremicnine,
                               zunanji_id="TEST-DUP-1", naslov="A", cena=500))
        try:
            repo.dodaj_oglas(Oglas(id_vira=vir.id_vira, id_nepremicnine=n.id_nepremicnine,
                                   zunanji_id="TEST-DUP-1", naslov="B", cena=600))
            raise AssertionError("podvojen zunanji_id bi moral biti zavrnjen")
        except AssertionError:
            raise
        except Exception:
            repo.conn.rollback()   # pričakovana napaka UNIQUE

    @test("Registracija in prijava delujeta, geslo je zgoščeno")
    def _():
        ime = "test_uporabnik_opb"
        if auth.obstaja_uporabnik(ime):
            with repo._cur() as cur:
                cur.execute("DELETE FROM uporabnik WHERE uporabnisko_ime = %s", (ime,))
            repo.conn.commit()

        u = auth.registriraj(ime, "geslo123", "geslo123")
        assert u.geslo_hash != "geslo123", "geslo NI zgoščeno!"
        assert u.geslo_hash.startswith("$2b$"), u.geslo_hash[:10]

        assert auth.prijavi(ime, "geslo123") is not None
        assert auth.prijavi(ime, "napacno") is None
        assert auth.prijavi("ne_obstaja", "geslo123") is None

        for napacni in (("ab", "geslo123", "geslo123"), (ime + "2", "123", "123"),
                        (ime + "3", "geslo123", "drugo"), (ime, "geslo123", "geslo123")):
            try:
                auth.registriraj(*napacni)
                raise AssertionError(f"{napacni} bi moral biti zavrnjen")
            except ValueError:
                pass

    @test("Čiščenje testnih podatkov")
    def _():
        with repo._cur() as cur:
            cur.execute("""
                DELETE FROM oglas
                WHERE id_nepremicnine IN (
                    SELECT n.id_nepremicnine FROM nepremicnina n
                        JOIN lokacija l ON l.id_lokacije = n.id_lokacije
                    WHERE l.obcina LIKE 'TEST-%'
                )
                   OR zunanji_id LIKE 'TEST-%'
            """)
            cur.execute("""
                DELETE FROM nepremicnina
                WHERE id_lokacije IN (SELECT id_lokacije FROM lokacija WHERE obcina LIKE 'TEST-%')
            """)
            cur.execute("DELETE FROM lokacija WHERE obcina LIKE 'TEST-%'")
            cur.execute("DELETE FROM regija WHERE ime_regije LIKE 'TEST-%'")
            cur.execute("DELETE FROM vrsta_nepremicnine WHERE ime_vrste LIKE 'TEST-%'")
            cur.execute("DELETE FROM vir WHERE ime_vira LIKE 'TEST-%'")
            cur.execute("DELETE FROM uporabnik WHERE uporabnisko_ime = 'test_uporabnik_opb'")
        repo.conn.commit()


# Povzetek
repo.zapri()

print("\n" + "=" * 74)
print(f" REZULTAT: {opravljeni} uspešnih, {padli} padlih, {preskoceni} preskočenih")
print("=" * 74)
sys.exit(1 if padli else 0)
