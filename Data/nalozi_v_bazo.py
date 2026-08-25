"""Uvoz oglasov iz CSV (scraper) v bazo.

    python -m Data.nalozi_v_bazo
    python -m Data.nalozi_v_bazo --suho           # samo preveri, nič ne zapiše
    python -m Data.nalozi_v_bazo --omejitev 100

Oglas ima v bazi stolpec zunanji_id (ID oglasa na portalu) in omejitev
UNIQUE (id_vira, zunanji_id), zato je uvoz idempotenten - skripto lahko
poženeš večkrat in oglasi se ne podvojijo.
"""

import argparse
import csv
import os
import sys
from collections import Counter
from datetime import date
from typing import Optional

from Data.models import Nepremicnina, Oglas
from Data.repository import DB_NAME, DB_USER, JE_PISALNI_DOSTOP, Repository


# Nastavitve

KORENSKA_MAPA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVZETI_CSV = os.path.join(KORENSKA_MAPA, "Scrape Data", "oglasi_full.csv")

IME_VIRA = "nepremicnine.net"
URL_VIRA = "https://www.nepremicnine.net"

# Meje razumnosti. Vrstice zunaj teh mej so skoraj zagotovo napaka na portalu
# (npr. cena 2 € ali 26.000 m² stanovanje) – v bazo jih ne spustimo,
# ker bi popačile vso statistiko.
MIN_CENA, MAX_CENA = 50.0, 50_000.0
MIN_M2, MAX_M2 = 5.0, 2_000.0
MIN_LETO, MAX_LETO = 1200, date.today().year + 5

# CSV zna biti velik (polni opisi oglasov), zato dvignemo privzeto omejitev
# velikosti posameznega polja.
csv.field_size_limit(10_000_000)


# nepremicnine.net oglašuje tudi hrvaške nepremičnine. Imena regij so pri obojih
# zapisana v slovenščini ("Splitsko-dalmatinska", "Mesto Zagreb"), povezava do
# oglasa pa države ne označuje, zato je edini razpoznavni znak ime regije.
# Seznama zajameta vseh 27 imen iz oglasi_full.csv (1428 SI + 1244 HR + 18 brez
# regije). Če uvoz javi neznano regijo, jo dodaj v ustrezen seznam z malimi
# črkami.

SLOVENSKE_REGIJE = {
    # 12 statističnih regij + ločeni Ljubljana mesto/okolica, kot jih
    # uporablja portal
    "lj-mesto",         # 680 oglasov
    "podravska",        # 164
    "j. primorska",     # 129  (Južna Primorska – Obala, Koper, Izola ...)
    "lj-okolica",       # 120
    "savinjska",        # 100
    "gorenjska",        #  92
    "dolenjska",        #  41
    "s.primorska",      #  28  (Severna Primorska – Goriška)
    "koroška",          #  25
    "posavska",         #  18
    "pomurska",         #  15
    "notranjska",       #   8
    "zasavska",         #   8
    # različice zapisa, če se portal kdaj premisli
    "ljubljana mesto", "ljubljana okolica", "osrednjeslovenska",
    "obalno-kraška", "goriška", "jugovzhodna slovenija", "primorsko-notranjska",
}

HRVASKE_REGIJE = {
    # hrvaške županije, zapisane v slovenščini
    "mesto zagreb",             # 674 oglasov
    "primorsko-goranska",       # 317
    "splitsko-dalmatinska",     # 102
    "zagrebška",                #  52
    "istrska",                  #  45
    "osiješko-baranjska",       #  17
    "zadarska",                 #  12
    "varaždinska",              #   8
    "karlovška",                #   7
    "šibeniško-kninska",        #   4
    "liško-senjska",            #   3
    "međimurska",               #   1
    "dubrovniško-neretvanska",  #   1
    "brodsko-posavska",         #   1
    # preostale hrvaške županije, ki se v tem zajemu niso pojavile
    "krapinsko-zagorska", "sisaško-moslavaška", "koprivniško-križevška",
    "bjelovarsko-bilogorska", "virovitiško-podravska", "požeško-slavonska",
    "vukovarsko-srijemska", "bjelovarsko-križevačka",
}


def doloci_drzavo(regija: str, url_oglasa: str = "") -> tuple:
    """Vrne ('SI'|'HR', ali_je_bila_regija_prepoznana).

    Vrstni red preverjanja:
      1. natančno ujemanje s seznamom hrvaških regij;
      2. natančno ujemanje s seznamom slovenskih regij;
      3. delno ujemanje (npr. "Zagrebška" vsebuje "zagreb");
      4. če nič od tega – privzamemo 'SI' in to JAVIMO v poročilu.

    Hrvaško preverjamo prvo, ker so hrvaška imena daljša in bolj specifična
    (npr. "primorsko-goranska" proti slovenski "j. primorska").

    Parameter url_oglasa je ohranjen za primer, da portal kdaj začne
    državo označevati v povezavi; trenutno se ne uporablja.
    """
    r = (regija or "").strip().lower()
    if not r:
        return "SI", True          # brez regije: id_regije bo NULL, ni opozorila

    if r in HRVASKE_REGIJE:
        return "HR", True
    if r in SLOVENSKE_REGIJE:
        return "SI", True

    # Delno ujemanje kot varovalo pri drobnih spremembah zapisa.
    for hr in HRVASKE_REGIJE:
        if hr in r or r in hr:
            return "HR", False     # ujelo se je, a vseeno javimo
    for si in SLOVENSKE_REGIJE:
        if si in r or r in si:
            return "SI", False

    return "SI", False             # neprepoznano – javimo uporabniku


# Pomožne funkcije za čiščenje

def besedilo(vrednost: Optional[str]) -> Optional[str]:
    """Prazen niz ali same presledke pretvori v None (v bazi je to NULL)."""
    if vrednost is None:
        return None
    v = str(vrednost).strip()
    return v if v else None


def stevilo(vrednost: Optional[str]) -> Optional[float]:
    """Besedilo pretvori v število; ob neuspehu vrne None namesto napake.

    Pokrije tudi slovenski zapis '1.405,50' (pika = tisočice, vejica = decimalke).
    """
    if vrednost is None:
        return None
    v = str(vrednost).strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        pass
    # Poskusimo še slovenski zapis
    v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def celo_stevilo(vrednost: Optional[str]) -> Optional[int]:
    f = stevilo(vrednost)
    return int(f) if f is not None else None


# Glavni uvoz

def uvozi(pot_csv: str, suho: bool = False, omejitev: Optional[int] = None) -> int:
    if not os.path.exists(pot_csv):
        print(f" NAPAKA: datoteke ni: {pot_csv}")
        return 1

    print("=" * 74)
    print(" UVOZ OGLASOV V BAZO")
    print("=" * 74)
    print(f" Datoteka:  {pot_csv}")
    print(f" Baza:      {DB_NAME}  (uporabnik: {DB_USER})")
    if suho:
        print(" NAČIN:     SUHI TEK – v bazo se NE bo zapisalo nič")
    print("=" * 74)

    if not suho and not JE_PISALNI_DOSTOP:
        print("\n NAPAKA: povezan si kot 'javnost' (samo branje).")
        print(" Ustvari Data/auth.py s svojimi podatki. Za preizkus uporabi --suho.")
        return 1

    # 1) Preberemo CSV v pomnilnik (2700 vrstic je za pomnilnik zanemarljivo).
    with open(pot_csv, "r", encoding="utf-8", newline="") as f:
        vrstice = list(csv.DictReader(f))

    if omejitev:
        vrstice = vrstice[:omejitev]
    print(f"\n Prebranih vrstic: {len(vrstice)}")

    repo = Repository()

    # Števci za končno poročilo.
    stat = Counter()
    neznane_regije = Counter()
    primeri_napak = []

    try:
        # 2) Vir – ustvarimo (ali najdemo) enkrat za vse oglase.
        if suho:
            id_vira = -1
            ze_uvozeni = set()
        else:
            vir = repo.dobi_ali_dodaj_vir(IME_VIRA, URL_VIRA)
            id_vira = vir.id_vira
            # Vseh obstoječih zunanjih ID-jev naenkrat = 1 poizvedba namesto 2700.
            ze_uvozeni = repo.obstojeci_zunanji_idji(id_vira)
            print(f" Vir '{IME_VIRA}' ima v bazi že {len(ze_uvozeni)} oglasov.")

        # Predpomnilniki, da za isto regijo/lokacijo/vrsto ne hodimo v bazo večkrat.
        # Ključ -> id. To uvoz pospeši za približno red velikosti.
        predpomnilnik_vrst: dict = {}
        predpomnilnik_regij: dict = {}
        predpomnilnik_lokacij: dict = {}

        print("\n Uvažam ...")
        for i, v in enumerate(vrstice, start=1):
            if i % 500 == 0:
                print(f"   ... obdelanih {i}/{len(vrstice)}")

            zunanji_id = besedilo(v.get("id_oglasa"))
            naslov = besedilo(v.get("naslov"))
            url_oglasa = besedilo(v.get("url_oglasa"))

            # --- Preverjanja, zaradi katerih vrstico preskočimo ---

            if not zunanji_id:
                stat["brez_id"] += 1
                continue

            if zunanji_id in ze_uvozeni:
                stat["ze_v_bazi"] += 1
                continue

            if not naslov:
                stat["brez_naslova"] += 1
                continue

            cena = stevilo(v.get("cena"))
            if cena is None or not (MIN_CENA <= cena <= MAX_CENA):
                stat["slaba_cena"] += 1
                if len(primeri_napak) < 12:
                    primeri_napak.append(f"cena={v.get('cena')!r} id={zunanji_id} {naslov[:40]}")
                continue

            m2 = stevilo(v.get("m2"))
            if m2 is None or not (MIN_M2 <= m2 <= MAX_M2):
                stat["slaba_m2"] += 1
                if len(primeri_napak) < 12:
                    primeri_napak.append(f"m2={v.get('m2')!r} id={zunanji_id} {naslov[:40]}")
                continue

            # --- Vrednosti, ki jih po potrebi le "popravimo" ---

            leto = celo_stevilo(v.get("leto_gradnje"))
            if leto is not None and not (MIN_LETO <= leto <= MAX_LETO):
                leto = None                      # nesmiselno leto raje zavržemo
                stat["popravljeno_leto"] += 1

            sobe = stevilo(v.get("stevilo_sob"))
            if sobe is not None and sobe <= 0:
                sobe = None

            tip = besedilo(v.get("tip_nepremicnine")) or "Neznano"
            regija_ime = besedilo(v.get("regija"))
            drzava, prepoznana = doloci_drzavo(regija_ime or "", url_oglasa or "")
            if not prepoznana and regija_ime:
                neznane_regije[regija_ime] += 1

            # Poln opis je boljši; če ga ni, vzamemo kratkega s seznama.
            opis = besedilo(v.get("opis_poln")) or besedilo(v.get("opis_kratek"))

            if suho:
                stat["bi_vstavil"] += 1
                ze_uvozeni.add(zunanji_id)
                continue

            # --- Vpis v bazo ---
            try:
                # (a) vrsta nepremičnine
                if tip not in predpomnilnik_vrst:
                    predpomnilnik_vrst[tip] = repo.dobi_ali_dodaj_vrsto(tip).id_vrste
                id_vrste = predpomnilnik_vrst[tip]

                # (b) regija
                id_regije = None
                if regija_ime:
                    kljuc_r = (regija_ime, drzava)
                    if kljuc_r not in predpomnilnik_regij:
                        predpomnilnik_regij[kljuc_r] = repo.dobi_ali_dodaj_regijo(
                            regija_ime, drzava
                        ).id_regije
                    id_regije = predpomnilnik_regij[kljuc_r]

                # (c) lokacija
                ue = besedilo(v.get("upravna_enota"))
                obcina = besedilo(v.get("obcina"))
                naselje = besedilo(v.get("naselje"))
                kljuc_l = (id_regije, ue, obcina, naselje)
                if kljuc_l not in predpomnilnik_lokacij:
                    predpomnilnik_lokacij[kljuc_l] = repo.dobi_ali_dodaj_lokacijo(
                        id_regije=id_regije, upravna_enota=ue,
                        obcina=obcina, naselje=naselje,
                    ).id_lokacije
                id_lokacije = predpomnilnik_lokacij[kljuc_l]

                # (d) nepremičnina
                nep = repo.dodaj_nepremicnino(Nepremicnina(
                    id_vrste=id_vrste,
                    id_lokacije=id_lokacije,
                    opis=opis,
                    leto_gradnje=leto,
                    stevilo_sob=sobe,
                    stevilo_sob_opis=besedilo(v.get("stevilo_sob_opis")),
                    nadstropje=besedilo(v.get("nadstropje")),
                    m2=m2,
                ))

                # (e) oglas
                repo.dodaj_oglas(Oglas(
                    id_vira=id_vira,
                    id_nepremicnine=nep.id_nepremicnine,
                    zunanji_id=zunanji_id,
                    naslov=naslov,
                    url_oglasa=url_oglasa,
                    cena=cena,
                    valuta=besedilo(v.get("valuta")) or "EUR",
                ))

                ze_uvozeni.add(zunanji_id)
                stat["vstavljeno"] += 1
                # Oglase brez regije štejemo posebej – v bazi imajo
                # id_regije = NULL in v filtru po državi se ne pojavijo.
                stat["brez_regije" if not regija_ime else f"drzava_{drzava}"] += 1

            except Exception as e:
                # Ena pokvarjena vrstica ne sme ustaviti celotnega uvoza.
                # rollback() povrne povezavo v uporabno stanje.
                repo.conn.rollback()
                stat["napaka_pri_vpisu"] += 1
                if len(primeri_napak) < 12:
                    primeri_napak.append(f"id={zunanji_id}: {type(e).__name__}: {e}")

        # 3) Poročilo
        print("\n" + "=" * 74)
        print(" POROČILO O UVOZU")
        print("=" * 74)
        print(f"  Prebranih vrstic v CSV:          {len(vrstice)}")
        if suho:
            print(f"  Bi vstavil:                      {stat['bi_vstavil']}")
        else:
            print(f"  Uspešno vstavljenih oglasov:     {stat['vstavljeno']}")
            print(f"     od tega slovenskih (SI):      {stat['drzava_SI']}")
            print(f"     od tega hrvaških  (HR):       {stat['drzava_HR']}")
            print(f"     od tega brez regije:          {stat['brez_regije']}")
        print(f"  Preskočenih (že v bazi):         {stat['ze_v_bazi']}")
        print(f"  Zavrnjenih – neveljavna cena:    {stat['slaba_cena']}")
        print(f"  Zavrnjenih – neveljavni m²:      {stat['slaba_m2']}")
        print(f"  Zavrnjenih – brez naslova/ID:    {stat['brez_naslova'] + stat['brez_id']}")
        print(f"  Popravljeno – nesmiselno leto:   {stat['popravljeno_leto']}")
        print(f"  Napake pri vpisu:                {stat['napaka_pri_vpisu']}")

        if primeri_napak:
            print("\n  Primeri zavrnjenih vrstic:")
            for p in primeri_napak:
                print(f"    - {p}")

        if neznane_regije:
            print("\n  NEZNANE REGIJE (privzeto uvrščene v SI):")
            print("  Če katera od teh spada na Hrvaško, jo dodaj v HRVASKE_REGIJE")
            print("  na vrhu datoteke Data/nalozi_v_bazo.py in poženi uvoz znova.")
            for ime, n in neznane_regije.most_common():
                print(f"    - {ime!r}  ({n} oglasov)")

        if not suho:
            print("\n  Stanje baze po uvozu:")
            print(f"    oglasov:      {repo.prestej_oglase()}")
            print(f"    regij:        {len(repo.seznam_regij())}")
            print(f"    lokacij:      {len(repo.seznam_lokacij())}")
            print(f"    vrst:         {len(repo.seznam_vrst())}")
        print("=" * 74)
        return 0

    finally:
        repo.zapri()


def main() -> int:
    p = argparse.ArgumentParser(description="Uvoz oglasov iz CSV v bazo.")
    p.add_argument("--datoteka", default=PRIVZETI_CSV, help="pot do CSV datoteke")
    p.add_argument("--suho", action="store_true",
                   help="samo preveri podatke, v bazo ne zapiši nič")
    p.add_argument("--omejitev", type=int, default=None,
                   help="uvozi samo prvih N vrstic (za preizkus)")
    a = p.parse_args()
    return uvozi(a.datoteka, suho=a.suho, omejitev=a.omejitev)


if __name__ == "__main__":
    sys.exit(main())
