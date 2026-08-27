"""
Podatkovni modeli
Vsak razred ustreza eni tabeli v bazi. Razredi s končnico DTO niso tabele,
ampak združujejo podatke iz več tabel skupaj.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

from dataclasses_json import dataclass_json


# 1. VIR

@dataclass_json
@dataclass
class Vir:
    """Portal, s katerega je oglas pobran (nepremicnine.net)"""

    id_vira: Optional[int] = field(default=None)   
    ime_vira: str = field(default="")
    url_vira: Optional[str] = field(default=None)


# 2. VRSTA NEPREMIČNINE

@dataclass_json
@dataclass
class VrstaNepremicnine:
    """Šifrant vrst: Stanovanje, hiša..."""

    id_vrste: Optional[int] = field(default=None)
    ime_vrste: str = field(default="")


# 3. REGIJA

@dataclass_json
@dataclass
class Regija:
    """Regija skupaj z državo ('SI' ali 'HR')."""

    id_regije: Optional[int] = field(default=None)
    ime_regije: str = field(default="")
    drzava: str = field(default="SI")

    def __post_init__(self):
        if self.drzava not in ("SI", "HR"):
            raise ValueError(f"Neveljavna država: {self.drzava!r} (dovoljeno: SI, HR)")

    @property
    def ime_z_drzavo(self) -> str:
        """Za spustne sezname v aplikaciji: 'Ljubljana mesto (SI)'."""
        return f"{self.ime_regije} ({self.drzava})"


# 4. LOKACIJA

@dataclass_json
@dataclass
class Lokacija:
    """Konkretna lokacija: upravna enota + občina + naselje znotraj regije."""

    id_lokacije: Optional[int] = field(default=None)
    id_regije: Optional[int] = field(default=None)
    upravna_enota: Optional[str] = field(default=None)
    obcina: Optional[str] = field(default=None)
    naselje: Optional[str] = field(default=None)
    postna_stevilka: Optional[int] = field(default=None)

    # Ta dva se napolnita samo, kadar lokacijo beremo skupaj z regijo (JOIN).
    ime_regije: Optional[str] = field(default=None)
    drzava: Optional[str] = field(default=None)

    def __post_init__(self):
        if self.postna_stevilka is not None and not (1000 <= self.postna_stevilka <= 99999):
            raise ValueError(f"Neveljavna poštna številka: {self.postna_stevilka}")

    @property
    def prikaz(self) -> str:
        """Berljiv zapis lokacije za prikaz na spletni strani.

        Sestavimo ga iz tistih delov, ki niso prazni, in jih ločimo z vejico:
        npr. 'Brdo, Ljubljana Vič-Rudnik, Ljubljana mesto'.
        """
        deli = [self.naselje, self.obcina, self.ime_regije]
        deli = [d for d in deli if d]           # odstranimo None in prazne nize
        return ", ".join(deli) if deli else "Neznana lokacija"


# 5. NEPREMIČNINA

@dataclass_json
@dataclass
class Nepremicnina:
    """Fizična nepremičnina: kvadratura, sobe, leto gradnje, nadstropje."""

    id_nepremicnine: Optional[int] = field(default=None)
    id_vrste: int = field(default=0)
    id_lokacije: int = field(default=0)

    opis: Optional[str] = field(default=None)
    leto_gradnje: Optional[int] = field(default=None)
    stevilo_sob: Optional[float] = field(default=None)
    stevilo_sob_opis: Optional[str] = field(default=None)
    nadstropje: Optional[str] = field(default=None)
    m2: float = field(default=0.0)

    def __post_init__(self):
        if self.m2 is None or float(self.m2) <= 0:
            raise ValueError("Površina (m2) mora biti večja od 0.")

        if self.stevilo_sob is not None and float(self.stevilo_sob) <= 0:
            raise ValueError("Število sob mora biti večje od 0.")

        if self.leto_gradnje is not None and not (1200 <= int(self.leto_gradnje) <= 2100):
            raise ValueError("Leto gradnje mora biti med 1200 in 2100.")


# 6. OGLAS

@dataclass_json
@dataclass
class Oglas:
    """Objava za najem: naslov, cena, povezava, datum"""

    id_oglasa: Optional[int] = field(default=None)
    id_vira: int = field(default=0)
    id_nepremicnine: int = field(default=0)

    zunanji_id: Optional[str] = field(default=None)  
    naslov: str = field(default="")
    url_oglasa: Optional[str] = field(default=None)
    cena: float = field(default=0.0)
    valuta: str = field(default="EUR")
    datum_objave: Optional[date] = field(default=None)
    datum_zajema: Optional[date] = field(default=None)

    def __post_init__(self):
        if self.cena is None or float(self.cena) < 0:
            raise ValueError("Cena ne sme biti negativna.")
        if not self.naslov or not self.naslov.strip():
            raise ValueError("Naslov oglasa ne sme biti prazen.")


# 7. UPORABNIK

@dataclass_json
@dataclass
class Uporabnik:
    """Uporabnik aplikacije. POZOR: geslo je vedno shranjeno kot bcrypt hash."""

    uporabnisko_ime: str = field(default="")
    geslo_hash: str = field(default="")
    vloga: str = field(default="uporabnik")            # 'admin' ali 'uporabnik'
    zadnja_prijava: Optional[datetime] = field(default=None)

    @property
    def je_admin(self) -> bool:
        return self.vloga == "admin"


# DTO razredi

@dataclass_json
@dataclass
class OglasDTO:
    """En oglas z VSEMI povezanimi podatki (rezultat pogleda oglas_pregled).

    Namesto da bi predlogi HTML podali pet ločenih objektov, ji podamo enega,
    v katerem je vse. V predlogi potem pišemo npr. `oglas.lokacija.prikaz`.
    """

    # Deli so obvezni: OglasDTO brez oglasa ali nepremičnine nima smisla.
    oglas: Oglas
    nepremicnina: Nepremicnina
    lokacija: Lokacija
    vrsta: VrstaNepremicnine
    vir: Vir
    cena_na_m2: Optional[float] = field(default=None)


@dataclass
class OglasFiltriDTO:
    """Vsi filtri, ki jih uporabnik lahko nastavi na strani z oglasi.

    Vsak filter je Optional: None pomeni 'tega filtra ne uporabljaj'.
    Repository iz teh polj sestavi WHERE del poizvedbe.
    """

    iskanje: Optional[str] = field(default=None)        
    id_vrste: Optional[int] = field(default=None)
    id_regije: Optional[int] = field(default=None)
    id_lokacije: Optional[int] = field(default=None)
    drzava: Optional[str] = field(default=None)       
    id_vira: Optional[int] = field(default=None)

    cena_min: Optional[float] = field(default=None)
    cena_max: Optional[float] = field(default=None)
    m2_min: Optional[float] = field(default=None)
    m2_max: Optional[float] = field(default=None)
    sobe_min: Optional[float] = field(default=None)
    leto_min: Optional[int] = field(default=None)

    # Razvrščanje – dovoljene vrednosti preveri Service, ne uporabnik!
    urejanje: str = field(default="cena_asc")

    def je_prazen(self) -> bool:
        """True, če ni nastavljen noben filter (za izpis 'Vsi oglasi')."""
        return all(
            getattr(self, ime) in (None, "")
            for ime in (
                "iskanje", "id_vrste", "id_regije", "id_lokacije", "drzava",
                "id_vira", "cena_min", "cena_max", "m2_min", "m2_max",
                "sobe_min", "leto_min",
            )
        )


@dataclass_json
@dataclass
class StatistikaDTO:
    """Zbirni izračuni nad (filtrirano) množico oglasov."""

    stevilo_oglasov: int = field(default=0)

    povprecna_cena: float = field(default=0.0)
    mediana_cena: float = field(default=0.0)
    minimalna_cena: float = field(default=0.0)
    maksimalna_cena: float = field(default=0.0)

    povprecna_m2: float = field(default=0.0)
    mediana_m2: float = field(default=0.0)
    skupna_povrsina_m2: float = field(default=0.0)

    povprecna_cena_na_m2: float = field(default=0.0)
    minimalna_cena_na_m2: float = field(default=0.0)
    maksimalna_cena_na_m2: float = field(default=0.0)

    povprecno_stevilo_sob: float = field(default=0.0)


@dataclass_json
@dataclass
class VrsticaPoRegijiDTO:
    """Ena vrstica v tabeli 'statistika po regijah'."""

    ime_regije: str = field(default="")
    drzava: str = field(default="SI")
    stevilo_oglasov: int = field(default=0)
    povprecna_cena: float = field(default=0.0)
    mediana_cena: float = field(default=0.0)
    povprecna_m2: float = field(default=0.0)
    povprecna_cena_na_m2: float = field(default=0.0)


@dataclass
class StranDTO:
    """Rezultat ene strani pri paginaciji (stran 1, 2, 3 ...)."""

    oglasi: List[OglasDTO] = field(default_factory=list)
    stran: int = field(default=1)              # trenutna stran
    na_stran: int = field(default=25)          # koliko oglasov na stran
    skupaj: int = field(default=0)             # koliko oglasov ustreza filtru

    @property
    def stevilo_strani(self) -> int:
        """ Zaokrožimo navzgor """
        if self.na_stran <= 0:
            return 1
        return max(1, (self.skupaj + self.na_stran - 1) // self.na_stran)

    @property
    def ima_prejsnjo(self) -> bool:
        return self.stran > 1

    @property
    def ima_naslednjo(self) -> bool:
        return self.stran < self.stevilo_strani
