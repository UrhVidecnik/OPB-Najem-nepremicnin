-- ============================================================
-- Uvoz 14 testnih oglasov iz mojikvadrati.com
-- Vir podatkov: mojikvadrati_oglasi.json
--
-- Vključuje vse potrebne statične podatke (vir, vrsta, lokacija)
-- in 14 oglasov razporejenih po entitetah:
--   vir → vrsta_nepremicnine → lokacija → nepremicnina → oglas
--
-- Zagotovljeno idempotentno (ON CONFLICT DO NOTHING / safe CTEs)
-- ============================================================

BEGIN;

-- ─── 1. VIR ─────────────────────────────────────────────────
INSERT INTO vir (ime_vira, url_vira) VALUES
    ('Moji Kvadrati', 'https://mojikvadrati.com/nepremicnine/oddaja')
ON CONFLICT DO NOTHING;


-- ─── 2. VRSTA NEPREMIČNINE ───────────────────────────────────
INSERT INTO vrsta_nepremicnine (ime_vrste) VALUES
    ('Stanovanje'),
    ('Hiša'),
    ('Poslovni prostor'),
    ('Parcela'),
    ('Počitniški objekt'),
    ('Garaža'),
    ('Vikend'),
    ('Kmetija'),
    ('Soba'),
    ('Posest')
ON CONFLICT (ime_vrste) DO NOTHING;


-- ─── 3. LOKACIJA (samo tiste, ki jih potrebujemo) ────────────
INSERT INTO lokacija (ime, postna_stevilka, regija, soseska) VALUES
    ('Ljubljana',                  1000, 'Osrednjeslovenska', NULL),
    ('Ljubljana - Center',         1000, 'Osrednjeslovenska', 'Center'),
    ('Ljubljana - Bežigrad',       1000, 'Osrednjeslovenska', 'Bežigrad'),
    ('Ljubljana - Šiška',          1000, 'Osrednjeslovenska', 'Šiška'),
    ('Ljubljana - Vič',            1000, 'Osrednjeslovenska', 'Vič'),
    ('Maribor',                    2000, 'Podravska',          NULL),
    ('Maribor - Tabor',            2000, 'Podravska',          'Tabor'),
    ('Kamnik',                     1241, 'Osrednjeslovenska', NULL),
    ('Brezovica pri Ljubljani',    1353, 'Osrednjeslovenska', NULL),
    ('Kozje',                      3260, 'Savinjska',          NULL),
    ('Bled',                       4260, 'Gorenjska',          NULL)
ON CONFLICT DO NOTHING;


-- ─── 4. NEPREMIČNINE + OGLASI ────────────────────────────────
-- Vsak par: CTE vstavi nepremicnina in vrne id,
-- nato vstavi oglas z dobljenim id-jem.
-- (Ni potrebe po currval ali sequence imenu)


-- [1] Stanovanje 3-sobno, Ljubljana - Center, 76.1 m², 1959
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Stanovanje'      LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Ljubljana - Center' LIMIT 1),
        NULL, 1959, 3.0, NULL, 76.1
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Stanovanje, 3-sobno – Ljubljana, Center',
    'https://mojikvadrati.com/nepremicnina/529899-oddaja-stanovanje-3-sobno-ljubljana-center',
    1450.00, NULL
FROM n;


-- [2] Stanovanje 2,5-sobno, Ljubljana - Bežigrad (Črnuče), 84.8 m², 2022
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Stanovanje'         LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Ljubljana - Bežigrad' LIMIT 1),
        NULL, 2022, 2.5, NULL, 84.8
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Stanovanje, 2,5-sobno – Ljubljana, Bežigrad, Črnuče',
    'https://mojikvadrati.com/nepremicnina/528980-oddaja-stanovanje-2-5-sobno-ljubljana-bezigrad',
    1350.00, NULL
FROM n;


-- [3] Stanovanje 2-sobno, Ljubljana - Center, 57.8 m², 2008
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Stanovanje'       LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Ljubljana - Center' LIMIT 1),
        NULL, 2008, 2.0, NULL, 57.8
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Stanovanje, 2-sobno – Ljubljana, Center',
    'https://mojikvadrati.com/nepremicnina/526721-oddaja-stanovanje-2-sobno-ljubljana-center',
    1500.00, NULL
FROM n;


-- [4] Hiša samostojna, Ljubljana - Bežigrad, 221 m², 1964
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Hiša'               LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Ljubljana - Bežigrad' LIMIT 1),
        NULL, 1964, NULL, NULL, 221.0
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Hiša, Samostojna – Ljubljana, Bežigrad',
    'https://mojikvadrati.com/nepremicnina/531063-oddaja-hisa-samostojna-ljubljana-bezigrad',
    3300.00, NULL
FROM n;


-- [5] Hiša dvostanovanjska, Maribor - Tabor, 180 m², 1940
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Hiša'          LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Maribor - Tabor' LIMIT 1),
        NULL, 1940, NULL, NULL, 180.0
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Hiša, Dvostanovanjska – Maribor, Tabor',
    'https://mojikvadrati.com/nepremicnina/531006-oddaja-hisa-dvostanovanjska-podravska-maribor',
    250.00, NULL
FROM n;


-- [6] Hiša samostojna, Kamnik (Stahovica), 152 m², 1960
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Hiša'   LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Kamnik' LIMIT 1),
        NULL, 1960, NULL, NULL, 152.0
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Hiša, Samostojna – Ljubljana okolica, Kamnik, Stahovica',
    'https://mojikvadrati.com/nepremicnina/530980-oddaja-hisa-samostojna-ljubljana-okolica-kamnik',
    1300.00, NULL
FROM n;


-- [7] Parcela zazidljiva, Brezovica pri Ljubljani, 2518 m²
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Parcela'                  LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Brezovica pri Ljubljani'  LIMIT 1),
        NULL, NULL, NULL, NULL, 2518.0
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Parcela, Zazidljiva – Ljubljana okolica, Brezovica',
    'https://mojikvadrati.com/nepremicnina/530975-oddaja-parcela-zazidljiva-ljubljana-okolica-brezovica',
    12600.00, NULL
FROM n;


-- [8] Poslovni prostor, Kozje, 157 m²
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Poslovni prostor' LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Kozje'            LIMIT 1),
        NULL, NULL, NULL, NULL, 157.0
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Poslovni prostor, Poslovni kompleks – Savinjska, Kozje',
    'https://mojikvadrati.com/nepremicnina/530919-oddaja-poslovni-prostor-poslovni-kompleks-savinjska-kozje',
    800.00, NULL
FROM n;


-- [9] Stanovanje 3-sobno, Kozje, 111.6 m², 1992
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Stanovanje' LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Kozje'      LIMIT 1),
        NULL, 1992, 3.0, NULL, 111.6
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Stanovanje, 3-sobno – Savinjska, Kozje',
    'https://mojikvadrati.com/nepremicnina/530918-oddaja-stanovanje-3-sobno-savinjska-kozje',
    700.00, NULL
FROM n;


-- [10] Stanovanje garsonjera, Bled, 37.8 m²
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Stanovanje' LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Bled'       LIMIT 1),
        NULL, NULL, 0.5, NULL, 37.8
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Stanovanje, Garsonjera – Gorenjska, Bled',
    'https://mojikvadrati.com/nepremicnina/530916-oddaja-stanovanje-garsonjera-gorenjska-bled',
    600.00, NULL
FROM n;


-- [11] Stanovanje 1-sobno, Ljubljana - Šiška, 75 m², 1967
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Stanovanje'      LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Ljubljana - Šiška' LIMIT 1),
        NULL, 1967, 1.0, NULL, 75.0
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Stanovanje, 1-sobno – Ljubljana, Šiška',
    'https://mojikvadrati.com/nepremicnina/530906-oddaja-stanovanje-1-sobno-ljubljana-siska',
    750.00, NULL
FROM n;


-- [12] Stanovanje 2-sobno, Ljubljana - Center (Prule), 46 m², 1840
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Stanovanje'       LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Ljubljana - Center' LIMIT 1),
        NULL, 1840, 2.0, NULL, 46.0
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Stanovanje, 2-sobno – Ljubljana, Center, Prule',
    'https://mojikvadrati.com/nepremicnina/530889-oddaja-stanovanje-2-sobno-ljubljana-center',
    1100.00, NULL
FROM n;


-- [13] Stanovanje 1-sobno, Ljubljana - Center (Vodmat), 55.81 m², 2025
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Stanovanje'       LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Ljubljana - Center' LIMIT 1),
        NULL, 2025, 1.0, NULL, 55.81
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Stanovanje, 1-sobno – Ljubljana, Center, Vodmat',
    'https://mojikvadrati.com/nepremicnina/530861-oddaja-stanovanje-1-sobno-ljubljana-center',
    1100.00, NULL
FROM n;


-- [14] Počitniški objekt apartma, Ljubljana - Vič, 34 m²
WITH n AS (
    INSERT INTO nepremicnina (id_vrste, id_lokacije, opis, leto_gradnje, stevilo_sob, nadstropje, m2)
    VALUES (
        (SELECT id_vrste    FROM vrsta_nepremicnine WHERE ime_vrste = 'Počitniški objekt' LIMIT 1),
        (SELECT id_lokacije FROM lokacija            WHERE ime      = 'Ljubljana - Vič'   LIMIT 1),
        NULL, NULL, NULL, NULL, 34.0
    ) RETURNING id_nepremicnine
)
INSERT INTO oglas (id_vira, id_nepremicnine, naslov, url_oglasa, cena, datum_objave)
SELECT
    (SELECT id_vira FROM vir WHERE ime_vira = 'Moji Kvadrati' LIMIT 1),
    id_nepremicnine,
    'Oddaja: Počitniški objekt, Apartma – Ljubljana, Vič-Rudnik',
    'https://mojikvadrati.com/nepremicnina/530850-oddaja-pocitniski-objekt-apartma-ljubljana-vic-rudnik',
    600.00, NULL
FROM n;


-- ─── Preveri rezultat ────────────────────────────────────────
SELECT
    o.id_oglasa,
    o.naslov,
    o.cena,
    v.ime_vira,
    vn.ime_vrste,
    l.ime        AS lokacija,
    l.soseska,
    n.m2,
    n.stevilo_sob,
    n.leto_gradnje
FROM oglas o
JOIN vir              v  ON v.id_vira        = o.id_vira
JOIN nepremicnina     n  ON n.id_nepremicnine = o.id_nepremicnine
JOIN vrsta_nepremicnine vn ON vn.id_vrste     = n.id_vrste
JOIN lokacija         l  ON l.id_lokacije    = n.id_lokacije
WHERE v.ime_vira = 'Moji Kvadrati'
ORDER BY o.id_oglasa;

COMMIT;
