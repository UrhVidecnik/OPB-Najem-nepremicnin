from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from typing import Optional
from datetime import date

# Definiramo podatokvne modele, ki jih bomo uporabljali

@dataclass_json
@dataclass

class Vir:
    id_vira: Optional[int] = field(default=None)
    ime_vira: str = field(default="")
    url_vira: Optional[str] = field(default=None)



@dataclass_json
@dataclass
class Vrsta_nepremicnine:
    id_vrste: Optional[int] = field(default=None)
    ime_vrste: str = field(default="")



@dataclass_json
@dataclass
class Lokacija:
    id_lokacije: Optional[int] = field(default=None)
    ime: str = field(default="")
    regija: Optional[str] = field(default=None)
    soseska: Optional[str] = field(default=None)
    postna_stevilka: Optional[int] = field(default=None)



@dataclass_json
@dataclass
class Nepremicnina:
    id_nepremicnine: Optional[int] = field(default=None)
    id_vrste: int = field(default=0)
    id_lokacije: int = field(default=0)

    opis: Optional[str] = field(default=None)
    leto_gradnje: Optional[int] = field(default=None)
    stevilo_sob: Optional[float] = field(default=None)
    nadstropje: Optional[str] = field(default=None)
    m2: float = field(default=0.0)

    def __post_init__(self):
        if self.m2 <= 0:
            raise ValueError("m2 mora biti > 0")

        if self.leto_gradnje is not None:
            if not (1800 <= self.leto_gradnje <= 2100):
                raise ValueError("Leto_gradnje mora biti med 1800 in 2100")

        if self.stevilo_sob is not None and self.stevilo_sob <= 0:
            raise ValueError("Število_sob mora biti > 0")



@dataclass_json
@dataclass
class Oglas:
    id_oglasa: Optional[int] = field(default=None)
    id_vira: int = field(default=0)
    id_nepremicnine: int = field(default=0)

    naslov: str = field(default="")
    url_oglasa: Optional[str] = field(default=None)
    cena: float = field(default=0.0)
    datum_objave: Optional[date] = field(default=None)

    def __post_init__(self):
        if self.cena < 0:
            raise ValueError("Cena ne sme biti negativna")



@dataclass_json
@dataclass
class OglasDTO:
    oglas: Oglas = field(default_factory=Oglas)
    nepremicnina: Nepremicnina = field(default_factory=Nepremicnina)
    lokacija: Lokacija = field(default_factory=Lokacija)
    vrsta: Vrsta_nepremicnine = field(default_factory=Vrsta_nepremicnine)
    vir: Vir = field(default_factory=Vir)


@dataclass
class OglasFiltri:
    id_vrste: Optional[int] = field(default=None)
    id_lokacije: Optional[int] = field(default=None)
    cena_min: Optional[float] = field(default=None)
    cena_max: Optional[float] = field(default=None)
    m2_min: Optional[float] = field(default=None)
    m2_max: Optional[float] = field(default=None)
