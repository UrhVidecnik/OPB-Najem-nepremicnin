"""
============================================================================
 OPB – Najem nepremičnin
 Datoteka: Services/service.py

 APLIKACIJSKI NIVO (business logic).

 Vmesni sloj med spletno aplikacijo (app.py) in bazo (Data/repository.py).

 Naloge tega nivoja:
   - PREVERI vhodne podatke, preden gredo v bazo (validacija);
   - PRETVORI podatke iz spletnega obrazca (vse je niz!) v prave tipe;
   - združi več klicev repozitorija v eno smiselno operacijo
     (npr. "dodaj oglas" = ustvari lokacijo + nepremičnino + oglas).

 Pravilo: app.py NE kliče Repository neposredno, vedno gre prek Service.
============================================================================
"""

from typing import List, Optional

from Data.models import (
    Lokacija,
    Nepremicnina,
    Oglas,
    OglasDTO,
    OglasFiltriDTO,
    Regija,
    StatistikaDTO,
    StranDTO,
    Vir,
    VrsticaPoRegijiDTO,
    VrstaNepremicnine,
)
from Data.repository import UREJANJA, Repository

# Koliko oglasov prikažemo na eni strani.
PRIVZETO_NA_STRAN = 25
NAJVEC_NA_STRAN = 100


class Service:
    """Poslovna logika aplikacije."""

    def __init__(self, repository: Optional[Repository] = None):
        # Repozitorij lahko podamo od zunaj (uporabno pri testiranju,
        # kjer podtaknemo lažni repozitorij); sicer si ga ustvarimo sami.
        self.repository = repository or Repository()

    # ── Pretvorbe iz spletnega obrazca ──────────────────────────────────────
    #
    # Iz HTML obrazca vedno pride NIZ. Prazno polje je prazen niz "".
    # Te tri metode niz varno pretvorijo v število ali None.

    @staticmethod
    def v_int(vrednost) -> Optional[int]:
        """'42' -> 42, '' -> None, 'abc' -> None (brez sesutja)."""
        if vrednost is None or str(vrednost).strip() == "":
            return None
        try:
            return int(str(vrednost).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def v_float(vrednost) -> Optional[float]:
        """'1200,50' ali '1200.50' -> 1200.5, '' -> None."""
        if vrednost is None or str(vrednost).strip() == "":
            return None
        try:
            return float(str(vrednost).strip().replace(",", "."))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def v_besedilo(vrednost) -> Optional[str]:
        """Obreže presledke; prazen niz postane None."""
        if vrednost is None:
            return None
        v = str(vrednost).strip()
        return v if v else None

    # ── Sestavljanje filtrov ────────────────────────────────────────────────

    def sestavi_filtre(self, obrazec) -> OglasFiltriDTO:
        """Iz parametrov URL-ja/obrazca sestavi OglasFiltriDTO.

        `obrazec` je bottle-ov request.query ali request.forms –
        obnaša se kot slovar, zato uporabimo .get().
        """
        drzava = self.v_besedilo(obrazec.get("drzava"))
        if drzava not in (None, "SI", "HR"):
            drzava = None      # neveljavno vrednost tiho ignoriramo

        urejanje = self.v_besedilo(obrazec.get("urejanje")) or "cena_asc"
        if urejanje not in UREJANJA:
            urejanje = "cena_asc"

        filtri = OglasFiltriDTO(
            iskanje=self.v_besedilo(obrazec.get("q")),
            id_vrste=self.v_int(obrazec.get("id_vrste")),
            id_regije=self.v_int(obrazec.get("id_regije")),
            id_lokacije=self.v_int(obrazec.get("id_lokacije")),
            drzava=drzava,
            id_vira=self.v_int(obrazec.get("id_vira")),
            cena_min=self.v_float(obrazec.get("cena_min")),
            cena_max=self.v_float(obrazec.get("cena_max")),
            m2_min=self.v_float(obrazec.get("m2_min")),
            m2_max=self.v_float(obrazec.get("m2_max")),
            sobe_min=self.v_float(obrazec.get("sobe_min")),
            leto_min=self.v_int(obrazec.get("leto_min")),
            urejanje=urejanje,
        )
        self.preveri_filtre(filtri)
        return filtri

    def preveri_filtre(self, filtri: Optional[OglasFiltriDTO]) -> None:
        """Zavrne nesmiselne filtre (npr. min > max).

        Namesto da bi vrgli napako in podrli stran, tu vrednosti
        raje POPRAVIMO – uporabnik dobi rezultate, ne pa napake 500.
        """
        if filtri is None:
            return

        # Negativne vrednosti nimajo smisla -> jih odstranimo.
        for ime in ("cena_min", "cena_max", "m2_min", "m2_max", "sobe_min"):
            vrednost = getattr(filtri, ime)
            if vrednost is not None and vrednost < 0:
                setattr(filtri, ime, None)

        # Če je uporabnik zamenjal min in max, ju zamenjamo nazaj.
        if (filtri.cena_min is not None and filtri.cena_max is not None
                and filtri.cena_min > filtri.cena_max):
            filtri.cena_min, filtri.cena_max = filtri.cena_max, filtri.cena_min

        if (filtri.m2_min is not None and filtri.m2_max is not None
                and filtri.m2_min > filtri.m2_max):
            filtri.m2_min, filtri.m2_max = filtri.m2_max, filtri.m2_min

        if filtri.leto_min is not None and not (1200 <= filtri.leto_min <= 2100):
            filtri.leto_min = None

    # ── Branje oglasov ──────────────────────────────────────────────────────

    def stran_oglasov(
        self,
        filtri: Optional[OglasFiltriDTO] = None,
        stran: int = 1,
        na_stran: int = PRIVZETO_NA_STRAN,
    ) -> StranDTO:
        """Ena stran (filtriranih) oglasov."""
        self.preveri_filtre(filtri)
        stran = max(1, stran or 1)
        na_stran = max(1, min(na_stran or PRIVZETO_NA_STRAN, NAJVEC_NA_STRAN))
        return self.repository.stran_oglasov(filtri, stran=stran, na_stran=na_stran)

    def dobi_oglas(self, id_oglasa: int) -> Optional[OglasDTO]:
        if id_oglasa is None:
            raise ValueError("ID oglasa je obvezen.")
        return self.repository.dobi_oglas(id_oglasa)

    def prestej_oglase(self, filtri: Optional[OglasFiltriDTO] = None) -> int:
        self.preveri_filtre(filtri)
        return self.repository.prestej_oglase(filtri)

    # ── Statistika ──────────────────────────────────────────────────────────

    def statistika(self, filtri: Optional[OglasFiltriDTO] = None) -> StatistikaDTO:
        self.preveri_filtre(filtri)
        return self.repository.statistika(filtri)

    def statistika_po_regijah(
        self, filtri: Optional[OglasFiltriDTO] = None, min_oglasov: int = 5
    ) -> List[VrsticaPoRegijiDTO]:
        self.preveri_filtre(filtri)
        return self.repository.statistika_po_regijah(filtri, min_oglasov=min_oglasov)

    def statistika_po_vrstah(self, filtri: Optional[OglasFiltriDTO] = None) -> List[dict]:
        self.preveri_filtre(filtri)
        return self.repository.statistika_po_vrstah(filtri)

    def porazdelitev_cen(
        self, filtri: Optional[OglasFiltriDTO] = None, sirina_razreda: int = 250
    ) -> List[dict]:
        """Podatki za stolpčni diagram cen. Širino razreda omejimo na razumno."""
        self.preveri_filtre(filtri)
        sirina_razreda = max(50, min(int(sirina_razreda), 2000))
        return self.repository.porazdelitev_cen(filtri, sirina_razreda)

    def najdrazji_najcenejsi(self, koliko: int = 5) -> dict:
        return self.repository.najdrazji_najcenejsi(max(1, min(koliko, 20)))

    # ── Šifranti (spustni seznami v obrazcih) ───────────────────────────────

    def vrste(self) -> List[VrstaNepremicnine]:
        return self.repository.seznam_vrst()

    def regije(self, drzava: Optional[str] = None) -> List[Regija]:
        if drzava not in (None, "SI", "HR"):
            drzava = None
        return self.repository.seznam_regij(drzava)

    def lokacije(self, id_regije: Optional[int] = None) -> List[Lokacija]:
        return self.repository.seznam_lokacij(id_regije)

    def viri(self) -> List[Vir]:
        return self.repository.seznam_virov()

    # ── Pisanje: dodajanje in urejanje oglasov ──────────────────────────────

    def dodaj_oglas(
        self,
        naslov: str,
        cena: float,
        m2: float,
        id_vrste: int,
        id_vira: int,
        id_regije: Optional[int] = None,
        obcina: Optional[str] = None,
        naselje: Optional[str] = None,
        upravna_enota: Optional[str] = None,
        url_oglasa: Optional[str] = None,
        opis: Optional[str] = None,
        leto_gradnje: Optional[int] = None,
        stevilo_sob: Optional[float] = None,
        stevilo_sob_opis: Optional[str] = None,
        nadstropje: Optional[str] = None,
    ) -> OglasDTO:
        """Doda nov oglas – skupaj z nepremičnino in po potrebi novo lokacijo.

        Vrne cel OglasDTO, da ga lahko takoj prikažemo uporabniku.
        Če karkoli ni v redu, vrže ValueError s SLOVENSKIM sporočilom,
        ki ga app.py prikaže nad obrazcem.
        """
        # --- validacija ---
        naslov = self.v_besedilo(naslov)
        if not naslov:
            raise ValueError("Naslov oglasa je obvezen.")
        if len(naslov) > 300:
            raise ValueError("Naslov je predolg (največ 300 znakov).")

        if cena is None:
            raise ValueError("Cena je obvezna.")
        if cena < 0:
            raise ValueError("Cena ne sme biti negativna.")
        if cena > 1_000_000:
            raise ValueError("Cena je nerealno visoka.")

        if m2 is None or m2 <= 0:
            raise ValueError("Površina mora biti večja od 0.")
        if m2 > 10_000:
            raise ValueError("Površina je nerealno velika.")

        if id_vrste is None:
            raise ValueError("Izbrati moraš vrsto nepremičnine.")
        if id_vira is None:
            raise ValueError("Izbrati moraš vir oglasa.")

        if leto_gradnje is not None and not (1200 <= leto_gradnje <= 2100):
            raise ValueError("Leto gradnje mora biti med 1200 in 2100.")

        if stevilo_sob is not None and stevilo_sob <= 0:
            raise ValueError("Število sob mora biti večje od 0.")

        if self.repository.dobi_vir(id_vira) is None:
            raise ValueError(f"Vir z ID {id_vira} ne obstaja.")

        # --- lokacija: poiščemo obstoječo ali ustvarimo novo ---
        lokacija = self.repository.dobi_ali_dodaj_lokacijo(
            id_regije=id_regije,
            upravna_enota=self.v_besedilo(upravna_enota),
            obcina=self.v_besedilo(obcina),
            naselje=self.v_besedilo(naselje),
        )

        # --- nepremičnina ---
        nepremicnina = self.repository.dodaj_nepremicnino(Nepremicnina(
            id_vrste=id_vrste,
            id_lokacije=lokacija.id_lokacije,
            opis=self.v_besedilo(opis),
            leto_gradnje=leto_gradnje,
            stevilo_sob=stevilo_sob,
            stevilo_sob_opis=self.v_besedilo(stevilo_sob_opis),
            nadstropje=self.v_besedilo(nadstropje),
            m2=m2,
        ))

        # --- oglas ---
        oglas = self.repository.dodaj_oglas(Oglas(
            id_vira=id_vira,
            id_nepremicnine=nepremicnina.id_nepremicnine,
            naslov=naslov,
            url_oglasa=self.v_besedilo(url_oglasa),
            cena=cena,
        ))

        # Preberemo ga nazaj iz baze, da dobimo tudi izračunane stolpce
        # (cena_na_m2, ime regije ...) – enako, kot bi ga videli v seznamu.
        return self.repository.dobi_oglas(oglas.id_oglasa)

    def posodobi_oglas(
        self,
        id_oglasa: int,
        naslov: str,
        cena: float,
        m2: float,
        leto_gradnje: Optional[int] = None,
        stevilo_sob: Optional[float] = None,
        nadstropje: Optional[str] = None,
        opis: Optional[str] = None,
        url_oglasa: Optional[str] = None,
    ) -> OglasDTO:
        """Posodobi obstoječi oglas in njegovo nepremičnino."""
        obstojeci = self.repository.dobi_oglas(id_oglasa)
        if obstojeci is None:
            raise ValueError(f"Oglas z ID {id_oglasa} ne obstaja.")

        naslov = self.v_besedilo(naslov)
        if not naslov:
            raise ValueError("Naslov oglasa je obvezen.")
        if cena is None or cena < 0:
            raise ValueError("Cena mora biti nenegativno število.")
        if m2 is None or m2 <= 0:
            raise ValueError("Površina mora biti večja od 0.")
        if leto_gradnje is not None and not (1200 <= leto_gradnje <= 2100):
            raise ValueError("Leto gradnje mora biti med 1200 in 2100.")
        if stevilo_sob is not None and stevilo_sob <= 0:
            raise ValueError("Število sob mora biti večje od 0.")

        # Nepremičnina: spremenimo samo tisto, kar obrazec ureja.
        n = obstojeci.nepremicnina
        n.m2 = m2
        n.leto_gradnje = leto_gradnje
        n.stevilo_sob = stevilo_sob
        n.nadstropje = self.v_besedilo(nadstropje)
        n.opis = self.v_besedilo(opis)
        self.repository.posodobi_nepremicnino(n)

        o = obstojeci.oglas
        o.naslov = naslov
        o.cena = cena
        o.url_oglasa = self.v_besedilo(url_oglasa)
        self.repository.posodobi_oglas(o)

        return self.repository.dobi_oglas(id_oglasa)

    def izbrisi_oglas(self, id_oglasa: int) -> bool:
        if id_oglasa is None:
            raise ValueError("ID oglasa je obvezen.")
        return self.repository.izbrisi_oglas(id_oglasa)

    # ── Šifranti: dodajanje ─────────────────────────────────────────────────

    def dodaj_vir(self, ime_vira: str, url_vira: Optional[str] = None) -> Vir:
        ime_vira = self.v_besedilo(ime_vira)
        if not ime_vira:
            raise ValueError("Ime vira ne sme biti prazno.")
        return self.repository.dobi_ali_dodaj_vir(ime_vira, self.v_besedilo(url_vira))

    def dodaj_vrsto(self, ime_vrste: str) -> VrstaNepremicnine:
        ime_vrste = self.v_besedilo(ime_vrste)
        if not ime_vrste:
            raise ValueError("Ime vrste ne sme biti prazno.")
        return self.repository.dobi_ali_dodaj_vrsto(ime_vrste)

    def dodaj_regijo(self, ime_regije: str, drzava: str = "SI") -> Regija:
        ime_regije = self.v_besedilo(ime_regije)
        if not ime_regije:
            raise ValueError("Ime regije ne sme biti prazno.")
        if drzava not in ("SI", "HR"):
            raise ValueError("Država mora biti 'SI' ali 'HR'.")
        return self.repository.dobi_ali_dodaj_regijo(ime_regije, drzava)
