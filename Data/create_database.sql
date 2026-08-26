-- Shema baze: tabele, indeksi in pogled oglas_pregled.
-- Zagon: python init_db.py  (ali psql -h ... -f Data/create_database.sql)
-- Pozor: razdelek 0 pobriše obstoječe tabele in vse podatke v njih.

-- 0. Brisanje obstoječih objektov
-- Vrstni red je pomemben: najprej pogled, nato tabele od "otrok" proti "staršem".
-- CASCADE poskrbi, da se pobrišejo tudi tuji ključi, ki kažejo na tabelo.

DROP VIEW  IF EXISTS oglas_pregled CASCADE;

DROP TABLE IF EXISTS oglas              CASCADE;
DROP TABLE IF EXISTS nepremicnina       CASCADE;
DROP TABLE IF EXISTS lokacija           CASCADE;
DROP TABLE IF EXISTS regija             CASCADE;
DROP TABLE IF EXISTS vrsta_nepremicnine CASCADE;
DROP TABLE IF EXISTS vir                CASCADE;
DROP TABLE IF EXISTS uporabnik          CASCADE;


-- 1. VIR
-- Od kod je oglas pobran (nepremicnine.net, bolha.com, ...).
-- Šifrant: majhna tabela z nekaj vrsticami, na katero se sklicujejo oglasi.

CREATE TABLE vir (
    id_vira  SERIAL PRIMARY KEY,          -- SERIAL = samodejno naraščajoče celo število
    ime_vira TEXT NOT NULL UNIQUE,        -- UNIQUE, da istega vira ne vnesemo dvakrat
    url_vira TEXT
);

COMMENT ON TABLE vir IS 'Spletni portal, s katerega je bil oglas pobran.';


-- 2. VRSTA NEPREMIČNINE
-- Stanovanje, Hiša, Poslovni prostor, Garaža, ...

CREATE TABLE vrsta_nepremicnine (
    id_vrste  SERIAL PRIMARY KEY,
    ime_vrste TEXT NOT NULL UNIQUE
);

COMMENT ON TABLE vrsta_nepremicnine IS 'Šifrant vrst nepremičnin (Stanovanje, Hiša, ...).';


-- 3. REGIJA
-- Regijo smo ločili v svojo tabelo, ker se v podatkih ponovi ZELO velikokrat
-- (npr. "Ljubljana mesto" pri več sto oglasih) – to je klasična normalizacija.
-- Država je lastnost regije: nepremicnine.net oglašuje tudi hrvaške nepremičnine,
-- vsaka regija pa pripada natanko eni državi.

CREATE TABLE regija (
    id_regije  SERIAL PRIMARY KEY,
    ime_regije TEXT NOT NULL,
    drzava     CHAR(2) NOT NULL DEFAULT 'SI',   -- ISO oznaka: 'SI', 'HR'

    CONSTRAINT uq_regija         UNIQUE (ime_regije, drzava),
    CONSTRAINT chk_regija_drzava CHECK (drzava IN ('SI', 'HR'))
);

COMMENT ON TABLE regija IS 'Regija (statistična / oglaševalska) skupaj z državo.';


-- 4. LOKACIJA
-- Ena vrstica = ena konkretna kombinacija upravna enota + občina + naselje
-- znotraj neke regije. Scraper pobere prav to hierarhijo z detajlne strani
-- oglasa ("Regija: Ljubljana mesto | Upravna enota: ... | Občina: ... | Naselje: ...").

CREATE TABLE lokacija (
    id_lokacije     SERIAL PRIMARY KEY,
    id_regije       INTEGER,               -- lahko NULL: ~18 oglasov nima lokacije
    upravna_enota   TEXT,
    obcina          TEXT,
    naselje         TEXT,
    postna_stevilka INTEGER,

    CONSTRAINT fk_lokacija_regija
        FOREIGN KEY (id_regije) REFERENCES regija (id_regije),

    CONSTRAINT chk_lokacija_posta
        CHECK (postna_stevilka IS NULL OR postna_stevilka BETWEEN 1000 AND 99999)
);

-- Navaden UNIQUE tu NE deluje, ker v SQL velja NULL <> NULL – dve vrstici z
-- NULL naseljem bi se šteli za različni in bi se lahko podvojili.
-- Zato COALESCE-amo NULL v prazen niz in šele nato zahtevamo enoličnost.
CREATE UNIQUE INDEX uq_lokacija ON lokacija (
    COALESCE(id_regije, -1),
    COALESCE(upravna_enota, ''),
    COALESCE(obcina, ''),
    COALESCE(naselje, '')
);

COMMENT ON TABLE lokacija IS 'Konkretna lokacija: upravna enota + občina + naselje znotraj regije.';


-- 5. NEPREMIČNINA
-- Fizična nepremičnina: koliko kvadratov, koliko sob, katero leto zgrajena.
-- Ločena od oglasa zato, ker je ista nepremičnina lahko oglaševana večkrat
-- (drug portal, druga cena, čez pol leta znova).

CREATE TABLE nepremicnina (
    id_nepremicnine  SERIAL PRIMARY KEY,
    id_vrste         INTEGER NOT NULL,
    id_lokacije      INTEGER NOT NULL,

    opis             TEXT,                 -- poln opis z detajlne strani
    leto_gradnje     INTEGER,
    stevilo_sob      NUMERIC(4,1),         -- NUMERIC, ker obstajajo "1,5-sobno"
    stevilo_sob_opis VARCHAR(100),         -- izvorni zapis, npr. "3-sobno"
    nadstropje       VARCHAR(50),          -- "P", "2", "M", "VP" – zato besedilo
    m2               NUMERIC(10,2) NOT NULL,

    CONSTRAINT fk_nepremicnina_vrsta
        FOREIGN KEY (id_vrste)    REFERENCES vrsta_nepremicnine (id_vrste),
    CONSTRAINT fk_nepremicnina_lokacija
        FOREIGN KEY (id_lokacije) REFERENCES lokacija (id_lokacije),

    CONSTRAINT chk_nepremicnina_sob
        CHECK (stevilo_sob IS NULL OR stevilo_sob > 0),
    CONSTRAINT chk_nepremicnina_m2
        CHECK (m2 > 0),
    -- Meja 1200 in ne 1800: med oglasi so res stavbe iz let 1451, 1520, 1607.
    CONSTRAINT chk_nepremicnina_leto
        CHECK (leto_gradnje IS NULL OR leto_gradnje BETWEEN 1200 AND 2100)
);

COMMENT ON TABLE nepremicnina IS 'Fizična nepremičnina (kvadratura, sobe, leto gradnje, lokacija).';


-- 6. OGLAS
-- Konkretna objava za najem: naslov, cena, povezava.

CREATE TABLE oglas (
    id_oglasa       SERIAL PRIMARY KEY,
    id_vira         INTEGER NOT NULL,
    id_nepremicnine INTEGER NOT NULL,

    -- zunanji_id = ID oglasa NA PORTALU (npr. 7111539 iz URL-ja).
    -- Skupaj z id_vira tvori UNIQUE – to je ključ, ki naredi uvoz IDEMPOTENTEN:
    -- skripto za uvoz lahko poženeš stokrat in oglasi se ne bodo podvajali.
    zunanji_id      TEXT,

    naslov          TEXT NOT NULL,
    url_oglasa      TEXT,
    cena            NUMERIC(12,2) NOT NULL,
    valuta          CHAR(3) NOT NULL DEFAULT 'EUR',
    datum_objave    DATE,
    datum_zajema    DATE NOT NULL DEFAULT CURRENT_DATE,   -- kdaj smo ga mi pobrali

    CONSTRAINT fk_oglas_vir
        FOREIGN KEY (id_vira)         REFERENCES vir (id_vira),
    CONSTRAINT fk_oglas_nepremicnina
        FOREIGN KEY (id_nepremicnine) REFERENCES nepremicnina (id_nepremicnine)
        -- CASCADE deluje v smeri tujega ključa: brisanje NEPREMIČNINE
        -- pobriše tudi njene oglase. Obratno ne velja – ko brišemo oglas,
        -- nepremičnino odstranimo sami (glej repository.izbrisi_oglas).
        ON DELETE CASCADE,

    CONSTRAINT uq_oglas_zunanji
        UNIQUE (id_vira, zunanji_id),
    CONSTRAINT chk_oglas_cena
        CHECK (cena >= 0)
);

COMMENT ON TABLE oglas IS 'Objava za najem: naslov, cena, povezava, datum.';


-- 7. UPORABNIK
-- Za prijavo v aplikacijo. Geslo NIKOLI ni shranjeno v čistopisu –
-- shranimo bcrypt zgoščeno vrednost (hash).

CREATE TABLE uporabnik (
    uporabnisko_ime TEXT PRIMARY KEY,
    geslo_hash      TEXT NOT NULL,
    vloga           TEXT NOT NULL DEFAULT 'uporabnik',
    zadnja_prijava  TIMESTAMP,

    CONSTRAINT chk_uporabnik_vloga CHECK (vloga IN ('admin', 'uporabnik'))
);

COMMENT ON TABLE uporabnik IS 'Uporabniki aplikacije (bcrypt gesla, vlogi admin/uporabnik).';


-- 8. INDEKSI
-- Indeksi na stolpcih, po katerih v aplikaciji filtriramo in sortiramo.
-- Brez njih mora Postgres pri vsakem filtru prebrati vseh ~2700 vrstic.

CREATE INDEX idx_oglas_cena           ON oglas (cena);
CREATE INDEX idx_oglas_vir            ON oglas (id_vira);
CREATE INDEX idx_nepremicnina_m2      ON nepremicnina (m2);
CREATE INDEX idx_nepremicnina_vrsta   ON nepremicnina (id_vrste);
CREATE INDEX idx_nepremicnina_lokacija ON nepremicnina (id_lokacije);
CREATE INDEX idx_lokacija_regija      ON lokacija (id_regije);

-- Indeks za iskanje po naslovu (ILIKE '%kranj%'). lower() zato,
-- da je iskanje neobčutljivo na velike/male črke.
CREATE INDEX idx_oglas_naslov_lower   ON oglas (lower(naslov));


-- 9. POGLED oglas_pregled
-- Pogled (VIEW) je shranjena poizvedba, ki se obnaša kot tabela.
-- Vse podatke o oglasu združi na eno mesto, da nam v Pythonu ni treba
-- vsakič pisati petih JOIN-ov.

CREATE VIEW oglas_pregled AS
SELECT
    o.id_oglasa,
    o.zunanji_id,
    o.naslov,
    o.url_oglasa,
    o.cena,
    o.valuta,
    o.datum_objave,
    o.datum_zajema,

    -- Izpeljani stolpec: cena na kvadratni meter.
    -- NULLIF(m2, 0) prepreči deljenje z nič.
    ROUND(o.cena / NULLIF(n.m2, 0), 2) AS cena_na_m2,

    n.id_nepremicnine,
    n.opis,
    n.leto_gradnje,
    n.stevilo_sob,
    n.stevilo_sob_opis,
    n.nadstropje,
    n.m2,

    vn.id_vrste,
    vn.ime_vrste,

    l.id_lokacije,
    l.upravna_enota,
    l.obcina,
    l.naselje,
    l.postna_stevilka,

    r.id_regije,
    r.ime_regije,
    r.drzava,

    vi.id_vira,
    vi.ime_vira,
    vi.url_vira
FROM oglas o
    JOIN nepremicnina       n  ON n.id_nepremicnine = o.id_nepremicnine
    JOIN vrsta_nepremicnine vn ON vn.id_vrste       = n.id_vrste
    JOIN lokacija           l  ON l.id_lokacije     = n.id_lokacije
    JOIN vir                vi ON vi.id_vira        = o.id_vira
    LEFT JOIN regija        r  ON r.id_regije       = l.id_regije;
    -- LEFT JOIN, ker lokacija brez regije še vedno mora biti vidna.

COMMENT ON VIEW oglas_pregled IS 'Vsi podatki o oglasu na enem mestu (oglas + nepremičnina + lokacija + regija + vir).';
