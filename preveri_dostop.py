"""
============================================================================
 OPB – Najem nepremičnin
 Datoteka: preveri_dostop.py

 PREVERI JAVNI DOSTOP DO BAZE (uporabnik 'javnost').

 Aplikacija se poveže kot 'javnost', kadar Data/auth.py ne obstaja – torej
 pri vsakem, ki projekt klonira z GitHuba. Ta skripta pove, ali tak dostop
 res deluje in kaj vse sme.

 ZAGON:
     python preveri_dostop.py
     (v VS Code:  Terminal -> Run Task…  ->  "9 · Preveri javni dostop")

 Skripta v bazo NIČESAR ne zapiše. Pravice prebere s funkcijo
 has_table_privilege(), zato ni treba ničesar vstavljati ali brisati.
============================================================================
"""

import os
import sys

import psycopg2

import Data.auth_public as javni

# Kaj mora javni dostop znati – tako je zapisano v Data/pravice.sql.
PRICAKOVANO = [
    ("oglas",        "SELECT", True,  "brskanje po oglasih"),
    ("oglas",        "INSERT", True,  "dodajanje oglasa prek obrazca"),
    ("oglas",        "UPDATE", False, "urejanje – dovoljeno samo osebnemu dostopu"),
    ("oglas",        "DELETE", False, "brisanje – dovoljeno samo osebnemu dostopu"),
    ("nepremicnina", "INSERT", True,  "nepremičnina novega oglasa"),
    ("lokacija",     "INSERT", True,  "nova lokacija, če je še ni"),
    ("uporabnik",    "INSERT", True,  "registracija novega uporabnika"),
    ("uporabnik",    "UPDATE", True,  "zadnja prijava, dodelitev vloge"),
]


def main() -> int:
    host = os.environ.get("DB_HOST", javni.host)
    port = int(os.environ.get("DB_PORT", getattr(javni, "port", 5432)))

    print("=" * 70)
    print(" PREVERJANJE JAVNEGA DOSTOPA")
    print(f" Baza:      {javni.db}")
    print(f" Strežnik:  {host}:{port}")
    print(f" Uporabnik: {javni.user}   (geslo iz Data/auth_public.py)")
    print("=" * 70)

    # ── 1. Ali se sploh lahko povežemo? ─────────────────────────────────────
    try:
        conn = psycopg2.connect(
            dbname=javni.db, host=host, user=javni.user,
            password=javni.password, port=port, connect_timeout=10,
        )
    except psycopg2.OperationalError as e:
        sporocilo = str(e).strip()
        print("\n POVEZAVA NI USPELA:\n")
        print(f"   {sporocilo}\n")

        if "password authentication failed" in sporocilo:
            print(" Geslo v Data/auth_public.py se ne ujema z geslom v bazi.")
            print(" Popravi ga tam ali pa geslo v bazi nastavi na to vrednost:")
            print(f"   ALTER ROLE {javni.user} PASSWORD '{javni.password}';")
        elif "does not exist" in sporocilo:
            print(f" Uporabnika '{javni.user}' na strežniku ni. Ustvari ga:")
            print(f"   CREATE ROLE {javni.user} LOGIN PASSWORD '{javni.password}';")
            print(" (Za oba ukaza potrebuješ dostop, ki sme upravljati vloge.)")
        else:
            print(" Preveri omrežje – strežnik FMF je dosegljiv samo z")
            print(" univerzitetnega omrežja oziroma prek VPN.")
        return 1

    # ── 2. Kaj v bazi sploh vidimo? ─────────────────────────────────────────
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM oglas")
            stevilo = cur.fetchone()[0]
            print(f"\n Povezava DELUJE. Oglasov v bazi: {stevilo}")

            # ── 3. Katere pravice ima ta uporabnik? ─────────────────────────
            #
            # has_table_privilege() vrne TRUE/FALSE, ne da bi karkoli
            # spremenila – zato lahko pravice preverimo brez tveganja.
            print("\n PRAVICE UPORABNIKA:\n")
            print(f"   {'TABELA':<14} {'PRAVICA':<8} {'STANJE':<10} POMEN")
            print("   " + "-" * 76)

            napake = []
            for tabela, pravica, mora_imeti, pomen in PRICAKOVANO:
                cur.execute(
                    "SELECT has_table_privilege(%s, %s, %s)",
                    (javni.user, tabela, pravica),
                )
                ima = cur.fetchone()[0]
                ustreza = (ima == mora_imeti)
                stanje = ("DA" if ima else "NE") + ("" if ustreza else "  <-- !")
                print(f"   {tabela:<14} {pravica:<8} {stanje:<10} {pomen}")
                if not ustreza:
                    napake.append((tabela, pravica, mora_imeti))
    finally:
        # Za SELECT-om psycopg2 pusti odprto transakcijo – zaključimo jo.
        conn.rollback()
        conn.close()

    # ── 4. Zaključek ────────────────────────────────────────────────────────
    print()
    if not napake:
        print(" VSE JE, KOT MORA BITI.")
        print(" Javni dostop sme brati in dodajati, ne sme pa urejati ali brisati.")
        return 0

    print(" PRAVICE SE NE UJEMAJO S PRIČAKOVANIMI:")
    for tabela, pravica, mora_imeti in napake:
        if mora_imeti:
            print(f"   manjka  {pravica} na {tabela}")
        else:
            print(f"   odveč   {pravica} na {tabela}")
    print()
    print(" Popravi jih tako, da z OSEBNIM dostopom izvedeš Data/pravice.sql:")
    print("   python podeli_pravice.py")
    print(" (v VS Code: Run Task… -> '8 · Podeli pravice v bazi')")
    return 1


if __name__ == "__main__":
    sys.exit(main())
