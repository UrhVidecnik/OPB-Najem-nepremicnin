"""Dodeljevanje vloge 'admin' iz ukazne vrstice.

    python nastavi_admina.py --seznam            # uporabniki in njihove vloge
    python nastavi_admina.py urh                 # obstoječega naredi za admina
    python nastavi_admina.py jure --geslo GESLO  # ustvari uporabnika in ga naredi za admina
    python nastavi_admina.py jure --odvzemi      # odvzame skrbniške pravice

Vloge namenoma ni mogoče spremeniti prek spletnega vmesnika - stran
"postani admin" bi lahko odprl vsakdo.
"""

import argparse
import getpass
import sys

from Data.repository import DB_NAME, DB_USER
from Services.auth_service import AuthService


def izpisi_seznam(auth: AuthService) -> None:
    """Izpiše vse uporabnike z njihovo vlogo in časom zadnje prijave."""
    uporabniki = auth.seznam_uporabnikov()

    if not uporabniki:
        print(" V bazi ni nobenega uporabnika.")
        print(" Najprej se registriraj v aplikaciji ali uporabi --geslo.")
        return

    print(f" {'UPORABNIŠKO IME':<24} {'VLOGA':<12} ZADNJA PRIJAVA")
    print(" " + "-" * 62)
    for u in uporabniki:
        zadnja = u.zadnja_prijava.strftime("%d. %m. %Y %H:%M") if u.zadnja_prijava else "–"
        oznaka = "admin  ★" if u.je_admin else "uporabnik"
        print(f" {u.uporabnisko_ime:<24} {oznaka:<12} {zadnja}")
    print()
    print(f" Skupaj: {len(uporabniki)} "
          f"(od tega {sum(1 for u in uporabniki if u.je_admin)} skrbnikov)")


def main() -> int:
    razclenjevalnik = argparse.ArgumentParser(
        description="Nastavi ali odvzame skrbniško (admin) vlogo uporabniku.",
    )
    razclenjevalnik.add_argument(
        "uporabnisko_ime", nargs="?",
        help="uporabnik, ki mu spreminjamo vlogo",
    )
    razclenjevalnik.add_argument(
        "--seznam", action="store_true",
        help="izpiši vse uporabnike in njihove vloge",
    )
    razclenjevalnik.add_argument(
        "--odvzemi", action="store_true",
        help="namesto dodelitve admina vlogo vrni na 'uporabnik'",
    )
    razclenjevalnik.add_argument(
        "--geslo", metavar="GESLO",
        help="če uporabnika še ni, ga ustvari s tem geslom "
             "(brez vrednosti geslo vpišeš skrito)",
    )
    argumenti = razclenjevalnik.parse_args()

    print("=" * 66)
    print(" UPORABNIKI IN VLOGE – OPB Najem nepremičnin")
    print(f" Baza: {DB_NAME} (povezan kot: {DB_USER})")
    print("=" * 66)

    auth = AuthService()
    try:
        # samo izpis
        if argumenti.seznam or not argumenti.uporabnisko_ime:
            izpisi_seznam(auth)
            if not argumenti.seznam:
                print()
                print(" Uporaba: python nastavi_admina.py <uporabnisko_ime>")
            return 0

        ime = argumenti.uporabnisko_ime.strip()
        nova_vloga = "uporabnik" if argumenti.odvzemi else "admin"

        # uporabnika še ni: ga ustvarimo (samo če imamo geslo)
        if not auth.obstaja_uporabnik(ime):
            if argumenti.odvzemi:
                print(f"\n NAPAKA: uporabnika '{ime}' ni v bazi.")
                return 1

            geslo = argumenti.geslo
            if geslo is None:
                print(f"\n Uporabnika '{ime}' v bazi še ni.")
                print(" Vpiši geslo zanj (Enter brez vpisa prekine):")
                geslo = getpass.getpass(" Geslo: ")
                if not geslo:
                    print(" Prekinjeno – nič ni bilo spremenjeno.")
                    return 0

            auth.registriraj(ime, geslo, vloga="admin")
            print(f"\n Uporabnik '{ime}' je USTVARJEN in ima vlogo 'admin'.")
            print(" Prijavi se lahko na /prijava z geslom, ki si ga pravkar vpisal.")
            return 0

        # uporabnik obstaja: samo spremenimo vlogo
        uporabnik = auth.nastavi_vlogo(ime, nova_vloga)
        if nova_vloga == "admin":
            print(f"\n Uporabnik '{uporabnik.uporabnisko_ime}' je zdaj SKRBNIK (admin).")
            print(" Sme urejati in brisati oglase.")
        else:
            print(f"\n Uporabniku '{uporabnik.uporabnisko_ime}' so bile skrbniške "
                  "pravice ODVZETE.")
            print(" Sme še vedno brskati in dodajati oglase.")

        print("\n Če je bil ta uporabnik med spremembo prijavljen, naj se")
        print(" odjavi in znova prijavi, da se mu osveži prikaz.")
        return 0

    except ValueError as e:
        print(f"\n NAPAKA: {e}")
        return 1
    except Exception as e:
        auth.repository.conn.rollback()
        print(f"\n NAPAKA pri dostopu do baze: {e}")
        return 1
    finally:
        auth.repository.zapri()


if __name__ == "__main__":
    sys.exit(main())
