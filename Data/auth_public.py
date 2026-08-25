"""Javni (bralni) dostop do baze.

Ta datoteka je v gitu, ker vsebuje samo geslo uporabnika 'javnost', ki sme
podatke brati in dodajati. Za pisanje (ustvarjanje tabel, uvoz podatkov)
skopiraj to datoteko v Data/auth.py in vpiši svoje podatke - Data/auth.py je
v .gitignore. Repository najprej poskusi uvoziti Data.auth, sicer vzame to.
"""

db = "sem2026_urhvid"
host = "baza.fmf.uni-lj.si"
user = "javnost"
password = "javnogeslo"
port = 5432
