-- ============================================================================
--  OPB – Najem nepremičnin
--  Datoteka: Data/pravice.sql
--
--  Podeli pravice nad bazo. Zaženi ŠELE PO create_database.sql,
--  ker GRANT deluje samo nad tabelami, ki že obstajajo.
--
--  Zaženi kot lastnik baze (urhvid):
--    psql -h baza.fmf.uni-lj.si -U urhvid -d sem2026_urhvid -f Data/pravice.sql
-- ============================================================================


-- ── 1. Jure (sodelavec pri projektu) – polne pravice ────────────────────────
GRANT CONNECT ON DATABASE sem2026_urhvid TO jurekr;
GRANT USAGE, CREATE ON SCHEMA public TO jurekr;
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO jurekr;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jurekr;

-- Da bo Jure imel pravice tudi nad tabelami, ki jih šele bomo ustvarili:
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO jurekr;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO jurekr;


-- ── 2. javnost (bralni dostop za spletno aplikacijo) ────────────────────────
-- Aplikacija se v privzeti nastavitvi poveže kot 'javnost'.
-- Ta uporabnik sme SAMO brati – tako nihče prek spleta ne more pokvariti baze.
GRANT CONNECT ON DATABASE sem2026_urhvid TO javnost;
GRANT USAGE ON SCHEMA public TO javnost;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO javnost;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO javnost;

-- Izjema: tabela uporabnik.
-- Registracija in beleženje zadnje prijave morata delovati tudi prek
-- javnega dostopa, zato tu dovolimo tudi INSERT in UPDATE.
-- (Gesla so bcrypt zgoščena, zato branje tabele ne razkrije gesel.)
GRANT INSERT, UPDATE ON uporabnik TO javnost;
