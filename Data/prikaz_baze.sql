-- ============================================================
-- Prikaz podatkov v bazi – OPB Projekt: Najem nepremičnin
-- ============================================================


-- ── 1. VSI OGLASI (pregled vseh entitet skupaj) ──────────────
SELECT
    o.id_oglasa                          AS "ID oglasa",
    v.ime_vira                           AS "Vir",
    o.naslov                             AS "Naslov",
    o.cena                               AS "Cena (€/mes)",
    vn.ime_vrste                         AS "Vrsta",
    l.ime                                AS "Lokacija",
    COALESCE(l.soseska, '')              AS "Soseska",
    l.regija                             AS "Regija",
    n.m2                                 AS "m²",
    n.stevilo_sob                        AS "Sobe",
    n.leto_gradnje                       AS "Leto gradnje",
    o.url_oglasa                         AS "URL"
FROM oglas            o
JOIN vir              v  ON v.id_vira          = o.id_vira
JOIN nepremicnina     n  ON n.id_nepremicnine  = o.id_nepremicnine
JOIN vrsta_nepremicnine vn ON vn.id_vrste      = n.id_vrste
JOIN lokacija         l  ON l.id_lokacije      = n.id_lokacije
ORDER BY o.cena DESC;