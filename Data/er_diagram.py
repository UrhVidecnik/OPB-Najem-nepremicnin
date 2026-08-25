"""Nariše ER diagram baze v SVG (brez zunanjih knjižnic).

Zagon: python Data/er_diagram.py
Nastane er-nepremicnine.svg v korenu projekta; PNG iz njega naredis npr. z
`rsvg-convert -s 2 er-nepremicnine.svg -o er-nepremicnine.png` ali v brskalniku.
"""

import os

# Barve po skupinah tabel: svetlejša, bolj ko je tabela pomožna.
BARVE = {
    "sifrant": "#7A8BA3",
    "lokacija": "#4A7FA5",
    "jedro": "#1F4E79",
    "oglas": "#C2410C",
    "prijava": "#6B7484",
}

TEKST = "#1F2933"
TEKST_TIP = "#6B7280"
TEKST_SIB = "#9AA3AF"
ROB = "#D7DBE3"
LOCILO = "#EFF1F5"
KLJUC_OZADJE = "#F7F9FC"
NOGA_OZADJE = "#FAFAFB"
CRTA = "#8FA0B4"

SANS = "'Helvetica Neue', Helvetica, Arial, 'DejaVu Sans', sans-serif"
MONO = "'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"

GLAVA_H = 36      # višina naslovne vrstice tabele
VRSTICA_H = 27
NOGA_H = 25
ROB_L = 13        # notranji levi odmik
STOLPEC_GAP = 140  # vodoravni razmik med stolpci diagrama

# Tabele: (značka, ime, tip, zastavice). Značka je "PK", "FK" ali "".
TABELE = {
    "regija": {
        "naslov": "regija",
        "opomba": "regija in država",
        "skupina": "lokacija",
        "stolpec": 0, "y": 232,
        "vrstice": [
            ("PK", "id_regije", "serial", ""),
            ("", "ime_regije", "text", "NN"),
            ("", "drzava", "char(2)", "NN"),
        ],
        "noge": ["unique (ime_regije, drzava)", "check drzava in ('SI', 'HR')"],
    },
    "lokacija": {
        "naslov": "lokacija",
        "opomba": "hierarhija kraja",
        "skupina": "lokacija",
        "stolpec": 1, "y": 186,
        "vrstice": [
            ("PK", "id_lokacije", "serial", ""),
            ("FK", "id_regije", "→ regija", ""),
            ("", "upravna_enota", "text", ""),
            ("", "obcina", "text", ""),
            ("", "naselje", "text", ""),
            ("", "postna_stevilka", "integer", ""),
        ],
        "noge": ["unique index nad coalesce(…) — NULL ni podvojen"],
    },
    "vrsta_nepremicnine": {
        "naslov": "vrsta_nepremicnine",
        "opomba": "šifrant",
        "skupina": "sifrant",
        "stolpec": 1, "y": 470,
        "vrstice": [
            ("PK", "id_vrste", "serial", ""),
            ("", "ime_vrste", "text", "NN UQ"),
        ],
        "noge": [],
    },
    "vir": {
        "naslov": "vir",
        "opomba": "šifrant",
        "skupina": "sifrant",
        "stolpec": 2, "y": 150,
        "vrstice": [
            ("PK", "id_vira", "serial", ""),
            ("", "ime_vira", "text", "NN UQ"),
            ("", "url_vira", "text", ""),
        ],
        "noge": [],
    },
    "nepremicnina": {
        "naslov": "nepremicnina",
        "opomba": "jedro",
        "skupina": "jedro",
        "stolpec": 2, "y": 322,
        "vrstice": [
            ("PK", "id_nepremicnine", "serial", ""),
            ("FK", "id_vrste", "→ vrsta_nepremicnine", "NN"),
            ("FK", "id_lokacije", "→ lokacija", "NN"),
            ("", "opis", "text", ""),
            ("", "leto_gradnje", "integer", ""),
            ("", "stevilo_sob", "numeric(4,1)", ""),
            ("", "stevilo_sob_opis", "varchar(100)", ""),
            ("", "nadstropje", "varchar(50)", ""),
            ("", "m2", "numeric(10,2)", "NN"),
        ],
        "noge": [],
    },
    "oglas": {
        "naslov": "oglas",
        "opomba": "osrednja tabela",
        "skupina": "oglas",
        "stolpec": 3, "y": 322,
        "vrstice": [
            ("PK", "id_oglasa", "serial", ""),
            ("FK", "id_vira", "→ vir", "NN"),
            ("FK", "id_nepremicnine", "→ nepremicnina", "NN"),
            ("", "zunanji_id", "text", ""),
            ("", "naslov", "text", "NN"),
            ("", "url_oglasa", "text", ""),
            ("", "cena", "numeric(12,2)", "NN"),
            ("", "valuta", "char(3)", "NN"),
            ("", "datum_objave", "date", ""),
            ("", "datum_zajema", "date", "NN"),
        ],
        "noge": ["unique (id_vira, zunanji_id)  →  uvoz je idempotenten",
                 "id_nepremicnine: on delete cascade"],
    },
    "uporabnik": {
        "naslov": "uporabnik",
        "opomba": "prijava v aplikacijo",
        "skupina": "prijava",
        "stolpec": 0, "y": 509,
        "vrstice": [
            ("PK", "uporabnisko_ime", "text", ""),
            ("", "geslo_hash", "text", "NN"),
            ("", "vloga", "text", "NN"),
            ("", "zadnja_prijava", "timestamp", ""),
        ],
        "noge": ["check vloga in ('admin', 'uporabnik')"],
    },
}

# (starš, vrstica starša, otrok, vrstica otroka, delež razmika do navpičnega odseka,
#  ali je tuji ključ lahko NULL)
POVEZAVE = [
    ("regija", 0, "lokacija", 1, 0.5, True),
    ("lokacija", 0, "nepremicnina", 2, 0.5, False),
    ("vrsta_nepremicnine", 0, "nepremicnina", 1, 0.62, False),
    ("vir", 0, "oglas", 1, 0.74, False),
    ("nepremicnina", 0, "oglas", 2, 0.36, False),
]


def sirina_besedila(besedilo, velikost, mono=False, krepko=False):
    """Groba ocena širine niza; namenoma velikodušna, da se besedilo ne prelije."""
    faktor = 0.63 if mono else (0.60 if krepko else 0.565)
    return len(besedilo) * velikost * faktor


def ubezi(besedilo):
    return besedilo.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sirina_tabele(t):
    ime_w = max(sirina_besedila(v[1], 12.5, krepko=bool(v[0])) for v in t["vrstice"])
    tip_w = max(sirina_besedila(v[2], 11.5, mono=True) for v in t["vrstice"])
    zas_w = max(sirina_besedila(v[3], 9.5, krepko=True) for v in t["vrstice"])
    glava_w = sirina_besedila(t["naslov"], 15, krepko=True) + sirina_besedila(t["opomba"], 10) + 26
    noga_w = max([sirina_besedila(n, 10.5) for n in t["noge"]] or [0]) + 2 * ROB_L
    vsebina = ROB_L + 30 + ime_w + 16 + tip_w + (10 + zas_w if zas_w else 0) + ROB_L
    return max(250, vsebina, glava_w + 2 * ROB_L, noga_w)


def visina_tabele(t):
    return GLAVA_H + VRSTICA_H * len(t["vrstice"]) + NOGA_H * len(t["noge"])


def postavi():
    """Vsakemu stolpcu določi x glede na najširšo tabelo v njem."""
    for t in TABELE.values():
        t["w"] = sirina_tabele(t)
        t["h"] = visina_tabele(t)
    x = 58.0
    for stolpec in range(4):
        v_stolpcu = [t for t in TABELE.values() if t["stolpec"] == stolpec]
        w = max(t["w"] for t in v_stolpcu)
        for t in v_stolpcu:
            t["x"] = x
            t["w"] = w          # enaka širina znotraj stolpca je bolj umirjena
        x += w + STOLPEC_GAP
    return x - STOLPEC_GAP


def y_vrstice(t, i):
    return t["y"] + GLAVA_H + VRSTICA_H * i + VRSTICA_H / 2


def zaobljena_pot(tocke, r=12):
    """Pravokotna pot z zaobljenimi vogali skozi dane točke."""
    d = [f"M {tocke[0][0]:.1f} {tocke[0][1]:.1f}"]
    for i in range(1, len(tocke) - 1):
        (x0, y0), (x1, y1), (x2, y2) = tocke[i - 1], tocke[i], tocke[i + 1]
        r1 = min(r, abs(x1 - x0) / 2 + abs(y1 - y0) / 2, abs(x2 - x1) / 2 + abs(y2 - y1) / 2)
        sx = x1 - (r1 if x1 > x0 else -r1 if x1 < x0 else 0)
        sy = y1 - (r1 if y1 > y0 else -r1 if y1 < y0 else 0)
        ex = x1 + (r1 if x2 > x1 else -r1 if x2 < x1 else 0)
        ey = y1 + (r1 if y2 > y1 else -r1 if y2 < y1 else 0)
        d.append(f"L {sx:.1f} {sy:.1f} Q {x1:.1f} {y1:.1f} {ex:.1f} {ey:.1f}")
    d.append(f"L {tocke[-1][0]:.1f} {tocke[-1][1]:.1f}")
    return " ".join(d)


def narisi_tabelo(t):
    x, y, w, h = t["x"], t["y"], t["w"], t["h"]
    barva = BARVE[t["skupina"]]
    s = [f'<g filter="url(#senca)">',
         f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" fill="#FFFFFF" stroke="{ROB}"/>',
         '</g>']

    # naslovna vrstica: zaobljena samo zgoraj
    s.append(f'<path d="M {x} {y+11} A 11 11 0 0 1 {x+11} {y} L {x+w-11} {y} '
             f'A 11 11 0 0 1 {x+w} {y+11} L {x+w} {y+GLAVA_H} L {x} {y+GLAVA_H} Z" fill="{barva}"/>')
    s.append(f'<text x="{x+ROB_L}" y="{y+GLAVA_H/2+5.5}" font-family="{SANS}" font-size="15" '
             f'font-weight="bold" fill="#FFFFFF">{t["naslov"]}</text>')
    s.append(f'<text x="{x+w-ROB_L}" y="{y+GLAVA_H/2+4.5}" font-family="{SANS}" font-size="10" '
             f'fill="#FFFFFF" fill-opacity="0.78" text-anchor="end">{t["opomba"]}</text>')

    kljucev = sum(1 for v in t["vrstice"] if v[0])
    if kljucev:
        s.append(f'<rect x="{x+1}" y="{y+GLAVA_H}" width="{w-2}" height="{VRSTICA_H*kljucev}" '
                 f'fill="{KLJUC_OZADJE}"/>')

    ime_x = x + ROB_L + 30
    tip_x = ime_x + max(sirina_besedila(v[1], 12.5, krepko=bool(v[0])) for v in t["vrstice"]) + 16
    for i, (znacka, ime, tip, zastavice) in enumerate(t["vrstice"]):
        yv = y + GLAVA_H + VRSTICA_H * i
        if i:
            s.append(f'<line x1="{x+1}" y1="{yv}" x2="{x+w-1}" y2="{yv}" stroke="{LOCILO}"/>')
        sredina = yv + VRSTICA_H / 2 + 4
        if znacka:
            oz, tx = ("#FEF3C7", "#92400E") if znacka == "PK" else ("#DBEAFE", "#1D4ED8")
            s.append(f'<rect x="{x+ROB_L}" y="{yv+7}" width="24" height="14" rx="4" fill="{oz}"/>')
            s.append(f'<text x="{x+ROB_L+12}" y="{yv+17.5}" font-family="{SANS}" font-size="9" '
                     f'font-weight="bold" fill="{tx}" text-anchor="middle">{znacka}</text>')
        s.append(f'<text x="{ime_x}" y="{sredina}" font-family="{SANS}" font-size="12.5" '
                 f'font-weight="{"bold" if znacka else "normal"}" fill="{TEKST}">{ime}</text>')
        s.append(f'<text x="{tip_x}" y="{sredina}" font-family="{MONO}" font-size="11.5" '
                 f'fill="{TEKST_TIP}">{ubezi(tip)}</text>')
        if zastavice:
            s.append(f'<text x="{x+w-ROB_L}" y="{sredina}" font-family="{SANS}" font-size="9.5" '
                     f'font-weight="bold" fill="{TEKST_SIB}" text-anchor="end" '
                     f'letter-spacing="0.5">{zastavice}</text>')

    if t["noge"]:
        yn = y + GLAVA_H + VRSTICA_H * len(t["vrstice"])
        hn = NOGA_H * len(t["noge"])
        s.append(f'<path d="M {x} {yn} L {x+w} {yn} L {x+w} {yn+hn-11} '
                 f'A 11 11 0 0 1 {x+w-11} {yn+hn} L {x+11} {yn+hn} '
                 f'A 11 11 0 0 1 {x} {yn+hn-11} Z" fill="{NOGA_OZADJE}"/>')
        s.append(f'<line x1="{x+1}" y1="{yn}" x2="{x+w-1}" y2="{yn}" stroke="{LOCILO}"/>')
        for i, vrsta in enumerate(t["noge"]):
            s.append(f'<text x="{x+ROB_L}" y="{yn+NOGA_H*i+NOGA_H/2+4}" font-family="{SANS}" '
                     f'font-size="10.5" font-style="italic" fill="{TEKST_TIP}">{ubezi(vrsta)}</text>')
    return "\n".join(s)


def narisi_povezavo(stars, i_stars, otrok, i_otrok, delez, nicelna):
    a, b = TABELE[stars], TABELE[otrok]
    x1, y1 = a["x"] + a["w"], y_vrstice(a, i_stars)
    x2, y2 = b["x"], y_vrstice(b, i_otrok)
    razmik = x2 - (a["x"] + a["w"])
    lx = x1 + razmik * delez
    zac, kon = x1 + 26, x2 - 22          # prostor za oznaki kardinalnosti
    tocke = [(zac, y1), (lx, y1), (lx, y2), (kon, y2)] if abs(y1 - y2) > 2 else [(zac, y1), (kon, y2)]

    s = [f'<path d="{zaobljena_pot(tocke)}" fill="none" stroke="{CRTA}" stroke-width="1.6"/>']
    # stran "1": prečna črtica (in krogec, če je tuji ključ lahko NULL)
    s.append(f'<line x1="{x1+13}" y1="{y1-7}" x2="{x1+13}" y2="{y1+7}" stroke="{CRTA}" stroke-width="1.6"/>')
    s.append(f'<line x1="{x1}" y1="{y1}" x2="{x1+26}" y2="{y1}" stroke="{CRTA}" stroke-width="1.6"/>')
    if nicelna:
        s.append(f'<circle cx="{x1+21}" cy="{y1}" r="4" fill="#FFFFFF" stroke="{CRTA}" stroke-width="1.6"/>')
    # stran "N": vranja noga
    s.append(f'<line x1="{x2-22}" y1="{y2}" x2="{x2}" y2="{y2}" stroke="{CRTA}" stroke-width="1.6"/>')
    for dy in (-7, 7):
        s.append(f'<line x1="{x2}" y1="{y2}" x2="{x2-13}" y2="{y2+dy}" stroke="{CRTA}" stroke-width="1.6"/>')
    s.append(f'<circle cx="{x2-18}" cy="{y2}" r="4" fill="#FFFFFF" stroke="{CRTA}" stroke-width="1.6"/>')

    s.append(f'<text x="{x1+30}" y="{y1-9}" font-family="{SANS}" font-size="11" font-weight="bold" '
             f'fill="{TEKST_SIB}">1</text>')
    s.append(f'<text x="{x2-30}" y="{y2-9}" font-family="{SANS}" font-size="11" font-weight="bold" '
             f'fill="{TEKST_SIB}" text-anchor="end">N</text>')
    return "\n".join(s)


PANEL_H = 186   # visina spodnjih dveh okvirjev (legenda, pogled)


def narisi_pogled(x, y, w):
    """Okvir s pojasnilom pogleda oglas_pregled (crtkan rob, ker ni tabela)."""
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{PANEL_H}" rx="11" fill="#FFFFFF" '
         f'stroke="{CRTA}" stroke-dasharray="6 4"/>',
         f'<text x="{x+ROB_L+2}" y="{y+32}" font-family="{SANS}" font-size="15" font-weight="bold" '
         f'fill="{TEKST}">oglas_pregled</text>',
         f'<text x="{x+ROB_L+2+sirina_besedila("oglas_pregled", 15, krepko=True)+12}" y="{y+32}" '
         f'font-family="{SANS}" font-size="10.5" fill="{TEKST_SIB}">pogled (view) – ni tabela</text>']
    for i, vrsta in enumerate([
            "Shranjena poizvedba, ki združi vse tabele okrog oglasa, da nam v Pythonu ni treba",
            "vsakič pisati petih JOIN-ov. Aplikacija bere skoraj vse podatke prek njega."]):
        s.append(f'<text x="{x+ROB_L+2}" y="{y+58+i*18}" font-family="{SANS}" font-size="11.5" '
                 f'fill="{TEKST_TIP}">{vrsta}</text>')

    cip_x = x + ROB_L + 2
    for ime, skupina in [("oglas", "oglas"), ("nepremicnina", "jedro"),
                         ("vrsta_nepremicnine", "sifrant"), ("lokacija", "lokacija"),
                         ("regija", "lokacija"), ("vir", "sifrant")]:
        barva = BARVE[skupina]
        w_cip = sirina_besedila(ime, 10.5, mono=True) + 18
        s.append(f'<rect x="{cip_x}" y="{y+100}" width="{w_cip}" height="20" rx="10" fill="{barva}" '
                 f'fill-opacity="0.12" stroke="{barva}" stroke-opacity="0.35"/>')
        s.append(f'<text x="{cip_x+w_cip/2}" y="{y+114}" font-family="{MONO}" font-size="10.5" '
                 f'fill="{barva}" text-anchor="middle">{ime}</text>')
        cip_x += w_cip + 7

    for i, vrsta in enumerate([
            "from oglas join nepremicnina join vrsta_nepremicnine join lokacija "
            "left join regija join vir",
            "+ izpeljani stolpec  cena_na_m2 = round(cena / nullif(m2, 0), 2)"]):
        s.append(f'<text x="{x+ROB_L+2}" y="{y+146+i*22}" font-family="{MONO}" font-size="11" '
                 f'fill="{TEKST if i else TEKST_TIP}">{ubezi(vrsta)}</text>')
    return "\n".join(s)


def narisi_legendo(x, y, w):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{PANEL_H}" rx="11" fill="#FFFFFF" stroke="{ROB}"/>',
         f'<text x="{x+ROB_L+2}" y="{y+30}" font-family="{SANS}" font-size="11" font-weight="bold" '
         f'fill="{TEKST_SIB}" letter-spacing="1.2">LEGENDA</text>']

    lx = x + ROB_L + 2
    for i, (znacka, opis, oz, tx) in enumerate([
            ("PK", "primarni ključ", "#FEF3C7", "#92400E"),
            ("FK", "tuji ključ", "#DBEAFE", "#1D4ED8")]):
        yy = y + 58 + i * 26
        s.append(f'<rect x="{lx}" y="{yy-11}" width="24" height="14" rx="4" fill="{oz}"/>')
        s.append(f'<text x="{lx+12}" y="{yy-0.5}" font-family="{SANS}" font-size="9" '
                 f'font-weight="bold" fill="{tx}" text-anchor="middle">{znacka}</text>')
        s.append(f'<text x="{lx+34}" y="{yy}" font-family="{SANS}" font-size="11.5" '
                 f'fill="{TEKST_TIP}">{opis}</text>')
    for i, (znacka, opis) in enumerate([("NN", "not null"), ("UQ", "unique")]):
        yy = y + 110 + i * 26
        s.append(f'<text x="{lx+12}" y="{yy}" font-family="{SANS}" font-size="9.5" font-weight="bold" '
                 f'fill="{TEKST_SIB}" text-anchor="middle" letter-spacing="0.5">{znacka}</text>')
        s.append(f'<text x="{lx+34}" y="{yy}" font-family="{SANS}" font-size="11.5" '
                 f'fill="{TEKST_TIP}">{opis}</text>')

    # kardinalnost: ista simbola kot na povezavah
    kx = x + w * 0.36
    s.append(f'<text x="{kx}" y="{y+44}" font-family="{SANS}" font-size="11.5" fill="{TEKST_TIP}">'
             f'ena vrstica šifranta …</text>')
    s.append(f'<line x1="{kx}" y1="{y+62}" x2="{kx+120}" y2="{y+62}" stroke="{CRTA}" stroke-width="1.6"/>')
    s.append(f'<line x1="{kx+14}" y1="{y+55}" x2="{kx+14}" y2="{y+69}" stroke="{CRTA}" stroke-width="1.6"/>')
    for dy in (-7, 7):
        s.append(f'<line x1="{kx+120}" y1="{y+62}" x2="{kx+107}" y2="{y+62+dy}" stroke="{CRTA}" '
                 f'stroke-width="1.6"/>')
    s.append(f'<circle cx="{kx+102}" cy="{y+62}" r="4" fill="#FFFFFF" stroke="{CRTA}" stroke-width="1.6"/>')
    s.append(f'<text x="{kx+132}" y="{y+66}" font-family="{SANS}" font-size="11.5" fill="{TEKST_TIP}">'
             f'… nastopa v nič ali več vrsticah tabele, ki kaže nanjo</text>')

    s.append(f'<line x1="{kx}" y1="{y+100}" x2="{kx+28}" y2="{y+100}" stroke="{CRTA}" stroke-width="1.6"/>')
    s.append(f'<line x1="{kx+7}" y1="{y+93}" x2="{kx+7}" y2="{y+107}" stroke="{CRTA}" stroke-width="1.6"/>')
    s.append(f'<circle cx="{kx+15}" cy="{y+100}" r="4" fill="#FFFFFF" stroke="{CRTA}" stroke-width="1.6"/>')
    s.append(f'<text x="{kx+44}" y="{y+104}" font-family="{SANS}" font-size="11.5" fill="{TEKST_TIP}">'
             f'krogec: tuji ključ je lahko NULL (lokacija brez regije)</text>')
    s.append(f'<text x="{kx}" y="{y+134}" font-family="{SANS}" font-size="11.5" fill="{TEKST_TIP}">'
             f'uporabnik ni povezan z ostalimi tabelami – rabimo ga samo za prijavo</text>')

    # barve glav
    bx = lx
    s.append(f'<text x="{bx}" y="{y+166}" font-family="{SANS}" font-size="11.5" fill="{TEKST_TIP}">'
             f'barva glave:</text>')
    bx += sirina_besedila("barva glave:", 11.5) + 16
    for ime, kljuc in [("šifranti", "sifrant"), ("lokacija", "lokacija"), ("nepremičnine", "jedro"),
                       ("oglasi", "oglas"), ("prijava", "prijava")]:
        s.append(f'<rect x="{bx}" y="{y+156}" width="13" height="13" rx="3" fill="{BARVE[kljuc]}"/>')
        s.append(f'<text x="{bx+19}" y="{y+166}" font-family="{SANS}" font-size="11.5" '
                 f'fill="{TEKST_TIP}">{ime}</text>')
        bx += 19 + sirina_besedila(ime, 11.5) + 24
    return "\n".join(s)


def narisi():
    desni_rob = postavi()
    zadnja_vrsta_y = max(t["y"] + t["h"] for t in TABELE.values())
    pas_y = zadnja_vrsta_y + 46
    sirina = desni_rob + 58
    legenda_w = TABELE["vrsta_nepremicnine"]["x"] + TABELE["vrsta_nepremicnine"]["w"] - 58
    pogled_x = TABELE["vir"]["x"]
    pogled_w = desni_rob - pogled_x

    legenda_svg = narisi_legendo(58, pas_y, legenda_w)
    pogled_svg = narisi_pogled(pogled_x, pas_y, pogled_w)
    visina = pas_y + PANEL_H + 54

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{sirina:.0f}" height="{visina:.0f}" '
         f'viewBox="0 0 {sirina:.0f} {visina:.0f}" font-family="{SANS}">',
         '<defs><filter id="senca" x="-20%" y="-20%" width="140%" height="140%">'
         '<feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0F172A" flood-opacity="0.10"/>'
         '</filter></defs>',
         f'<rect width="{sirina:.0f}" height="{visina:.0f}" fill="#F5F7FA"/>']

    s.append(f'<text x="58" y="62" font-size="25" font-weight="bold" fill="{TEKST}">'
             f'Najem nepremičnin — ER diagram baze</text>')
    s.append(f'<text x="58" y="88" font-size="13" fill="{TEKST_TIP}">'
             f'PostgreSQL · 7 tabel in pogled oglas_pregled · vse povezave so 1 : N</text>')
    s.append(f'<text x="{sirina-58:.0f}" y="62" font-size="12" fill="{TEKST_SIB}" text-anchor="end">'
             f'shema: Data/create_database.sql</text>')
    s.append(f'<text x="{sirina-58:.0f}" y="82" font-size="12" fill="{TEKST_SIB}" text-anchor="end">'
             f'diagram: Data/er_diagram.py</text>')
    s.append(f'<line x1="58" y1="106" x2="{sirina-58:.0f}" y2="106" stroke="{ROB}"/>')

    for p in POVEZAVE:
        s.append(narisi_povezavo(*p))
    for t in TABELE.values():
        s.append(narisi_tabelo(t))
    s.append(legenda_svg)
    s.append(pogled_svg)
    s.append('</svg>')
    return "\n".join(s)


if __name__ == "__main__":
    koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pot = os.path.join(koren, "er-nepremicnine.svg")
    with open(pot, "w", encoding="utf-8") as f:
        f.write(narisi())
    print("zapisano:", pot)
