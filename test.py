from Data.repository import Repository
from Data.models import *

repo = Repository()

# Testi za models, repository in povezavo z bazo

vir = Vir(ime_vira="Nepremicnine.net", url_vira="https://www.nepremicnine.net")
vir = repo.add_vir(vir)
print("INSERT VIR:", vir)
prebran = repo.get_vir_by_id(vir.id_vira)
print("GET VIR:", prebran)

lok = Lokacija(
    ime="Ljubljana",
    regija="Osrednjeslovenska",
    soseska="Center",
    postna_stevilka=1000
)
lok = repo.add_lokacija(lok)
print("INSERT LOKACIJA:", lok)
print("ALL LOKACIJE:", repo.list_lokacije())

vrsta = Vrsta_nepremicnine(ime_vrste="Stanovanje")
print("VRSTE:", repo.list_vrste())

nep = Nepremicnina(
    id_vrste=vrsta.id_vrste,
    id_lokacije=lok.id_lokacije,
    opis="Lepo stanovanje v centru",
    leto_gradnje=2005,
    stevilo_sob=2,
    nadstropje="2",
    m2=55.0
)

nep = repo.add_nepremicnina(nep)

oglas = Oglas(
    id_vira=vir.id_vira,
    id_nepremicnine=nep.id_nepremicnine,
    naslov="Oddaja 2-sobnega stanovanja",
    url_oglasa="https://www.nepremicnine.net",
    cena=900,
    datum_objave=date.today()
    )
oglas = repo.add_oglas(oglas)
print("INSERT OGLAS:", oglas)