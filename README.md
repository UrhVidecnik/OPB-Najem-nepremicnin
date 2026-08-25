# Najem nepremičnin

Projektna naloga pri predmetu **Osnove podatkovnih baz** (FMF, 3. letnik).

**Avtorja:** Jure Kraševec in Urh Videčnik

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/UrhVidecnik/OPB-Najem-nepremicnin/main?urlpath=proxy/8080)

---

## Opis projekta

Spletna aplikacija za pregled ponudbe **najema nepremičnin** v Sloveniji in na
Hrvaškem. Podatki so avtomatsko pobrani s portala
[nepremicnine.net](https://www.nepremicnine.net), shranjeni v relacijsko bazo
PostgreSQL na strežniku FMF, aplikacija pa nad njimi omogoča iskanje,
filtriranje in statistično analizo.

### Kaj aplikacija omogoča

* **Brskanje po oglasih** – iskanje po ključni besedi (naslov, opis, kraj) in
  filtriranje po vrsti nepremičnine, državi, regiji, ceni, površini, številu sob
  in letu gradnje.
* **Razvrščanje in ostranjevanje** – po ceni, površini, ceni na m², letu
  gradnje ali naslovu; rezultati so razdeljeni na strani.
* **Podrobnosti oglasa** – vse lastnosti nepremičnine, izračunana cena na m²,
  povezava do izvirnega oglasa in seznam podobnih oglasov v isti regiji.
* **Statistika** – povprečje, mediana, minimum in maksimum najemnin, histogram
  porazdelitve cen ter primerjalne razpredelnice po regijah in vrstah
  nepremičnin. Vsi izračuni se izvedejo v bazi z agregatnimi funkcijami SQL.
* **Dodajanje oglasov** – za vsakega prijavljenega uporabnika.
* **Urejanje in brisanje oglasov** – samo za uporabnike z vlogo `admin`.
* **Registracija in prijava** – gesla so shranjena zgoščeno (bcrypt),
  seja teče prek podpisanih piškotkov.

---

## ER-diagram

![ER diagram podatkovne baze](er-nepremicnine.png)

Baza ima **sedem tabel** in en pogled:

| Tabela | Pomen |
|---|---|
| `vir` | portal, s katerega je oglas pobran |
| `vrsta_nepremicnine` | šifrant: Stanovanje, Hiša, … |
| `regija` | regija in država (`SI` / `HR`) |
| `lokacija` | upravna enota + občina + naselje znotraj regije |
| `nepremicnina` | fizična nepremičnina: m², sobe, leto gradnje, nadstropje |
| `oglas` | objava za najem: naslov, cena, povezava, datum |
| `uporabnik` | uporabniki aplikacije (bcrypt gesla, vlogi `admin` / `uporabnik`) |
| `oglas_pregled` *(pogled)* | vsi podatki o oglasu na enem mestu + izračunana cena na m² |

**Dve odločitvi, ki sta vredni omembe:**

* Regija je ločena od lokacije, ker se v podatkih ponovi na stotine krat;
  država je lastnost regije, saj vsaka regija pripada natanko eni državi.
* `oglas.zunanji_id` hrani ID oglasa na portalu, omejitev
  `UNIQUE (id_vira, zunanji_id)` pa naredi uvoz **idempotenten** – skripto za
  uvoz lahko poženeš večkrat, oglasi se ne bodo podvojili.

---

## Struktura projekta

```
OPB-Najem-nepremicnin/
├── app.py                     Spletna aplikacija (poti / routes)
├── init_db.py                 Ustvari shemo baze in podeli pravice
├── podeli_pravice.py          Osveži pravice, ne da bi pobrisal podatke
├── preveri_dostop.py          Preveri, ali javni dostop deluje in kaj sme
├── nastavi_admina.py          Dodeli ali odvzame vlogo 'admin'
├── testi.py                   35 testov vseh treh nivojev
├── requirements.txt           Knjižnice za aplikacijo
├── er-nepremicnine.png        ER diagram
├── PREDSTAVITEV.md            Scenarij za zagovor projekta
│
├── Data/                      PODATKOVNI NIVO
│   ├── create_database.sql      shema: tabele, indeksi, pogled
│   ├── pravice.sql              GRANT ukazi (jurekr, javnost)
│   ├── prikaz_baze.sql          14 poizvedb za predstavitev
│   ├── er_diagram.dot           izvorna koda ER diagrama (Graphviz)
│   ├── models.py                podatkovni modeli (dataclass)
│   ├── repository.py            vse SQL poizvedbe
│   ├── nalozi_v_bazo.py         uvoz CSV → baza
│   ├── auth_public.py           javni bralni dostop (v gitu)
│   └── auth.py                  osebni dostop s pisanjem (NI v gitu)
│
├── Services/                  APLIKACIJSKI NIVO
│   ├── service.py               poslovna logika in validacija
│   └── auth_service.py          prijava, registracija, bcrypt
│
├── Presentation/              PREDSTAVITVENI NIVO
│   ├── bottleext.py             nadgradnja Bottle (url(), TEMPLATE_PATH)
│   ├── static/style.css         slog
│   └── views/                   predloge HTML
│
├── Scrape Data/               ZAJEM PODATKOV
│   ├── scrape_all_data.py       scraper (Playwright + BeautifulSoup)
│   ├── oglasi_full.csv          združeni pobrani podatki
│   ├── oglasi_osnovno.csv       podatki s seznamov oglasov
│   └── oglasi_lokacije.csv      podatki z detajlnih strani
│
└── binder/                    Zagon v oblaku (mybinder.org)
```

Aplikacija je razdeljena na **tri nivoje**. Vsak nivo govori samo s tistim
pod sabo:

```
app.py  →  Services/  →  Data/repository.py  →  PostgreSQL
```

`app.py` nikoli ne piše SQL, `Services` se nikoli ne pogovarja z bazo
neposredno. Če se shema baze spremeni, popravimo samo `repository.py`.

---

## Namestitev in zagon

### 1. Kloniranje

```bash
git clone https://github.com/UrhVidecnik/OPB-Najem-nepremicnin.git
cd OPB-Najem-nepremicnin
```

Vse nadaljnje ukaze poganjaj **iz korenske mape projekta**.

### 2. Virtualno okolje

```bash
python3 -m venv env
```

Aktivacija:

```bash
source env/bin/activate          # macOS / Linux
env\Scripts\activate             # Windows
```

Ko je okolje aktivno, se na začetku vrstice v terminalu pojavi `(env)`.

> **VS Code:** virtualno okolje je treba izbrati še kot interpreter –
> klikni na verzijo Pythona v spodnjem desnem kotu in izberi
> `Python ('env': venv)`.

### 3. Namestitev knjižnic

```bash
pip install -r requirements.txt
```

### 4. Povezava z bazo

Aplikacija se privzeto poveže kot uporabnik `javnost` (geslo je zapisano
v `Data/auth_public.py`, ker ni tajno). Ta uporabnik sme podatke **brati in
dodajati**, ne sme pa jih **spreminjati ali brisati** – za zagon aplikacije
torej ni treba nastaviti ničesar.

Za **urejanje in brisanje oglasov** ter za pripravo baze (ustvarjanje tabel,
uvoz podatkov) potrebuješ osebni dostop. Skopiraj `Data/auth_public.py` v
`Data/auth.py` in vpiši svoje podatke:

```bash
cp Data/auth_public.py Data/auth.py     # macOS / Linux
copy Data\auth_public.py Data\auth.py   # Windows
```

```python
db = "sem2026_urhvid"
host = "baza.fmf.uni-lj.si"
user = "tvoje_uporabnisko_ime"
password = "tvoje_geslo"
port = 5432
```

`Data/auth.py` je v `.gitignore`, zato ne bo nikoli romala na GitHub.

### 5. Zagon

```bash
python app.py
```

Odpri <http://localhost:8080>. Aplikacijo ustaviš s `Ctrl+C`.

---

## Uporabniki in vloge

V aplikaciji sta dve vlogi:

| Dejanje | neprijavljen | `uporabnik` | `admin` |
|---|:--:|:--:|:--:|
| Brskanje, iskanje, filtri, statistika | ✔ | ✔ | ✔ |
| Registracija in prijava | ✔ | – | – |
| **Dodajanje** oglasov | ✘ | ✔ | ✔ |
| **Urejanje** oglasov | ✘ | ✘ | ✔ |
| **Brisanje** oglasov | ✘ | ✘ | ✔ |

Vsak, ki se registrira, dobi vlogo `uporabnik`. Vloge namenoma **ni mogoče
spremeniti prek spletnega vmesnika** – če bi obstajala stran "postani admin",
bi jo lahko odprl vsakdo. Skrbnika zato določi lastnik baze iz ukazne vrstice:

```bash
python nastavi_admina.py --seznam            # kdo je v bazi in kakšno vlogo ima
python nastavi_admina.py urh                 # obstoječega uporabnika naredi za admina
python nastavi_admina.py jure --geslo TAJNO  # uporabnika ustvari IN naredi za admina
python nastavi_admina.py jure --odvzemi      # skrbniške pravice odvzame
```

Sprememba začne veljati ob naslednji prijavi.

### Kako je dostop zares zavarovan

Zaščita je na treh nivojih – vsak sam zase ne bi zadostoval:

1. **Predloge HTML** skrijejo gumbe, ki jih uporabnik ne sme uporabiti.
   To je zgolj udobje: skrit gumb ni zaščita, saj lahko kdorkoli naslov
   `/uredi/123` vtipka neposredno v brskalnik.
2. **Dekoratorji v `app.py`** (`zahtevaj_prijavo`, `zahtevaj_admina`) dostop
   zares preprečijo in vrnejo odgovor 403. Vlogo pri tem **preberejo iz baze**,
   ne iz piškotka. Piškotka sta poleg tega **podpisana** (glej
   `Presentation/bottleext.py`), zato si uporabnik ne more sam nastaviti
   `vloga=admin` – spremenjen piškotek ne prestane preverjanja podpisa.
3. **Pravice v PostgreSQL** (`Data/pravice.sql`) so zadnja obramba: uporabnik
   `javnost` nima pravic `UPDATE` in `DELETE` nad oglasi, zato jih ne more
   spremeniti niti, če bi se na bazo povezal mimo aplikacije.

Pravice preveriš in po potrebi osvežiš z:

```bash
python preveri_dostop.py    # ali se da povezati kot 'javnost' in kaj sme
python podeli_pravice.py    # znova izvede Data/pravice.sql (podatkov ne briše)
```

`preveri_dostop.py` v bazo ničesar ne zapiše – pravice prebere s funkcijo
`has_table_privilege()`.

---

## Priprava baze od začetka

Te korake potrebuješ samo ob prvi postavitvi ali ob spremembi sheme.
Za oba je potrebna `Data/auth.py` s pravico pisanja.

```bash
# 1) Ustvari tabele, indekse, pogled in podeli pravice
#    POZOR: pobriše obstoječe tabele – skripta te vpraša za potrditev.
python init_db.py

# 2) Uvozi pobrane oglase iz CSV v bazo
python -m Data.nalozi_v_bazo
```

Uporabne možnosti uvoza:

```bash
python -m Data.nalozi_v_bazo --suho              # samo preveri, nič ne zapiše
python -m Data.nalozi_v_bazo --omejitev 100      # uvozi samo prvih 100 vrstic
python -m Data.nalozi_v_bazo --datoteka pot.csv  # druga vhodna datoteka
```

Uvoz na koncu izpiše poročilo: koliko oglasov je bilo vstavljenih, koliko
preskočenih (ker so že v bazi) in koliko zavrnjenih zaradi neveljavnih
podatkov – skupaj s konkretnimi primeri.

---

## Testi

```bash
python testi.py
```

Testi pokrivajo modele, validacijo v aplikacijskem nivoju, poizvedbe,
filtriranje, ostranjevanje, statistiko, prijavo in idempotentnost uvoza.
Testi, ki pišejo v bazo, se samodejno preskočijo, če si povezan kot `javnost`.
Testni podatki se na koncu pobrišejo.

---

## Ponovno pobiranje podatkov

Scraper je ločen od aplikacije in ga za običajno uporabo ni treba poganjati –
pobrani podatki so že v `Scrape Data/oglasi_full.csv`.

```bash
pip install -r "Scrape Data/requirements.txt"
playwright install firefox

cd "Scrape Data"
cp .env.example .env        # vpiši SEARCH_URLS in ostale nastavitve
python scrape_all_data.py
```

Scraper dela v dveh korakih: najprej prebere strani s seznami oglasov
(`oglasi_osnovno.csv`), nato še detajlne strani posameznih oglasov
(`oglasi_lokacije.csv`, od koder dobimo hierarhijo regija → upravna enota →
občina → naselje), na koncu pa oboje združi v `oglasi_full.csv`.

Uporablja Playwright s **Firefoxom** brez okna, ker portal blokira zahtevke
navadnih knjižnic in brskalnikov na osnovi Chromiuma.

---

## Poizvedbe za predstavitev

V `Data/prikaz_baze.sql` je 14 pripravljenih poizvedb – od preprostega
štetja vrstic do okenskih funkcij in CTE. Poganjaj jih po eno naenkrat
(pgAdmin, DBeaver ali `psql`).

---

## Vir podatkov

Podatki so pobrani s portala [nepremicnine.net](https://www.nepremicnine.net)
in služijo izključno študijskim namenom.
