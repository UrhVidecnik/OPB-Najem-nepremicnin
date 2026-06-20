from typing import Optional, List

from Data.repository import Repository
from Data.models import Vir, Vrsta_nepremicnine, Lokacija, Nepremicnina, Oglas, OglasDTO, OglasFiltriDTO, StatisticsDTO

class Service:
    def __init__(self, repository: Optional[Repository] = None):
        self.repository = repository or Repository()

    def get_oglasi(self, filtri: Optional[OglasFiltriDTO] = None) -> List[OglasDTO]:
        self._preveri_filtre(filtri)
        return self.repository.get_oglasi_dto(filtri)
    
    def get_statistics(self, filtri: Optional[OglasFiltriDTO] = None) -> StatisticsDTO:
        self._preveri_filtre(filtri)
        return self.repository.get_statistics(filtri)
    
    def _preveri_filtre(self, filtri: Optional[OglasFiltriDTO]) -> None:
        if filtri is None:
            return

        if filtri.cena_min is not None and filtri.cena_min < 0:
            raise ValueError("Minimalna cena ne sme biti negativna")

        if filtri.cena_max is not None and filtri.cena_max < 0:
            raise ValueError("Maksimalna cena ne sme biti negativna")

        if (
            filtri.cena_min is not None
            and filtri.cena_max is not None
            and filtri.cena_min > filtri.cena_max
        ):
            raise ValueError("Minimalna cena ne sme biti večja od maksimalne.")

        if filtri.m2_min is not None and filtri.m2_min < 0:
            raise ValueError("Minimalna površina ne sme biti negativna")

        if filtri.m2_max is not None and filtri.m2_max < 0:
            raise ValueError("Maksimalna površina ne sme biti negativna")
        
        if (
            filtri.m2_min is not None
            and filtri.m2_max is not None
            and filtri.m2_min > filtri.m2_max
        ):
            raise ValueError("Minimalna površina ne sme biti večja od maksimalne.")

    
    def dodaj_oglas(
        self,
        id_vira: int,
        id_vrste: int,
        id_lokacije: int,
        naslov: str,
        cena: float,
        m2: float,
        url_oglasa: Optional[str] = None,
        datum_objave: Optional[date] = None,
        opis: Optional[str] = None,
        leto_gradnje: Optional[int] = None,
        stevilo_sob: Optional[float] = None,
        nadstropje: Optional[str] = None,
    ) -> OglasDTO:
        """
        Doda nov oglas v bazo skupaj s pripadajočo nepremičnino.
 
        Vrne celoten OglasDTO, pripravljen za takojšen prikaz uporabniku.
        """
        if not naslov or not naslov.strip():
            raise ValueError("Naslov oglasa ne sme biti prazen")
 
        vir = self.repository.get_vir_by_id(id_vira)
        if vir is None:
            raise ValueError(f"Vir z id_vira={id_vira} ne obstaja")
 
        url_oglasa = url_oglasa.strip() if url_oglasa else None
        opis = opis.strip() if opis else None
        nadstropje = nadstropje.strip() if nadstropje else None
 
        nepremicnina = Nepremicnina(
            id_vrste=id_vrste,
            id_lokacije=id_lokacije,
            opis=opis,
            leto_gradnje=leto_gradnje,
            stevilo_sob=stevilo_sob,
            nadstropje=nadstropje,
            m2=m2,
        )
        nepremicnina = self.repository.add_nepremicnina(nepremicnina)
 
        oglas = Oglas(
            id_vira=id_vira,
            id_nepremicnine=nepremicnina.id_nepremicnine,
            naslov=naslov,
            url_oglasa=url_oglasa,
            cena=cena,
            datum_objave=datum_objave,
        )
        oglas = self.repository.add_oglas(oglas)
 
        vrsta = self._najdi_vrsto(id_vrste)
        lokacija = self._najdi_lokacijo(id_lokacije)

        return OglasDTO(
            oglas=oglas,
            nepremicnina=nepremicnina,
            lokacija=lokacija,
            vrsta=vrsta,
            vir=vir,
        )
    
    def _najdi_vrsto(self, id_vrste: int):
        return next((v for v in self.repository.list_vrste() if v.id_vrste == id_vrste), None)
 
    def _najdi_lokacijo(self, id_lokacije: int):
        return next((l for l in self.repository.list_lokacije() if l.id_lokacije == id_lokacije), None)

    def get_viri(self) -> List[Vir]:
        """Vrne seznam vseh virov (npr. za spustni seznam pri filtriranju oglasov)."""
        return self.repository.list_viri()
 
    def get_vir(self, id_vira: int) -> Optional[Vir]:
        if id_vira is None:
            raise ValueError("id_vira je obvezen podatek")
        return self.repository.get_vir_by_id(id_vira)
 
    def dodaj_vir(self, ime_vira: str, url_vira: Optional[str] = None) -> Vir:
        """Doda nov vir oglasov v bazo (npr. nepremicnine.net, bolha.com ...)."""
        ime_vira = ime_vira.strip() if ime_vira else None
        if not ime_vira:
            raise ValueError("Ime vira ne sme biti prazno")
 
        vir = Vir(ime_vira=ime_vira, url_vira=url_vira.strip() if url_vira else None)
        return self.repository.add_vir(vir)
 
    def get_vrste(self) -> List[Vrsta_nepremicnine]:
        """Vrne seznam vseh vrst nepremičnin (npr. za spustni seznam pri filtriranju oglasov)."""
        return self.repository.list_vrste()
 
    def get_lokacije(self) -> List[Lokacija]:
        """Vrne seznam vseh lokacij (npr. za spustni seznam pri filtriranju oglasov)."""
        return self.repository.list_lokacije()
 
    def dodaj_lokacijo(
        self,
        ime: str,
        regija: Optional[str] = None,
        soseska: Optional[str] = None,
        postna_stevilka: Optional[int] = None,
    ) -> Lokacija:
        """Doda novo lokacijo v bazo."""
        ime = ime.strip() if ime else None
        if not ime:
            raise ValueError("Ime lokacije ne sme biti prazno")
 
        if postna_stevilka is not None and not (1000 <= postna_stevilka <= 9999):
            raise ValueError("Poštna številka mora biti štirimestno število (1000-9999)")
 
        lokacija = Lokacija(
            ime=ime,
            regija=regija.strip() if regija else None,
            soseska=soseska.strip() if soseska else None,
            postna_stevilka=postna_stevilka,
        )
        return self.repository.add_lokacija(lokacija)

