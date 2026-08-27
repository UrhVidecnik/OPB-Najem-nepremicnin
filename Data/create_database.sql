-- Shema baze: tabele, indeksi in pogled oglas_pregled.


-- Vsakič ob zagonu te datoteke se baza resitira in na novo vzpostavi (brisanje obstoječih tabel in podatkov v njih)
-- CASCADE poskrbi, da se pobrišejo tudi tuji ključi, ki kažejo na tabelo.
DROP VIEW  IF EXISTS oglas_pregled CASCADE;

DROP TABLE IF EXISTS oglas              CASCADE;
DROP TABLE IF EXISTS nepremicnina       CASCADE;
DROP TABLE IF EXISTS lokacija           CASCADE;
DROP TABLE IF EXISTS regija             CASCADE;
DROP TABLE IF EXISTS vrsta_nepremicnine CASCADE;
DROP TABLE IF EXISTS vir                CASCADE;
DROP TABLE IF EXISTS uporabnik          CASCADE;


-- 1. VIR - od kod je oglas pobran

CREATE TABLE vir (
    id_vira  SERIAL PRIMARY KEY,          
    ime_vira TEXT NOT NULL UNIQUE,        
    url_vira TEXT
);

COMMENT ON TABLE vir IS 'Spletni portal, s katerega je bil oglas pobran.';


-- 2. VRSTA NEPREMIČNINE

CREATE TABLE vrsta_nepremicnine (
    id_vrste  SERIAL PRIMARY KEY,
    ime_vrste TEXT NOT NULL UNIQUE
);

COMMENT ON TABLE vrsta_nepremicnine IS 'Šifrant vrst nepremičnin (Stanovanje, Hiša, ...).';


-- 3. REGIJA
-- Rregijo ločimo v svojo tabelo, ker se v podatkih ponovi velikokrat - normalizacija
-- vsaka regija pripada eni državi

CREATE TABLE regija (
    id_regije  SERIAL PRIMARY KEY,
    ime_regije TEXT NOT NULL,
    drzava     CHAR(2) NOT NULL DEFAULT 'SI',   -- ISO oznaka: 'SI', 'HR'

    CONSTRAINT uq_regija         UNIQUE (ime_regije, drzava),
    CONSTRAINT chk_regija_drzava CHECK (drzava IN ('SI', 'HR'))
);

COMMENT ON TABLE regija IS 'Regija (statistična / oglaševalska) skupaj z državo.';


-- 4. LOKACIJA
-- upravna enota, obcina, naselje, postna stevilka

CREATE TABLE lokacija (
    id_lokacije     SERIAL PRIMARY KEY,
    id_regije       INTEGER,               -- lahko NULL
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
-- opis, leto gradnje, število sob, nadstropje, kvadratura
-- ločeno od oglasa, ker je lahko oglaševana večkrat

CREATE TABLE nepremicnina (
    id_nepremicnine  SERIAL PRIMARY KEY,
    id_vrste         INTEGER NOT NULL,
    id_lokacije      INTEGER NOT NULL,

    opis             TEXT,                
    leto_gradnje     INTEGER,
    stevilo_sob      NUMERIC(4,1),         -- NUMERIC, ker obstajajo "1,5-sobno"
    stevilo_sob_opis VARCHAR(100),         -- izvorni zapis, npr. "3-sobno"
    nadstropje       VARCHAR(50),          -- "P", "2", "M", "VP" 
    m2               NUMERIC(10,2) NOT NULL,

    CONSTRAINT fk_nepremicnina_vrsta
        FOREIGN KEY (id_vrste)    REFERENCES vrsta_nepremicnine (id_vrste),
    CONSTRAINT fk_nepremicnina_lokacija
        FOREIGN KEY (id_lokacije) REFERENCES lokacija (id_lokacije),

    CONSTRAINT chk_nepremicnina_sob
        CHECK (stevilo_sob IS NULL OR stevilo_sob > 0),
    CONSTRAINT chk_nepremicnina_m2
        CHECK (m2 > 0),
    CONSTRAINT chk_nepremicnina_leto
        CHECK (leto_gradnje IS NULL OR leto_gradnje BETWEEN 1200 AND 2100)
);

COMMENT ON TABLE nepremicnina IS 'Fizična nepremičnina (kvadratura, sobe, leto gradnje, lokacija).';


-- 6. OGLAS
-- Konkretna objava za najem: naslov, cena, povezava

CREATE TABLE oglas (
    id_oglasa       SERIAL PRIMARY KEY,
    id_vira         INTEGER NOT NULL,
    id_nepremicnine INTEGER NOT NULL,

    -- zunanji_id = ID oglasa na portalu, skupaj z id_vira tvori UNIQUE
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
        ON DELETE CASCADE,              -- brisanje NEPREMIČNINE pobriše tudi njene oglase; obratno ne velja

    CONSTRAINT uq_oglas_zunanji
        UNIQUE (id_vira, zunanji_id),
    CONSTRAINT chk_oglas_cena
        CHECK (cena >= 0)
);

COMMENT ON TABLE oglas IS 'Objava za najem: naslov, cena, povezava, datum.';


-- 7. UPORABNIK
-- Za prijavo v aplikacijo, geslo shranjeno kot bcrypt hash

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

CREATE INDEX idx_oglas_cena           ON oglas (cena);
CREATE INDEX idx_oglas_vir            ON oglas (id_vira);
CREATE INDEX idx_nepremicnina_m2      ON nepremicnina (m2);
CREATE INDEX idx_nepremicnina_vrsta   ON nepremicnina (id_vrste);
CREATE INDEX idx_nepremicnina_lokacija ON nepremicnina (id_lokacije);
CREATE INDEX idx_lokacija_regija      ON lokacija (id_regije);

-- indeks za iskanje po naslovu; lower(), da je iskanje neobčutljivo na velike/male črke
CREATE INDEX idx_oglas_naslov_lower   ON oglas (lower(naslov));


-- 9. POGLED oglas_pregled
-- vse podatke o oglasu združimo na eno mesto

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

    ROUND(o.cena / NULLIF(n.m2, 0), 2) AS cena_na_m2,       -- cena na kvadratni meter

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
    -- LEFT JOIN, ker lokacija brez regije mora ostati vidna

COMMENT ON VIEW oglas_pregled IS 'Vsi podatki o oglasu na enem mestu (oglas + nepremičnina + lokacija + regija + vir).';
