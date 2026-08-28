"""Ustvari shemo baze in podeli pravice: python init_db.py

Potrebuje Data/auth.py, ker uporabnik 'javnost' tabel ne sme ustvarjati.
Pozor: najprej pobriše obstoječe tabele, zato vpraša za potrditev.
"""

import os
import sys

from Data.repository import DB_HOST, DB_NAME, DB_USER, JE_PISALNI_DOSTOP, Repository

# Poti sestavimo glede na mesto te datoteke, da skripta deluje ne glede
# na to, iz katere mape jo poženeš.
KORENSKA_MAPA = os.path.dirname(os.path.abspath(__file__))
SHEMA_SQL = os.path.join(KORENSKA_MAPA, "Data", "create_database.sql")
PRAVICE_SQL = os.path.join(KORENSKA_MAPA, "Data", "pravice.sql")


def main() -> int:
    print("=" * 70)
    print(" USTVARJANJE BAZE – OPB Najem nepremičnin")
    print("=" * 70)
    print(f" Baza:      {DB_NAME}")
    print(f" Strežnik:  {DB_HOST}")
    print(f" Uporabnik: {DB_USER}")
    print("=" * 70)

    if not JE_PISALNI_DOSTOP:
        print()
        print(" NAPAKA: povezan si kot 'javnost', ki ima samo bralni dostop.")
        print(" Ustvari Data/auth.py s svojimi podatki (glej Data/auth_public.py).")
        return 1

    # --force preskoči vprašanje
    if "--force" not in sys.argv:
        print()
        print(" OPOZORILO: vse obstoječe tabele in podatki bodo POBRISANI.")
        odgovor = input(" Nadaljujem? Vpiši 'da': ").strip().lower()
        if odgovor != "da":
            print(" Prekinjeno – nič ni bilo spremenjeno.")
            return 0

    repo = Repository()
    try:
        print("\n[1/2] Ustvarjam tabele, indekse in pogled ...")
        repo.izvedi_sql_datoteko(SHEMA_SQL)
        print("      Tabele so ustvarjene.")

        print("[2/2] Podeljujem pravice (jurekr, javnost) ...")
        try:
            repo.izvedi_sql_datoteko(PRAVICE_SQL)
            print("      Pravice so podeljene.")
        except Exception as e:
            # Uporabnika jurekr/javnost morda ni (tuja baza, lokalni
            # Postgres) - shema je kljub temu že narejena.
            repo.conn.rollback()
            print(f"      OPOZORILO: pravic ni bilo mogoče podeliti: {e}")
            print("      (Shema je kljub temu ustvarjena.)")

        print("\n Baza je pripravljena.")
        print(" Naslednji korak:  python -m Data.nalozi_v_bazo")
        return 0
    finally:
        repo.zapri()


if __name__ == "__main__":
    sys.exit(main())
