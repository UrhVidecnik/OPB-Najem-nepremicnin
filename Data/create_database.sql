-- Ta datoteka vsebuje vse potrebne CREATE ukaze s katerimi lahko ustvarimo bazo od začetka.

CREATE TABLE vir (
    id_vira SERIAL PRIMARY KEY,
    ime_vira VARCHAR(100) NOT NULL,
    url_vira TEXT
);

CREATE TABLE vrsta_nepremicnine (
    id_vrste SERIAL PRIMARY KEY,
    ime_vrste VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE lokacija_mesto (
    id_lokacije SERIAL PRIMARY KEY,
    ime VARCHAR(100) NOT NULL,
    regija VARCHAR(100),
    soseska VARCHAR(100),
    postna_stevilka VARCHAR(10)
);

CREATE TABLE nepremicnina (
    id_nepremicnine SERIAL PRIMARY KEY,
    id_vrste INTEGER NOT NULL,
    id_lokacije INTEGER NOT NULL,
    opis TEXT,
    leto_gradnje INTEGER,
    stevilo_sob NUMERIC(4,1),
    nadstropje VARCHAR(30),
    m2 NUMERIC(10,2) NOT NULL,
    CONSTRAINT fk_nepremicnina_vrsta
        FOREIGN KEY (id_vrste) REFERENCES vrsta_nepremicnine (id_vrste),
    CONSTRAINT fk_nepremicnina_lokacija
        FOREIGN KEY (id_lokacije) REFERENCES lokacija_mesto (id_lokacije),
    CONSTRAINT chk_nepremicnina_leto_gradnje
        CHECK (leto_gradnje IS NULL OR leto_gradnje BETWEEN 1800 AND 2100),
    CONSTRAINT chk_nepremicnina_stevilo_sob
        CHECK (stevilo_sob IS NULL OR stevilo_sob > 0),
    CONSTRAINT chk_nepremicnina_m2
        CHECK (m2 > 0)
);

CREATE TABLE oglas (
    id_oglasa SERIAL PRIMARY KEY,
    id_vira INTEGER NOT NULL,
    id_nepremicnine INTEGER NOT NULL,
    naslov VARCHAR(255) NOT NULL,
    url_oglasa TEXT,
    cena NUMERIC(12,2) NOT NULL,
    datum_objave DATE,
    CONSTRAINT fk_oglas_vir
        FOREIGN KEY (id_vira) REFERENCES vir (id_vira),
    CONSTRAINT fk_oglas_nepremicnina
        FOREIGN KEY (id_nepremicnine) REFERENCES nepremicnina (id_nepremicnine),
    CONSTRAINT chk_oglas_cena
        CHECK (cena >= 0)
);
