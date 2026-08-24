"""
============================================================================
 OPB – Najem nepremičnin
 Datoteka: Data/auth_public.py

 JAVNI (bralni) podatki za priklop na bazo.
 Ta datoteka JE v gitu, ker vsebuje samo javno geslo uporabnika 'javnost',
 ki sme podatke SAMO brati.

 Če želiš v bazo tudi PISATI (uvoz podatkov, ustvarjanje tabel):
   1. skopiraj to datoteko v  Data/auth.py
   2. v kopiji vpiši svoje uporabniško ime in geslo na FMF bazi
   3. Data/auth.py je v .gitignore, zato ne bo nikoli romala na GitHub

 Repository najprej poskusi uvoziti Data.auth; če je ni, uporabi to datoteko.
============================================================================
"""

db = "sem2026_urhvid"
host = "baza.fmf.uni-lj.si"
user = "javnost"
password = "javnogeslo"
port = 5432
