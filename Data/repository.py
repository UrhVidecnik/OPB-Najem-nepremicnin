import psycopg2, psycopg2.extensions, psycopg2.extras
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
import Data.auth_public as auth

from Data.models import Vir, Vrsta_nepremicnine, Lokacija, Nepremicnina, Oglas, OglasDTO, OglasFiltriDTO, StatisticsDTO
from typing import List, Optional


class Repository:
    def __init__(self):
        self.conn = psycopg2.connect(
            database=auth.db,
            host=auth.host,
            user=auth.user,
            password=auth.password,
            port=5432
        )


    def add_vir(self, vir: Vir) -> Vir:
        """Vnos (insert ukaz) novega vira v bazo."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
            INSERT INTO vir (ime_vira, url_vira)
            VALUES (%s, %s)
            RETURNING id_vira
            """, (vir.ime_vira, vir.url_vira))
            vir.id_vira = cur.fetchone()["id_vira"]
            return vir

    def get_vir_by_id(self, id_vira: int) -> Vir | None:
        """Dostop do posameznega vira."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id_vira, ime_vira, url_vira FROM vir WHERE id_vira = %s", (id_vira,))
            row = cur.fetchone()
            if not row:
                return None
            return Vir(id_vira=row["id_vira"], ime_vira=row["ime_vira"], url_vira=row.get("url_vira"))


    def list_viri(self) -> List[Vir]:
        """Dostop do vseh virov (za dropdown filter)."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id_vira, ime_vira, url_vira FROM vir ORDER BY ime_vira")
            return [Vir(id_vira=r["id_vira"], ime_vira=r["ime_vira"], url_vira=r.get("url_vira")) for r in cur.fetchall()]


    def list_vrste(self) -> List[Vrsta_nepremicnine]:
        """Dostop do vseh vrst nepremicnine (za dropdown filter)."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id_vrste, ime_vrste FROM vrsta_nepremicnine ORDER BY ime_vrste")
            return [Vrsta_nepremicnine(id_vrste=r["id_vrste"], ime_vrste=r["ime_vrste"]) for r in cur.fetchall()]
        

    def add_lokacija(self, lok: Lokacija) -> Lokacija:
        """Vnos (insert ukaz) nove lokacije v bazo."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
            INSERT INTO lokacija (ime, regija, soseska, postna_stevilka)
            VALUES (%s, %s, %s, %s)
            RETURNING id_lokacije
            """, (lok.ime, lok.regija, lok.soseska, lok.postna_stevilka))
            lok.id_lokacije = cur.fetchone()["id_lokacije"]
            return lok
        

    def list_lokacije(self) -> List[Lokacija]:
        """Dostop do vseh lokacij (za dropdown filter)."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id_lokacije, ime, regija, soseska, postna_stevilka FROM lokacija ORDER BY ime")
            rows = cur.fetchall()
            return [Lokacija(id_lokacije=r["id_lokacije"], ime=r["ime"], regija=r.get("regija"), soseska=r.get("soseska"), postna_stevilka=r.get("postna_stevilka")) for r in rows]
        
    
    def add_nepremicnina(self, n: Nepremicnina) -> Nepremicnina:
        """Vnos (insert ukaz) nove nepremicnine v bazo."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
            INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id_nepremicnine
            """, (n.id_vrste, n.id_lokacije, n.opis, n.leto_gradnje, n.stevilo_sob, n.nadstropje, n.m2))
            n.id_nepremicnine = cur.fetchone()["id_nepremicnine"]
            return n
        
    
    def add_oglas(self, og: Oglas) -> Oglas:
        """Vnos (insert ukaz) novega oglasa v bazo."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
            INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_oglasa
            """, (og.id_vira, og.id_nepremicnine, og.naslov, og.url_oglasa, og.cena, og.datum_objave))
            og.id_oglasa = cur.fetchone()["id_oglasa"]
            return og
    

    def get_oglasi_dto(self, filtri: Optional[OglasFiltriDTO] = None) -> List[OglasDTO]:
        """ Vrne vse oglase ali filtrirane oglase skupaj z vsemi podatki."""

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            sql = """
                SELECT
                    o.id_oglasa, o.naslov, o.url_oglasa, o.cena, o.datum_objave,
                    n.id_nepremicnine, n.opis, n.leto_gradnje, n.stevilo_sob, n.nadstropje, n.m2,
                    l.id_lokacije, l.ime, l.regija, l.soseska, l.postna_stevilka,
                    v.id_vrste, v.ime_vrste,
                    vi.id_vira, vi.ime_vira, vi.url_vira
                FROM oglas o
                JOIN nepremicnina n
                    ON o.id_nepremicnine = n.id_nepremicnine
                JOIN lokacija l
                    ON n.id_lokacije = l.id_lokacije
                JOIN vrsta_nepremicnine v
                    ON n.id_vrste = v.id_vrste
                JOIN vir vi
                    ON o.id_vira = vi.id_vira
            """

            pogoji = []
            vrednosti = []

            if filtri is not None:

                if filtri.id_vrste is not None:
                    pogoji.append("n.id_vrste = %s")
                    vrednosti.append(filtri.id_vrste)

                if filtri.id_lokacije is not None:
                    pogoji.append("n.id_lokacije = %s")
                    vrednosti.append(filtri.id_lokacije)

                if filtri.cena_min is not None:
                    pogoji.append("o.cena >= %s")
                    vrednosti.append(filtri.cena_min)

                if filtri.cena_max is not None:
                    pogoji.append("o.cena <= %s")
                    vrednosti.append(filtri.cena_max)

                if filtri.m2_min is not None:
                    pogoji.append("n.m2 >= %s")
                    vrednosti.append(filtri.m2_min)

                if filtri.m2_max is not None:
                    pogoji.append("n.m2 <= %s")
                    vrednosti.append(filtri.m2_max)

            if pogoji:
                sql += " WHERE " + " AND ".join(pogoji)

            sql += " ORDER BY o.datum_objave DESC"

            cur.execute(sql, vrednosti)
            rows = cur.fetchall()

            result = []

            for r in rows:
                oglas = Oglas(
                    id_oglasa=r["id_oglasa"], naslov=r["naslov"],
                    url_oglasa=r["url_oglasa"], cena=r["cena"],
                    datum_objave=r["datum_objave"], id_vira=r["id_vira"],
                    id_nepremicnine=r["id_nepremicnine"],
                )
                nepremicnina = Nepremicnina(
                    id_nepremicnine=r["id_nepremicnine"], opis=r["opis"],
                    leto_gradnje=r["leto_gradnje"], stevilo_sob=r["stevilo_sob"],
                    nadstropje=r["nadstropje"], m2=r["m2"],
                    id_vrste=r["id_vrste"], id_lokacije=r["id_lokacije"],
                )
                lokacija = Lokacija(
                    id_lokacije=r["id_lokacije"], ime=r["ime"], regija=r["regija"],
                    soseska=r["soseska"], postna_stevilka=r["postna_stevilka"],
                )
                vrsta = Vrsta_nepremicnine(id_vrste=r["id_vrste"], ime_vrste=r["ime_vrste"])
                vir = Vir(id_vira=r["id_vira"], ime_vira=r["ime_vira"], url_vira=r["url_vira"])

                result.append(OglasDTO(oglas=oglas, nepremicnina=nepremicnina,
                                    lokacija=lokacija, vrsta=vrsta, vir=vir))

            return result

    def get_statistics(self, filtri: Optional[OglasFiltriDTO] = None) -> StatisticsDTO:
        """ Vrne osnovne izračune (št. oglasov, povprečna cena, mediana cene, min in max cena) glede na dane filtre."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql = """
                SELECT
                    COUNT(*) AS stevilo_oglasov,

                    AVG(o.cena) AS povprecna_cena,
                    MIN(o.cena) AS minimalna_cena,
                    MAX(o.cena) AS maksimalna_cena,

                    PERCENTILE_CONT(0.5)
                        WITHIN GROUP (ORDER BY o.cena) AS mediana_cena,

                    AVG(n.m2) AS povprecna_m2,
                    SUM(n.m2) AS skupna_povrsina_m2,

                    AVG(o.cena / NULLIF(n.m2, 0)) AS povprecna_cena_na_m2,
                    MIN(o.cena / NULLIF(n.m2, 0)) AS minimalna_cena_na_m2,
                    MAX(o.cena / NULLIF(n.m2, 0)) AS maksimalna_cena_na_m2

                FROM oglas o
                JOIN nepremicnina n
                    ON o.id_nepremicnine = n.id_nepremicnine
            """

            pogoji = []
            vrednosti = []

            if filtri is not None:

                if filtri.id_vrste is not None:
                    pogoji.append("n.id_vrste = %s")
                    vrednosti.append(filtri.id_vrste)

                if filtri.id_lokacije is not None:
                    pogoji.append("n.id_lokacije = %s")
                    vrednosti.append(filtri.id_lokacije)

                if filtri.cena_min is not None:
                    pogoji.append("o.cena >= %s")
                    vrednosti.append(filtri.cena_min)

                if filtri.cena_max is not None:
                    pogoji.append("o.cena <= %s")
                    vrednosti.append(filtri.cena_max)

                if filtri.m2_min is not None:
                    pogoji.append("n.m2 >= %s")
                    vrednosti.append(filtri.m2_min)

                if filtri.m2_max is not None:
                    pogoji.append("n.m2 <= %s")
                    vrednosti.append(filtri.m2_max)

            if pogoji:
                sql += " WHERE " + " AND ".join(pogoji)

            cur.execute(sql, vrednosti)
            row = cur.fetchone()

            return StatisticsDTO(
                stevilo_oglasov=int(row["stevilo_oglasov"] or 0),

                povprecna_cena=float(row["povprecna_cena"] or 0),
                mediana_cena=float(row["mediana_cena"] or 0),
                minimalna_cena=float(row["minimalna_cena"] or 0),
                maksimalna_cena=float(row["maksimalna_cena"] or 0),

                povprecna_m2=float(row["povprecna_m2"] or 0),
                skupna_povrsina_m2=float(row["skupna_povrsina_m2"] or 0),

                povprecna_cena_na_m2=float(row["povprecna_cena_na_m2"] or 0),
                minimalna_cena_na_m2=float(row["minimalna_cena_na_m2"] or 0),
                maksimalna_cena_na_m2=float(row["maksimalna_cena_na_m2"] or 0),
            )



