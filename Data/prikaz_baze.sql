-- Poizvedbe za predstavitev projekta; poganjaj jih po eno naenkrat
-- (pgAdmin, DBeaver ali psql). Razvrščene so od preprostih proti zahtevnejšim:
-- JOIN, GROUP BY, HAVING, podpoizvedbe, okenske funkcije, CTE in pogled.

-- 1. Koliko podatkov sploh imamo?
SELECT 'oglas'              AS tabela, COUNT(*) AS stevilo FROM oglas
UNION ALL SELECT 'nepremicnina',       COUNT(*) FROM nepremicnina
UNION ALL SELECT 'lokacija',           COUNT(*) FROM lokacija
UNION ALL SELECT 'regija',             COUNT(*) FROM regija
UNION ALL SELECT 'vrsta_nepremicnine', COUNT(*) FROM vrsta_nepremicnine
UNION ALL SELECT 'vir',                COUNT(*) FROM vir
UNION ALL SELECT 'uporabnik',          COUNT(*) FROM uporabnik
ORDER BY stevilo DESC;


-- 2. Pregled oglasov prek pogleda oglas_pregled
-- Pogled nam prihrani pisanje petih JOIN-ov.
SELECT
    id_oglasa      AS "ID",
    naslov         AS "Naslov",
    cena           AS "Cena (€/mes)",
    m2             AS "m²",
    cena_na_m2     AS "€/m²",
    naselje        AS "Naselje",
    obcina         AS "Občina",
    ime_regije     AS "Regija",
    drzava         AS "Država"
FROM oglas_pregled
ORDER BY cena DESC
LIMIT 20;


-- 3. Isto brez pogleda – da vidimo, kaj pogled skriva
SELECT
    o.id_oglasa, o.naslov, o.cena, n.m2,
    l.naselje, l.obcina, r.ime_regije, r.drzava, vn.ime_vrste, vi.ime_vira
FROM oglas o
    JOIN nepremicnina       n  ON n.id_nepremicnine = o.id_nepremicnine
    JOIN vrsta_nepremicnine vn ON vn.id_vrste       = n.id_vrste
    JOIN lokacija           l  ON l.id_lokacije     = n.id_lokacije
    JOIN vir                vi ON vi.id_vira        = o.id_vira
    LEFT JOIN regija        r  ON r.id_regije       = l.id_regije
ORDER BY o.cena DESC
LIMIT 20;


-- 4. Povprečna najemnina po regijah (GROUP BY + HAVING)
-- HAVING filtrira PO združevanju (WHERE filtrira PRED njim).
SELECT
    r.ime_regije                                        AS "Regija",
    r.drzava                                            AS "Država",
    COUNT(*)                                            AS "Št. oglasov",
    ROUND(AVG(o.cena), 2)                               AS "Povpr. cena",
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY o.cena)::numeric, 2)
                                                        AS "Mediana",
    ROUND(AVG(n.m2), 1)                                 AS "Povpr. m²",
    ROUND(AVG(o.cena / NULLIF(n.m2, 0)), 2)             AS "Povpr. €/m²"
FROM oglas o
    JOIN nepremicnina n ON n.id_nepremicnine = o.id_nepremicnine
    JOIN lokacija     l ON l.id_lokacije     = n.id_lokacije
    JOIN regija       r ON r.id_regije       = l.id_regije
GROUP BY r.ime_regije, r.drzava
HAVING COUNT(*) >= 10
ORDER BY "Povpr. €/m²" DESC;


-- 5. Primerjava Slovenija : Hrvaška
SELECT
    r.drzava                                 AS "Država",
    COUNT(*)                                 AS "Št. oglasov",
    ROUND(AVG(o.cena), 2)                    AS "Povpr. najemnina",
    ROUND(MIN(o.cena), 2)                    AS "Najnižja",
    ROUND(MAX(o.cena), 2)                    AS "Najvišja",
    ROUND(AVG(n.m2), 1)                      AS "Povpr. m²",
    ROUND(AVG(o.cena / NULLIF(n.m2, 0)), 2)  AS "Povpr. €/m²"
FROM oglas o
    JOIN nepremicnina n ON n.id_nepremicnine = o.id_nepremicnine
    JOIN lokacija     l ON l.id_lokacije     = n.id_lokacije
    JOIN regija       r ON r.id_regije       = l.id_regije
GROUP BY r.drzava
ORDER BY r.drzava;


-- 6. Deset najdražjih naselij (podpoizvedba v FROM)
SELECT *
FROM (
    SELECT
        l.naselje,
        r.ime_regije,
        COUNT(*)                                AS stevilo_oglasov,
        ROUND(AVG(o.cena / NULLIF(n.m2, 0)), 2) AS eur_na_m2
    FROM oglas o
        JOIN nepremicnina n ON n.id_nepremicnine = o.id_nepremicnine
        JOIN lokacija     l ON l.id_lokacije     = n.id_lokacije
        JOIN regija       r ON r.id_regije       = l.id_regije
    WHERE l.naselje IS NOT NULL
    GROUP BY l.naselje, r.ime_regije
    HAVING COUNT(*) >= 5
) AS po_naseljih
ORDER BY eur_na_m2 DESC
LIMIT 10;


-- 7. Oglasi, dražji od povprečja SVOJE regije (okenska funkcija)
-- AVG(...) OVER (PARTITION BY ...) izračuna povprečje po skupinah,
-- a NE zloži vrstic skupaj – zato lahko vsako vrstico primerjamo s "svojim"
-- povprečjem. Brez okenskih funkcij bi potrebovali dodatno podpoizvedbo.
WITH s_povprecji AS (
    SELECT
        o.id_oglasa,
        o.naslov,
        o.cena,
        r.ime_regije,
        ROUND(AVG(o.cena) OVER (PARTITION BY r.id_regije), 2) AS povprecje_regije
    FROM oglas o
        JOIN nepremicnina n ON n.id_nepremicnine = o.id_nepremicnine
        JOIN lokacija     l ON l.id_lokacije     = n.id_lokacije
        JOIN regija       r ON r.id_regije       = l.id_regije
)
SELECT
    naslov,
    ime_regije,
    cena,
    povprecje_regije,
    ROUND(cena - povprecje_regije, 2) AS "Razlika"
FROM s_povprecji
WHERE cena > povprecje_regije * 1.5
ORDER BY "Razlika" DESC
LIMIT 15;


-- 8. Najdražji oglas v vsaki regiji (ROW_NUMBER)
WITH ostevilceni AS (
    SELECT
        o.naslov, o.cena, r.ime_regije, l.naselje,
        ROW_NUMBER() OVER (PARTITION BY r.id_regije ORDER BY o.cena DESC) AS mesto
    FROM oglas o
        JOIN nepremicnina n ON n.id_nepremicnine = o.id_nepremicnine
        JOIN lokacija     l ON l.id_lokacije     = n.id_lokacije
        JOIN regija       r ON r.id_regije       = l.id_regije
)
SELECT ime_regije, naslov, naselje, cena
FROM ostevilceni
WHERE mesto = 1
ORDER BY cena DESC;


-- 9. Porazdelitev cen po razredih (histogram)
SELECT
    (FLOOR(cena / 250) * 250)::int AS "Razred od (€)",
    (FLOOR(cena / 250) * 250 + 249)::int AS "Razred do (€)",
    COUNT(*)                       AS "Št. oglasov",
    REPEAT('█', (COUNT(*) / 10)::int) AS "Graf"   -- besedilni stolpčni graf
FROM oglas
GROUP BY 1, 2
ORDER BY 1;


-- 10. Cena glede na starost stavbe
-- CASE deluje kot if-elif-else in nam omogoči lastne skupine.
SELECT
    CASE
        WHEN n.leto_gradnje IS NULL      THEN 'ni podatka'
        WHEN n.leto_gradnje < 1945       THEN 'pred 1945'
        WHEN n.leto_gradnje < 1980       THEN '1945–1979'
        WHEN n.leto_gradnje < 2000       THEN '1980–1999'
        WHEN n.leto_gradnje < 2015       THEN '2000–2014'
        ELSE                                  '2015 in novejše'
    END                                     AS "Obdobje gradnje",
    COUNT(*)                                AS "Št. oglasov",
    ROUND(AVG(o.cena), 2)                   AS "Povpr. cena",
    ROUND(AVG(o.cena / NULLIF(n.m2, 0)), 2) AS "Povpr. €/m²"
FROM oglas o
    JOIN nepremicnina n ON n.id_nepremicnine = o.id_nepremicnine
GROUP BY 1
ORDER BY 1;


-- 11. Kje je največ ponudbe? (top 15 občin)
SELECT
    l.obcina                    AS "Občina",
    r.drzava                    AS "Država",
    COUNT(*)                    AS "Št. oglasov",
    ROUND(AVG(o.cena), 2)       AS "Povpr. cena"
FROM oglas o
    JOIN nepremicnina n ON n.id_nepremicnine = o.id_nepremicnine
    JOIN lokacija     l ON l.id_lokacije     = n.id_lokacije
    JOIN regija       r ON r.id_regije       = l.id_regije
WHERE l.obcina IS NOT NULL
GROUP BY l.obcina, r.drzava
ORDER BY COUNT(*) DESC
LIMIT 15;


-- 12. Preverjanje kakovosti podatkov
-- Koliko oglasov nima posameznega podatka?
SELECT
    COUNT(*)                                              AS "Vseh oglasov",
    COUNT(*) FILTER (WHERE n.leto_gradnje IS NULL)        AS "Brez leta gradnje",
    COUNT(*) FILTER (WHERE n.stevilo_sob IS NULL)         AS "Brez št. sob",
    COUNT(*) FILTER (WHERE n.nadstropje IS NULL)          AS "Brez nadstropja",
    COUNT(*) FILTER (WHERE n.opis IS NULL)                AS "Brez opisa",
    COUNT(*) FILTER (WHERE l.id_regije IS NULL)           AS "Brez regije",
    COUNT(*) FILTER (WHERE o.url_oglasa IS NULL)          AS "Brez povezave"
FROM oglas o
    JOIN nepremicnina n ON n.id_nepremicnine = o.id_nepremicnine
    JOIN lokacija     l ON l.id_lokacije     = n.id_lokacije;


-- 13. Ali je uvoz res idempotenten?
-- Poizvedba mora vrniti NIČ vrstic – to dokazuje, da ni podvojenih oglasov.
SELECT id_vira, zunanji_id, COUNT(*) AS kolikokrat
FROM oglas
WHERE zunanji_id IS NOT NULL
GROUP BY id_vira, zunanji_id
HAVING COUNT(*) > 1;


-- 14. Ali kateri indeks sploh uporabimo?
-- EXPLAIN pokaže načrt izvedbe. Pri filtru po ceni bi moral Postgres
-- uporabiti idx_oglas_cena namesto branja celotne tabele (Seq Scan).
EXPLAIN ANALYZE
SELECT * FROM oglas WHERE cena BETWEEN 800 AND 1200;
