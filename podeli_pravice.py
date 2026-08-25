"""
============================================================================
 OPB – Najem nepremičnin
 Datoteka: podeli_pravice.py

 IZVEDE Data/pravice.sql – podeli pravice uporabnikoma 'jurekr' in 'javnost'.

 Isto naredi tudi init_db.py, a ta najprej POBRIŠE vse tabele. Kadar želimo
 samo osvežiti pravice (npr. ko smo pravice.sql spremenili), uporabimo to
 skripto – podatki ostanejo nedotaknjeni.

 ZAGON:
     python podeli_pravice.py
     (v VS Code:  Terminal -> Run Task…  ->  "8 · Podeli pravice v bazi")

 Potrebuješ Data/auth.py – pravice lahko podeli samo lastnik tabel.
 Enako bi naredil ukaz:
     psql -h baza.fmf.uni-lj.si -U urhvid -d sem2026_urhvid -f Data/pravice.sql
 vendar psql ni nujno nameščen, ta skripta pa uporabi psycopg2, ki ga imamo.
============================================================================
"""

import os
import sys

from Data.repository import DB_NAME, DB_USER, JE_PISALNI_DOSTOP, Repository

PRAVICE_SQL = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Data", "pravice.sql"
)


def main() -> int:
    print("=" * 70)
    print(" PODELJEVANJE PRAVIC")
    print(f" Baza: {DB_NAME} (povezan kot: {DB_USER})")
    print("=" * 70)

    if not JE_PISALNI_DOSTOP:
        print("\n NAPAKA: povezan si kot 'javnost'.")
        print(" Pravice lahko podeli samo lastnik tabel – ustvari Data/auth.py")
        print(" s svojimi podatki (glej Data/auth_public.py).")
        return 1

    repo = Repository()
    try:
        repo.izvedi_sql_datoteko(PRAVICE_SQL)
        print("\n Pravice so podeljene.")
        print(" Preveri jih z:  python preveri_dostop.py")
        return 0
    except Exception as e:
        repo.conn.rollback()
        print(f"\n NAPAKA: {e}")
        print("\n Če se pritožuje nad uporabnikom 'jurekr' ali 'javnost',")
        print(" ta na strežniku ne obstaja – vrstice zanj v Data/pravice.sql")
        print(" zakomentiraj in poskusi znova.")
        return 1
    finally:
        repo.zapri()


if __name__ == "__main__":
    sys.exit(main())
