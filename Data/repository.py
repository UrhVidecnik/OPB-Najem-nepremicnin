"""Podatkovni nivo: vse SQL poizvedbe projekta.

Edina datoteka, ki se pogovarja s PostgreSQL; nivoji nad njo delajo samo
s Python objekti iz Data/models.py. Parametrov ne lepimo v SQL z f-stringi,
ampak jih podamo prek %s - psycopg2 poskrbi za ubežanje in s tem prepreči
SQL injection.
"""

import os
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Tuple

import psycopg2
import psycopg2.extensions
import psycopg2.extras

from Data.models import (
    Lokacija,
    Nepremicnina,
    Oglas,
    OglasDTO,
    OglasFiltriDTO,
    Regija,
    StatistikaDTO,
    StranDTO,
    Uporabnik,
    Vir,
    VrsticaPoRegijiDTO,
    VrstaNepremicnine,
)

# Poskrbimo, da psycopg2 vrača prave Python nize (šumniki ČŠŽ).
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)


# Podatke za povezavo iščemo po vrsti: okoljske spremenljivke (uporablja jih
# Binder), nato Data/auth.py (osebni dostop s pravico pisanja, ni v gitu) in
# nazadnje Data/auth_public.py (javni bralni dostop).

try:
    import Data.auth as auth            # type: ignore
    _VIR_NASTAVITEV = "Data/auth.py"
except ImportError:
    import Data.auth_public as auth     # type: ignore
    _VIR_NASTAVITEV = "Data/auth_public.py"


DB_NAME = os.environ.get("DB_NAME", auth.db)
DB_HOST = os.environ.get("DB_HOST", auth.host)
DB_USER = os.environ.get("DB_USER", auth.user)
DB_PASSWORD = os.environ.get("DB_PASSWORD", auth.password)
DB_PORT = int(os.environ.get("DB_PORT", getattr(auth, "port", 5432)))

# Uporabnik 'javnost' ima po Data/pravice.sql pravico SELECT nad vsemi tabelami
# in INSERT nad oglasi, nepremičninami, lokacijami in uporabniki, nima pa UPDATE
# in DELETE nad oglasi – urejanja in brisanja torej ni mogoče izvesti niti mimo
# aplikacije. Osebni dostop iz Data/auth.py ima vse pravice; aplikacija to
# zastavico prebere in gumbe za urejanje po potrebi skrije.
JE_JAVNI_DOSTOP = DB_USER == "javnost"
JE_PISALNI_DOSTOP = not JE_JAVNI_DOSTOP    # sme UPDATE in DELETE (urejanje, brisanje)
JE_DODAJANJE_MOZNO = True                  # INSERT sme tudi 'javnost'


# Dovoljena razvrščanja. Ključ pride iz obrazca, v SQL pa gre vrednost iz tega
# slovarja – tako uporabnik na ORDER BY ne more vplivati.
UREJANJA = {
    "cena_asc":   "o.cena ASC",
    "cena_desc":  "o.cena DESC",
    "m2_asc":     "n.m2 ASC",
    "m2_desc":    "n.m2 DESC",
    "eur_m2_asc": "(o.cena / NULLIF(n.m2, 0)) ASC",
    "eur_m2_desc": "(o.cena / NULLIF(n.m2, 0)) DESC",
    "leto_desc":  "n.leto_gradnje DESC NULLS LAST",
    "naslov_asc": "lower(o.naslov) ASC",
    "novi":       "o.datum_zajema DESC, o.id_oglasa DESC",
}


class Repository:
    """Dostop do baze. Ena instanca = ena odprta povezava."""

    # Povezava

    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME,
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
        )
        # autocommit=False (privzeto) – transakcijo zaključimo sami s commit().

    def _cur(self):
        """Kurzor za PISANJE. Vrstice vrača kot slovarje.

        Brez RealDictCursor bi vrstice dobili kot terke in bi do stolpcev
        dostopali z row[0], row[1] ... – kar je neberljivo in krhko.
        Z njim pišemo row["cena"].

        Za tem kurzorjem je treba poklicati self.conn.commit().
        """
        return self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    @contextmanager
    def _beri(self):
        """Kurzor za BRANJE, ki transakcijo na koncu vedno zaključi.

        ZAKAJ je to potrebno:
        psycopg2 ob prvem ukazu SAM odpre transakcijo – tudi pri navadnem
        SELECT. Če je ne zaključimo, povezava obtiči v stanju
        'idle in transaction' in DRŽI ZAKLEPE (locks) na prebranih tabelah.
        Posledice na skupnem strežniku FMF:
          - ukaz DROP TABLE (npr. iz init_db.py) čaka v nedogled;
          - Postgres ne more počistiti starih vrstic (VACUUM);
          - dolge odprte transakcije zasedajo povezave.

        Rešitev: po branju pokličemo rollback(). Ker nismo ničesar
        spreminjali, rollback ne "razveljavi" nobenega podatka – samo
        zaključi transakcijo in sprosti zaklepe.
        """
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
        finally:
            cur.close()
            if not self.conn.closed:
                self.conn.rollback()

    def zapri(self) -> None:
        """Zapre povezavo z bazo."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    # Podpora za `with Repository() as repo:` – povezava se zapre sama.
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.zapri()

    # Ustvarjanje sheme

    def izvedi_sql_datoteko(self, pot: str) -> None:
        """Prebere .sql datoteko in jo izvede. Uporablja jo init_db.py."""
        with open(pot, "r", encoding="utf-8") as f:
            sql = f.read()
        with self.conn.cursor() as cur:
            cur.execute(sql)
        self.conn.commit()

    # VIR

    def dodaj_vir(self, vir: Vir) -> Vir:
        """Vstavi nov vir in vrne isti objekt z izpolnjenim id_vira."""
        with self._cur() as cur:
            cur.execute(
                """
                INSERT INTO vir (ime_vira, url_vira)
                VALUES (%s, %s)
                RETURNING id_vira
                """,
                (vir.ime_vira, vir.url_vira),
            )
            # RETURNING nam takoj vrne ID, ki ga je dodelil SERIAL –
            # brez dodatne poizvedbe.
            vir.id_vira = cur.fetchone()["id_vira"]
        self.conn.commit()
        return vir

    def dobi_ali_dodaj_vir(self, ime_vira: str, url_vira: Optional[str] = None) -> Vir:
        """Vrne obstoječi vir z danim imenom, sicer ga ustvari.

        Ta 'dobi ali dodaj' vzorec potrebujemo pri uvozu: skripto lahko
        poženemo večkrat, pa se šifranti ne bodo podvajali.
        """
        with self._cur() as cur:
            cur.execute("SELECT * FROM vir WHERE ime_vira = %s", (ime_vira,))
            vrstica = cur.fetchone()
            if vrstica:
                # Vir že obstaja – ničesar nismo spremenili, a SELECT je
                # odprl transakcijo, zato jo tu zaključimo (glej _beri()).
                self.conn.rollback()
                return Vir(**vrstica)

            cur.execute(
                "INSERT INTO vir (ime_vira, url_vira) VALUES (%s, %s) RETURNING id_vira",
                (ime_vira, url_vira),
            )
            nov_id = cur.fetchone()["id_vira"]
        self.conn.commit()
        return Vir(id_vira=nov_id, ime_vira=ime_vira, url_vira=url_vira)

    def dobi_vir(self, id_vira: int) -> Optional[Vir]:
        with self._beri() as cur:
            cur.execute("SELECT * FROM vir WHERE id_vira = %s", (id_vira,))
            vrstica = cur.fetchone()
        return Vir(**vrstica) if vrstica else None

    def seznam_virov(self) -> List[Vir]:
        """Vsi viri – za spustni seznam v obrazcu za filtriranje."""
        with self._beri() as cur:
            cur.execute("SELECT * FROM vir ORDER BY ime_vira")
            return [Vir(**v) for v in cur.fetchall()]

    # VRSTA NEPREMIČNINE

    def dobi_ali_dodaj_vrsto(self, ime_vrste: str) -> VrstaNepremicnine:
        with self._cur() as cur:
            cur.execute(
                "SELECT * FROM vrsta_nepremicnine WHERE ime_vrste = %s", (ime_vrste,)
            )
            vrstica = cur.fetchone()
            if vrstica:
                self.conn.rollback()      # zaključimo transakcijo od SELECT-a
                return VrstaNepremicnine(**vrstica)

            cur.execute(
                "INSERT INTO vrsta_nepremicnine (ime_vrste) VALUES (%s) RETURNING id_vrste",
                (ime_vrste,),
            )
            nov_id = cur.fetchone()["id_vrste"]
        self.conn.commit()
        return VrstaNepremicnine(id_vrste=nov_id, ime_vrste=ime_vrste)

    def seznam_vrst(self) -> List[VrstaNepremicnine]:
        with self._beri() as cur:
            cur.execute("SELECT * FROM vrsta_nepremicnine ORDER BY ime_vrste")
            return [VrstaNepremicnine(**v) for v in cur.fetchall()]

    # REGIJA

    def dobi_ali_dodaj_regijo(self, ime_regije: str, drzava: str = "SI") -> Regija:
        with self._cur() as cur:
            cur.execute(
                "SELECT * FROM regija WHERE ime_regije = %s AND drzava = %s",
                (ime_regije, drzava),
            )
            vrstica = cur.fetchone()
            if vrstica:
                self.conn.rollback()      # zaključimo transakcijo od SELECT-a
                return Regija(**vrstica)

            cur.execute(
                "INSERT INTO regija (ime_regije, drzava) VALUES (%s, %s) RETURNING id_regije",
                (ime_regije, drzava),
            )
            nov_id = cur.fetchone()["id_regije"]
        self.conn.commit()
        return Regija(id_regije=nov_id, ime_regije=ime_regije, drzava=drzava)

    def seznam_regij(self, drzava: Optional[str] = None) -> List[Regija]:
        """Vse regije, po želji omejeno na eno državo (za spustni seznam)."""
        with self._beri() as cur:
            if drzava:
                cur.execute(
                    "SELECT * FROM regija WHERE drzava = %s ORDER BY ime_regije",
                    (drzava,),
                )
            else:
                cur.execute("SELECT * FROM regija ORDER BY drzava, ime_regije")
            return [Regija(**v) for v in cur.fetchall()]

    # LOKACIJA

    def dobi_ali_dodaj_lokacijo(
        self,
        id_regije: Optional[int] = None,
        upravna_enota: Optional[str] = None,
        obcina: Optional[str] = None,
        naselje: Optional[str] = None,
        postna_stevilka: Optional[int] = None,
    ) -> Lokacija:
        """Vrne lokacijo z natanko temi štirimi vrednostmi ali jo ustvari.

        Pozor na `IS NOT DISTINCT FROM`: navadni `=` v SQL vrne NULL
        (torej "ne ujema se"), kadar je katera stran NULL.
        `IS NOT DISTINCT FROM` pa NULL primerja z NULL kot enaka.
        """
        with self._cur() as cur:
            cur.execute(
                """
                SELECT * FROM lokacija
                WHERE id_regije     IS NOT DISTINCT FROM %s
                  AND upravna_enota IS NOT DISTINCT FROM %s
                  AND obcina        IS NOT DISTINCT FROM %s
                  AND naselje       IS NOT DISTINCT FROM %s
                """,
                (id_regije, upravna_enota, obcina, naselje),
            )
            vrstica = cur.fetchone()
            if vrstica:
                self.conn.rollback()      # zaključimo transakcijo od SELECT-a
                return Lokacija(**vrstica)

            cur.execute(
                """
                INSERT INTO lokacija (id_regije, upravna_enota, obcina, naselje, postna_stevilka)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id_lokacije
                """,
                (id_regije, upravna_enota, obcina, naselje, postna_stevilka),
            )
            nov_id = cur.fetchone()["id_lokacije"]
        self.conn.commit()
        return Lokacija(
            id_lokacije=nov_id,
            id_regije=id_regije,
            upravna_enota=upravna_enota,
            obcina=obcina,
            naselje=naselje,
            postna_stevilka=postna_stevilka,
        )

    def seznam_lokacij(self, id_regije: Optional[int] = None) -> List[Lokacija]:
        """Lokacije skupaj z imenom regije (JOIN), za spustni seznam."""
        sql = """
            SELECT l.*, r.ime_regije, r.drzava
            FROM lokacija l
            LEFT JOIN regija r ON r.id_regije = l.id_regije
        """
        parametri: list = []
        if id_regije is not None:
            sql += " WHERE l.id_regije = %s"
            parametri.append(id_regije)
        sql += " ORDER BY r.ime_regije NULLS LAST, l.obcina NULLS LAST, l.naselje NULLS LAST"

        with self._beri() as cur:
            cur.execute(sql, parametri)
            return [Lokacija(**v) for v in cur.fetchall()]

    # NEPREMIČNINA

    def dodaj_nepremicnino(self, n: Nepremicnina) -> Nepremicnina:
        with self._cur() as cur:
            cur.execute(
                """
                INSERT INTO nepremicnina
                    (id_vrste, id_lokacije, opis, leto_gradnje,
                     stevilo_sob, stevilo_sob_opis, nadstropje, m2)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_nepremicnine
                """,
                (n.id_vrste, n.id_lokacije, n.opis, n.leto_gradnje,
                 n.stevilo_sob, n.stevilo_sob_opis, n.nadstropje, n.m2),
            )
            n.id_nepremicnine = cur.fetchone()["id_nepremicnine"]
        self.conn.commit()
        return n

    def posodobi_nepremicnino(self, n: Nepremicnina) -> Nepremicnina:
        with self._cur() as cur:
            cur.execute(
                """
                UPDATE nepremicnina
                SET id_vrste = %s, id_lokacije = %s, opis = %s, leto_gradnje = %s,
                    stevilo_sob = %s, stevilo_sob_opis = %s, nadstropje = %s, m2 = %s
                WHERE id_nepremicnine = %s
                """,
                (n.id_vrste, n.id_lokacije, n.opis, n.leto_gradnje,
                 n.stevilo_sob, n.stevilo_sob_opis, n.nadstropje, n.m2,
                 n.id_nepremicnine),
            )
        self.conn.commit()
        return n

    # OGLAS

    def dodaj_oglas(self, og: Oglas) -> Oglas:
        with self._cur() as cur:
            cur.execute(
                """
                INSERT INTO oglas
                    (id_vira, id_nepremicnine, zunanji_id, naslov,
                     url_oglasa, cena, valuta, datum_objave, datum_zajema)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_DATE))
                RETURNING id_oglasa, datum_zajema
                """,
                (og.id_vira, og.id_nepremicnine, og.zunanji_id, og.naslov,
                 og.url_oglasa, og.cena, og.valuta, og.datum_objave, og.datum_zajema),
            )
            vrstica = cur.fetchone()
            og.id_oglasa = vrstica["id_oglasa"]
            og.datum_zajema = vrstica["datum_zajema"]
        self.conn.commit()
        return og

    def posodobi_oglas(self, og: Oglas) -> Oglas:
        with self._cur() as cur:
            cur.execute(
                """
                UPDATE oglas
                SET naslov = %s, url_oglasa = %s, cena = %s,
                    valuta = %s, datum_objave = %s
                WHERE id_oglasa = %s
                """,
                (og.naslov, og.url_oglasa, og.cena, og.valuta,
                 og.datum_objave, og.id_oglasa),
            )
        self.conn.commit()
        return og

    def izbrisi_oglas(self, id_oglasa: int) -> bool:
        """Pobriše oglas IN pripadajočo nepremičnino.

        Nepremičnino brišemo eksplicitno, ker tuji ključ kaže v nasprotno
        smer (oglas -> nepremicnina), zato je ON DELETE CASCADE sam ne odstrani.
        Obe brisanji sta v ISTI transakciji: če druga spodleti, se prva razveljavi.
        """
        with self._cur() as cur:
            cur.execute(
                "DELETE FROM oglas WHERE id_oglasa = %s RETURNING id_nepremicnine",
                (id_oglasa,),
            )
            vrstica = cur.fetchone()
            if vrstica is None:
                self.conn.rollback()
                return False

            # Nepremičnino pobrišemo samo, če nanjo ne kaže noben drug oglas.
            cur.execute(
                """
                DELETE FROM nepremicnina
                WHERE id_nepremicnine = %s
                  AND NOT EXISTS (
                        SELECT 1 FROM oglas WHERE id_nepremicnine = %s
                  )
                """,
                (vrstica["id_nepremicnine"], vrstica["id_nepremicnine"]),
            )
        self.conn.commit()
        return True

    def obstaja_zunanji_id(self, id_vira: int, zunanji_id: str) -> bool:
        """Ali oglas s tem ID-jem s portala že imamo? (za idempotenten uvoz)"""
        with self._beri() as cur:
            cur.execute(
                "SELECT 1 FROM oglas WHERE id_vira = %s AND zunanji_id = %s",
                (id_vira, zunanji_id),
            )
            return cur.fetchone() is not None

    def obstojeci_zunanji_idji(self, id_vira: int) -> set:
        """Vsi zunanji ID-ji tega vira naenkrat.

        Pri uvozu 2700 oglasov je to ENA poizvedba namesto 2700 –
        uvoz je s tem bistveno hitrejši.
        """
        with self._beri() as cur:
            cur.execute(
                "SELECT zunanji_id FROM oglas WHERE id_vira = %s AND zunanji_id IS NOT NULL",
                (id_vira,),
            )
            return {v["zunanji_id"] for v in cur.fetchall()}

    # Branje oglasov s filtri

    def _sestavi_pogoje(self, f: Optional[OglasFiltriDTO]) -> Tuple[str, list]:
        """Iz filtrov sestavi WHERE del poizvedbe in seznam parametrov.

        Vrne npr. ("WHERE o.cena >= %s AND n.m2 <= %s", [500, 80]).
        Ta ista metoda se uporabi pri seznamu, štetju IN statistiki,
        zato so rezultati vedno usklajeni.
        """
        if f is None:
            return "", []

        pogoji: List[str] = []
        vrednosti: list = []

        if f.iskanje:
            # ILIKE = LIKE, neobčutljiv na velike/male črke.
            # Iščemo po naslovu ALI po opisu ALI po imenu naselja/občine.
            pogoji.append("""(
                o.naslov ILIKE %s
                OR n.opis ILIKE %s
                OR l.naselje ILIKE %s
                OR l.obcina ILIKE %s
            )""")
            vzorec = f"%{f.iskanje.strip()}%"
            vrednosti.extend([vzorec, vzorec, vzorec, vzorec])

        if f.id_vrste is not None:
            pogoji.append("n.id_vrste = %s")
            vrednosti.append(f.id_vrste)

        if f.id_regije is not None:
            pogoji.append("l.id_regije = %s")
            vrednosti.append(f.id_regije)

        if f.id_lokacije is not None:
            pogoji.append("n.id_lokacije = %s")
            vrednosti.append(f.id_lokacije)

        if f.drzava:
            pogoji.append("r.drzava = %s")
            vrednosti.append(f.drzava)

        if f.id_vira is not None:
            pogoji.append("o.id_vira = %s")
            vrednosti.append(f.id_vira)

        if f.cena_min is not None:
            pogoji.append("o.cena >= %s")
            vrednosti.append(f.cena_min)

        if f.cena_max is not None:
            pogoji.append("o.cena <= %s")
            vrednosti.append(f.cena_max)

        if f.m2_min is not None:
            pogoji.append("n.m2 >= %s")
            vrednosti.append(f.m2_min)

        if f.m2_max is not None:
            pogoji.append("n.m2 <= %s")
            vrednosti.append(f.m2_max)

        if f.sobe_min is not None:
            pogoji.append("n.stevilo_sob >= %s")
            vrednosti.append(f.sobe_min)

        if f.leto_min is not None:
            pogoji.append("n.leto_gradnje >= %s")
            vrednosti.append(f.leto_min)

        if not pogoji:
            return "", []
        return " WHERE " + " AND ".join(pogoji), vrednosti

    # Skupni FROM z JOIN-i – uporabimo ga v več metodah, da ga ne podvajamo.
    _OSNOVA = """
        FROM oglas o
            JOIN nepremicnina       n  ON n.id_nepremicnine = o.id_nepremicnine
            JOIN vrsta_nepremicnine vn ON vn.id_vrste       = n.id_vrste
            JOIN lokacija           l  ON l.id_lokacije     = n.id_lokacije
            JOIN vir                vi ON vi.id_vira        = o.id_vira
            LEFT JOIN regija        r  ON r.id_regije       = l.id_regije
    """

    def _v_dto(self, r: dict) -> OglasDTO:
        """Eno vrstico iz baze pretvori v OglasDTO."""
        return OglasDTO(
            oglas=Oglas(
                id_oglasa=r["id_oglasa"], id_vira=r["id_vira"],
                id_nepremicnine=r["id_nepremicnine"], zunanji_id=r["zunanji_id"],
                naslov=r["naslov"], url_oglasa=r["url_oglasa"],
                cena=float(r["cena"]), valuta=r["valuta"],
                datum_objave=r["datum_objave"], datum_zajema=r["datum_zajema"],
            ),
            nepremicnina=Nepremicnina(
                id_nepremicnine=r["id_nepremicnine"], id_vrste=r["id_vrste"],
                id_lokacije=r["id_lokacije"], opis=r["opis"],
                leto_gradnje=r["leto_gradnje"],
                stevilo_sob=float(r["stevilo_sob"]) if r["stevilo_sob"] is not None else None,
                stevilo_sob_opis=r["stevilo_sob_opis"], nadstropje=r["nadstropje"],
                m2=float(r["m2"]),
            ),
            lokacija=Lokacija(
                id_lokacije=r["id_lokacije"], id_regije=r["id_regije"],
                upravna_enota=r["upravna_enota"], obcina=r["obcina"],
                naselje=r["naselje"], postna_stevilka=r["postna_stevilka"],
                ime_regije=r["ime_regije"], drzava=r["drzava"],
            ),
            vrsta=VrstaNepremicnine(id_vrste=r["id_vrste"], ime_vrste=r["ime_vrste"]),
            vir=Vir(id_vira=r["id_vira"], ime_vira=r["ime_vira"], url_vira=r["url_vira"]),
            cena_na_m2=float(r["cena_na_m2"]) if r.get("cena_na_m2") is not None else None,
        )

    def prestej_oglase(self, filtri: Optional[OglasFiltriDTO] = None) -> int:
        """Koliko oglasov ustreza filtrom. Potrebujemo za paginacijo."""
        where, vrednosti = self._sestavi_pogoje(filtri)
        with self._beri() as cur:
            cur.execute("SELECT COUNT(*) AS n " + self._OSNOVA + where, vrednosti)
            return int(cur.fetchone()["n"])

    def seznam_oglasov(
        self,
        filtri: Optional[OglasFiltriDTO] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[OglasDTO]:
        """Vrne (filtrirane, urejene, ostranjene) oglase.

        LIMIT/OFFSET sta ključna: brez njiju bi vsakič prenesli vseh 2700
        oglasov skupaj s polnimi opisi – stran bi se nalagala nekaj sekund.
        """
        where, vrednosti = self._sestavi_pogoje(filtri)

        urejanje_kljuc = (filtri.urejanje if filtri else "cena_asc")
        # .get s privzeto vrednostjo: če uporabnik v URL vpiše karkoli
        # drugega, tiho uporabimo varno privzeto razvrščanje.
        order_by = UREJANJA.get(urejanje_kljuc, UREJANJA["cena_asc"])

        sql = f"""
            SELECT
                o.id_oglasa, o.id_vira, o.id_nepremicnine, o.zunanji_id, o.naslov,
                o.url_oglasa, o.cena, o.valuta, o.datum_objave, o.datum_zajema,
                ROUND(o.cena / NULLIF(n.m2, 0), 2) AS cena_na_m2,
                n.opis, n.leto_gradnje, n.stevilo_sob, n.stevilo_sob_opis,
                n.nadstropje, n.m2,
                vn.id_vrste, vn.ime_vrste,
                l.id_lokacije, l.upravna_enota, l.obcina, l.naselje, l.postna_stevilka,
                r.id_regije, r.ime_regije, r.drzava,
                vi.ime_vira, vi.url_vira
            {self._OSNOVA}
            {where}
            ORDER BY {order_by}, o.id_oglasa
        """
        # Dodamo še id_oglasa kot zadnji kriterij: brez njega bi oglasi
        # z enako ceno lahko med stranmi "skakali" sem ter tja.

        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            vrednosti = vrednosti + [limit, offset]

        with self._beri() as cur:
            cur.execute(sql, vrednosti)
            return [self._v_dto(v) for v in cur.fetchall()]

    def stran_oglasov(
        self,
        filtri: Optional[OglasFiltriDTO] = None,
        stran: int = 1,
        na_stran: int = 25,
    ) -> StranDTO:
        """Ena stran rezultatov skupaj s podatki za navigacijo."""
        skupaj = self.prestej_oglase(filtri)

        # Popravimo številko strani, če je uporabnik vpisal nesmisel v URL.
        stevilo_strani = max(1, (skupaj + na_stran - 1) // na_stran)
        stran = max(1, min(stran, stevilo_strani))

        oglasi = self.seznam_oglasov(
            filtri, limit=na_stran, offset=(stran - 1) * na_stran
        )
        return StranDTO(oglasi=oglasi, stran=stran, na_stran=na_stran, skupaj=skupaj)

    def dobi_oglas(self, id_oglasa: int) -> Optional[OglasDTO]:
        """En oglas z vsemi podatki – za stran s podrobnostmi."""
        sql = f"""
            SELECT
                o.id_oglasa, o.id_vira, o.id_nepremicnine, o.zunanji_id, o.naslov,
                o.url_oglasa, o.cena, o.valuta, o.datum_objave, o.datum_zajema,
                ROUND(o.cena / NULLIF(n.m2, 0), 2) AS cena_na_m2,
                n.opis, n.leto_gradnje, n.stevilo_sob, n.stevilo_sob_opis,
                n.nadstropje, n.m2,
                vn.id_vrste, vn.ime_vrste,
                l.id_lokacije, l.upravna_enota, l.obcina, l.naselje, l.postna_stevilka,
                r.id_regije, r.ime_regije, r.drzava,
                vi.ime_vira, vi.url_vira
            {self._OSNOVA}
            WHERE o.id_oglasa = %s
        """
        with self._beri() as cur:
            cur.execute(sql, (id_oglasa,))
            vrstica = cur.fetchone()
        return self._v_dto(vrstica) if vrstica else None

    # STATISTIKA

    def statistika(self, filtri: Optional[OglasFiltriDTO] = None) -> StatistikaDTO:
        """Agregatne funkcije nad (filtriranimi) oglasi.

        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ...) je standardni
        SQL način za mediano – Postgres nima funkcije MEDIAN().
        """
        where, vrednosti = self._sestavi_pogoje(filtri)
        sql = f"""
            SELECT
                COUNT(*)                                                   AS stevilo_oglasov,
                AVG(o.cena)                                                AS povprecna_cena,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY o.cena)        AS mediana_cena,
                MIN(o.cena)                                                AS minimalna_cena,
                MAX(o.cena)                                                AS maksimalna_cena,
                AVG(n.m2)                                                  AS povprecna_m2,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n.m2)          AS mediana_m2,
                SUM(n.m2)                                                  AS skupna_povrsina_m2,
                AVG(o.cena / NULLIF(n.m2, 0))                              AS povprecna_cena_na_m2,
                MIN(o.cena / NULLIF(n.m2, 0))                              AS minimalna_cena_na_m2,
                MAX(o.cena / NULLIF(n.m2, 0))                              AS maksimalna_cena_na_m2,
                AVG(n.stevilo_sob)                                         AS povprecno_stevilo_sob
            {self._OSNOVA}
            {where}
        """
        with self._beri() as cur:
            cur.execute(sql, vrednosti)
            r = cur.fetchone()

        # `or 0` pokrije primer prazne množice, kjer AVG vrne NULL.
        return StatistikaDTO(
            stevilo_oglasov=int(r["stevilo_oglasov"] or 0),
            povprecna_cena=float(r["povprecna_cena"] or 0),
            mediana_cena=float(r["mediana_cena"] or 0),
            minimalna_cena=float(r["minimalna_cena"] or 0),
            maksimalna_cena=float(r["maksimalna_cena"] or 0),
            povprecna_m2=float(r["povprecna_m2"] or 0),
            mediana_m2=float(r["mediana_m2"] or 0),
            skupna_povrsina_m2=float(r["skupna_povrsina_m2"] or 0),
            povprecna_cena_na_m2=float(r["povprecna_cena_na_m2"] or 0),
            minimalna_cena_na_m2=float(r["minimalna_cena_na_m2"] or 0),
            maksimalna_cena_na_m2=float(r["maksimalna_cena_na_m2"] or 0),
            povprecno_stevilo_sob=float(r["povprecno_stevilo_sob"] or 0),
        )

    def statistika_po_regijah(
        self, filtri: Optional[OglasFiltriDTO] = None, min_oglasov: int = 5
    ) -> List[VrsticaPoRegijiDTO]:
        """GROUP BY regija – po katerih regijah je najem najdražji.

        HAVING odreže regije z manj kot `min_oglasov` oglasi, ker je
        povprečje iz dveh oglasov nezanesljivo.
        """
        where, vrednosti = self._sestavi_pogoje(filtri)
        sql = f"""
            SELECT
                r.ime_regije,
                r.drzava,
                COUNT(*)                                            AS stevilo_oglasov,
                AVG(o.cena)                                         AS povprecna_cena,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY o.cena) AS mediana_cena,
                AVG(n.m2)                                           AS povprecna_m2,
                AVG(o.cena / NULLIF(n.m2, 0))                       AS povprecna_cena_na_m2
            {self._OSNOVA}
            {where}
            {"AND" if where else "WHERE"} r.ime_regije IS NOT NULL
            GROUP BY r.ime_regije, r.drzava
            HAVING COUNT(*) >= %s
            ORDER BY AVG(o.cena / NULLIF(n.m2, 0)) DESC NULLS LAST
        """
        with self._beri() as cur:
            cur.execute(sql, vrednosti + [min_oglasov])
            return [
                VrsticaPoRegijiDTO(
                    ime_regije=v["ime_regije"],
                    drzava=v["drzava"],
                    stevilo_oglasov=int(v["stevilo_oglasov"]),
                    povprecna_cena=float(v["povprecna_cena"] or 0),
                    mediana_cena=float(v["mediana_cena"] or 0),
                    povprecna_m2=float(v["povprecna_m2"] or 0),
                    povprecna_cena_na_m2=float(v["povprecna_cena_na_m2"] or 0),
                )
                for v in cur.fetchall()
            ]

    def statistika_po_vrstah(self, filtri: Optional[OglasFiltriDTO] = None) -> List[dict]:
        """GROUP BY vrsta nepremičnine – koliko oglasov in kakšna cena po vrstah."""
        where, vrednosti = self._sestavi_pogoje(filtri)
        sql = f"""
            SELECT
                vn.ime_vrste,
                COUNT(*)                      AS stevilo_oglasov,
                AVG(o.cena)                   AS povprecna_cena,
                AVG(n.m2)                     AS povprecna_m2,
                AVG(o.cena / NULLIF(n.m2, 0)) AS povprecna_cena_na_m2
            {self._OSNOVA}
            {where}
            GROUP BY vn.ime_vrste
            ORDER BY COUNT(*) DESC
        """
        with self._beri() as cur:
            cur.execute(sql, vrednosti)
            # Postgres vrne AVG kot Decimal; pretvorimo v float, da se v
            # predlogah lepo formatira z npr. "%.2f".
            return [
                {
                    "ime_vrste": v["ime_vrste"],
                    "stevilo_oglasov": int(v["stevilo_oglasov"]),
                    "povprecna_cena": float(v["povprecna_cena"] or 0),
                    "povprecna_m2": float(v["povprecna_m2"] or 0),
                    "povprecna_cena_na_m2": float(v["povprecna_cena_na_m2"] or 0),
                }
                for v in cur.fetchall()
            ]

    def porazdelitev_cen(
        self, filtri: Optional[OglasFiltriDTO] = None, sirina_razreda: int = 250
    ) -> List[dict]:
        """Histogram cen: koliko oglasov je v razredu 0-250 €, 250-500 € ...

        Trik: `WIDTH_BUCKET` bi bil eleganten, a potrebuje fiksne meje.
        Namesto tega ceno celoštevilsko delimo s širino razreda –
        FLOOR(cena / 250) * 250 nam da spodnjo mejo razreda.
        """
        where, vrednosti = self._sestavi_pogoje(filtri)
        sql = f"""
            SELECT
                (FLOOR(o.cena / %s) * %s)::int AS spodnja_meja,
                COUNT(*)                       AS stevilo
            {self._OSNOVA}
            {where}
            GROUP BY 1
            ORDER BY 1
        """
        with self._beri() as cur:
            cur.execute(sql, [sirina_razreda, sirina_razreda] + vrednosti)
            return [dict(v) for v in cur.fetchall()]

    def najdrazji_najcenejsi(self, koliko: int = 5) -> dict:
        """Top N najdražjih in najcenejših oglasov – za domačo stran."""
        najdrazji = self.seznam_oglasov(
            OglasFiltriDTO(urejanje="cena_desc"), limit=koliko
        )
        najcenejsi = self.seznam_oglasov(
            OglasFiltriDTO(urejanje="cena_asc"), limit=koliko
        )
        return {"najdrazji": najdrazji, "najcenejsi": najcenejsi}

    # UPORABNIK (prijava / registracija)

    def dobi_uporabnika(self, uporabnisko_ime: str) -> Optional[Uporabnik]:
        with self._beri() as cur:
            cur.execute(
                "SELECT * FROM uporabnik WHERE uporabnisko_ime = %s",
                (uporabnisko_ime,),
            )
            vrstica = cur.fetchone()
        return Uporabnik(**vrstica) if vrstica else None

    def dodaj_uporabnika(self, u: Uporabnik) -> Uporabnik:
        with self._cur() as cur:
            cur.execute(
                """
                INSERT INTO uporabnik (uporabnisko_ime, geslo_hash, vloga)
                VALUES (%s, %s, %s)
                """,
                (u.uporabnisko_ime, u.geslo_hash, u.vloga),
            )
        self.conn.commit()
        return u

    def zabelezi_prijavo(self, uporabnisko_ime: str) -> None:
        """Ob uspešni prijavi zapiše trenutni čas v zadnja_prijava."""
        with self._cur() as cur:
            cur.execute(
                "UPDATE uporabnik SET zadnja_prijava = %s WHERE uporabnisko_ime = %s",
                (datetime.now(), uporabnisko_ime),
            )
        self.conn.commit()

    def nastavi_vlogo(self, uporabnisko_ime: str, vloga: str) -> Optional[Uporabnik]:
        """Spremeni vlogo uporabnika ('admin' ali 'uporabnik').

        Vrne posodobljenega uporabnika, ali None, če ga v bazi ni.
        RETURNING * nam vrne posodobljeno vrstico takoj, zato ne
        potrebujemo dodatnega SELECT-a.
        """
        with self._cur() as cur:
            cur.execute(
                """
                UPDATE uporabnik
                   SET vloga = %s
                 WHERE uporabnisko_ime = %s
             RETURNING *
                """,
                (vloga, uporabnisko_ime),
            )
            vrstica = cur.fetchone()
        self.conn.commit()
        return Uporabnik(**vrstica) if vrstica else None

    def seznam_uporabnikov(self) -> List[Uporabnik]:
        with self._beri() as cur:
            cur.execute("SELECT * FROM uporabnik ORDER BY uporabnisko_ime")
            return [Uporabnik(**v) for v in cur.fetchall()]
