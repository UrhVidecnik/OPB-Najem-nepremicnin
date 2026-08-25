-- Pravice nad bazo. Zaženi šele po create_database.sql, ker GRANT deluje
-- samo nad tabelami, ki že obstajajo. Zaženi kot lastnik baze.

-- 1. Jure (sodelavec pri projektu) – polne pravice
GRANT CONNECT ON DATABASE sem2026_urhvid TO jurekr;
GRANT USAGE, CREATE ON SCHEMA public TO jurekr;
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO jurekr;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jurekr;

-- Da bo Jure imel pravice tudi nad tabelami, ki jih šele bomo ustvarili:
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO jurekr;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO jurekr;


-- 2. javnost (bralni dostop za spletno aplikacijo)
-- Aplikacija se v privzeti nastavitvi poveže kot 'javnost'.
--
-- Ta uporabnik sme:
--     BRATI vse (SELECT)
--     DODAJATI oglase (INSERT)
-- ne sme pa:
--     SPREMINJATI ali BRISATI oglasov (UPDATE, DELETE)
--     spreminjati sheme (CREATE, DROP, ALTER)
--
-- To se ujema s pravili v aplikaciji: dodajanje je dovoljeno vsakemu
-- prijavljenemu uporabniku, urejanje in brisanje pa samo skrbniku, ki
-- aplikacijo poganja z osebnim dostopom (Data/auth.py). Tudi če bi kdo
-- obšel spletni vmesnik in se na bazo povezal neposredno kot 'javnost',
-- obstoječih oglasov ne more pokvariti.

GRANT CONNECT ON DATABASE sem2026_urhvid TO javnost;
GRANT USAGE ON SCHEMA public TO javnost;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO javnost;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO javnost;

-- Dodajanje novega oglasa prek obrazca vpiše vrstico v tri tabele:
-- lokacijo (če je še ni), nepremičnino in oglas.
GRANT INSERT ON lokacija      TO javnost;
GRANT INSERT ON nepremicnina  TO javnost;
GRANT INSERT ON oglas         TO javnost;

-- Stolpci SERIAL vrednosti jemljejo iz zaporedij (sequence), zato mora
-- imeti uporabnik nad njimi pravico USAGE – brez tega INSERT ne uspe.
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO javnost;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO javnost;

-- Tabela uporabnik: registracija (INSERT), beleženje zadnje prijave in
-- dodeljevanje vlog s skripto nastavi_admina.py (UPDATE).
-- (Gesla so bcrypt zgoščena, zato branje tabele ne razkrije gesel.)
GRANT INSERT, UPDATE ON uporabnik TO javnost;
