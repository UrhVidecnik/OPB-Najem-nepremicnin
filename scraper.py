"""
Scraper za nepremicnine.net – verzija s Playwright
Pobira oglase za najem nepremičnin in jih shrani v CSV datoteke,
ki ustrezajo strukturi baze (vir, lokacija, vrsta_nepremicnine, nepremicnina, oglas).

Namestitev:
    pip install playwright
    playwright install chromium

Zagon:
    python scraper.py

Nastavi REGIJE in VRSTE po želji, ter MAX_STRANI za vsako kombinacijo.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup
import csv, time, re, os
from datetime import date
from dataclasses import dataclass
from typing import Optional

# ─── NASTAVITVE ───────────────────────────────────────────────────────────────

MAX_STRANI   = 3       # strani po kombinaciji (1 stran ≈ 25 oglasov)
ZAMIK        = 2.0     # sekunde med zahtevki
ZAMIK_STRAN  = 3.0     # sekunde po nalaganju vsake strani

OUTPUT_DIR   = "Data/csv"
os.makedirs(OUTPUT_DIR, exist_ok=True)

REGIJE = [
    "ljubljana-mesto",
    "ljubljana-okolica",
    "gorenjska",
    "maribor",
    "primorska",
]

VRSTE_MAP = {
    "stanovanje": "Stanovanje",
    "hisa":       "Hiša",
    "garsonjera": "Garsonjera",
    "soba":       "Soba",
}

# ─── PODATKOVNE STRUKTURE ─────────────────────────────────────────────────────

@dataclass
class SurovjOglas:
    naslov:            str            = ""
    url_oglasa:        Optional[str]  = None
    cena:              Optional[float]= None
    datum_objave:      Optional[str]  = None
    m2:                Optional[float]= None
    stevilo_sob:       Optional[float]= None
    nadstropje:        Optional[str]  = None
    leto_gradnje:      Optional[int]  = None
    opis:              Optional[str]  = None
    lokacija_ime:      str            = ""
    lokacija_soseska:  Optional[str]  = None
    postna_stevilka:   Optional[int]  = None
    vrsta_ime:         str            = ""
    regija:            str            = ""

# ─── POMOŽNE FUNKCIJE ─────────────────────────────────────────────────────────

def razcleni_ceno(tekst: str) -> Optional[float]:
    tekst = tekst.replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", tekst)
    if m:
        try: return float(m.group(1))
        except: pass
    return None

def razcleni_m2(tekst: str) -> Optional[float]:
    tekst = tekst.replace("\xa0", "").replace(" ", "")
    m = re.search(r"([\d]+[.,]?[\d]*)\s*m", tekst, re.IGNORECASE)
    if m:
        try: return float(m.group(1).replace(",", "."))
        except: pass
    return None

def razcleni_sobe(tekst: str) -> Optional[float]:
    m = re.search(r"(\d+[.,]?\d*)", tekst)
    if m:
        try: return float(m.group(1).replace(",", "."))
        except: pass
    return None

def razcleni_postno(tekst: str) -> Optional[int]:
    m = re.search(r"\b(\d{4})\b", tekst)
    return int(m.group(1)) if m else None

def razcleni_leto(tekst: str) -> Optional[int]:
    m = re.search(r"\b(1[89]\d{2}|20[0-2]\d)\b", tekst)
    return int(m.group(1)) if m else None

def razcleni_datum(tekst: str) -> Optional[str]:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", tekst)
    if m: return m.group(1)
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", tekst)
    if m: return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None

# ─── SCRAPING SEZNAMA (ena stran) ─────────────────────────────────────────────

def scrape_seznam(page, url: str, vrsta_ime: str, regija: str) -> list[SurovjOglas]:
    """Odpre stran seznama z Playwrightom in izvleče kartice oglasov."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(int(ZAMIK_STRAN * 1000))
    except PWTimeout:
        print(f"  [!] Timeout za {url}")
        return []

    # Zapri morebitni cookie banner
    for sel in ["button:has-text('Sprejmi')", "button:has-text('Strinjam')",
                "#onetrust-accept-btn-handler", ".cc-accept"]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(500)
                break
        except:
            pass

    soup = BeautifulSoup(page.content(), "html.parser")

    # Kartice oglasov — nepremicnine.net uporablja .entity-body znotraj article
    kartice = soup.select("article.single-result")
    if not kartice:
        kartice = soup.select(".entity-body")
    print(f"    Najdenih kartic: {len(kartice)}")

    oglasi = []
    for k in kartice:
        og = SurovjOglas(vrsta_ime=vrsta_ime, regija=regija)

        # Naslov
        el = k.select_one("h3.entity-title, .entity-title")
        if el: og.naslov = el.get_text(strip=True)[:500]

        # URL
        a = k.select_one("a.entity-description-title, a[href*='/oglas/']")
        if not a: a = k.select_one("a[href]")
        if a:
            href = a.get("href", "")
            og.url_oglasa = href if href.startswith("http") else "https://www.nepremicnine.net" + href

        # Cena
        el = k.select_one(".price-box")
        if el: og.cena = razcleni_ceno(el.get_text())

        # Lokacija
        el = k.select_one(".entity-description-main")
        if el:
            lok = el.get_text(strip=True)
            deli = [d.strip() for d in lok.split(",")]
            og.lokacija_ime = deli[0][:200] if deli else regija
            if len(deli) > 1:
                og.lokacija_soseska = deli[1][:200]
            og.postna_stevilka = razcleni_postno(lok)

        # m² — v opisu lastnosti
        for el in k.select(".entity-description-features li, .features-list li"):
            txt = el.get_text(strip=True)
            if "m²" in txt or "m2" in txt.lower():
                og.m2 = razcleni_m2(txt)
            elif "sob" in txt.lower() and og.stevilo_sob is None:
                og.stevilo_sob = razcleni_sobe(txt)

        # Datum
        el = k.select_one("time, .datum, [class*='date']")
        if el:
            dt = el.get("datetime", "") or el.get_text(strip=True)
            og.datum_objave = razcleni_datum(dt)
        if not og.datum_objave:
            og.datum_objave = date.today().isoformat()

        if og.naslov or og.url_oglasa:
            oglasi.append(og)

    return oglasi

# ─── SCRAPING PODROBNE STRANI ──────────────────────────────────────────────────

def scrape_podrobnosti(page, og: SurovjOglas) -> SurovjOglas:
    """Obišče stran posameznega oglasa in dopolni manjkajoče podatke."""
    if not og.url_oglasa:
        return og
    try:
        page.goto(og.url_oglasa, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(int(ZAMIK * 1000))
    except PWTimeout:
        return og

    soup = BeautifulSoup(page.content(), "html.parser")

    # Opis
    el = soup.select_one(".description-value, [class*='opis'], .full-description")
    if el and not og.opis:
        og.opis = el.get_text(separator=" ", strip=True)[:2000]

    # Tabela lastnosti
    for vrstica in soup.select("table.features-table tr, .features-list li"):
        tds = vrstica.select("td, th")
        if len(tds) >= 2:
            kljuc = tds[0].get_text(strip=True).lower()
            vred  = tds[1].get_text(strip=True)
        else:
            tekst = vrstica.get_text(separator=":", strip=True)
            if ":" not in tekst: continue
            kljuc, _, vred = tekst.partition(":")
            kljuc = kljuc.lower()

        if ("m²" in kljuc or "površina" in kljuc or "m2" in kljuc) and og.m2 is None:
            og.m2 = razcleni_m2(vred)
        elif "sob" in kljuc and og.stevilo_sob is None:
            og.stevilo_sob = razcleni_sobe(vred)
        elif "nadstropje" in kljuc and og.nadstropje is None:
            og.nadstropje = vred.strip()[:50]
        elif "leto" in kljuc and og.leto_gradnje is None:
            og.leto_gradnje = razcleni_leto(vred)
        elif ("cena" in kljuc or "najemnina" in kljuc) and og.cena is None:
            og.cena = razcleni_ceno(vred)

    # m² iz naslova/opisa kot fallback
    if og.m2 is None and og.naslov:
        og.m2 = razcleni_m2(og.naslov)

    # Lokacija kot fallback
    if not og.lokacija_ime:
        el = soup.select_one(".bread-crumb, [class*='locat']")
        if el:
            og.lokacija_ime = el.get_text(strip=True).split(">")[-1].strip()[:200]

    return og

# ─── GENERIRANJE CSV ───────────────────────────────────────────────────────────

def generiraj_csv(oglasi: list[SurovjOglas]):
    # 1. VIR
    with open(f"{OUTPUT_DIR}/vir.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_vira", "ime_vira", "url_vira"])
        w.writeheader()
        w.writerow({"id_vira": 1, "ime_vira": "nepremicnine.net", "url_vira": "https://www.nepremicnine.net"})
    print("  vir.csv – 1 vrstica")

    # 2. VRSTA_NEPREMICNINE
    vrste_set = sorted({og.vrsta_ime for og in oglasi if og.vrsta_ime})
    vrste_id  = {v: i+1 for i, v in enumerate(vrste_set)}
    with open(f"{OUTPUT_DIR}/vrsta_nepremicnine.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_vrste", "ime_vrste"])
        w.writeheader()
        for ime, iid in vrste_id.items():
            w.writerow({"id_vrste": iid, "ime_vrste": ime})
    print(f"  vrsta_nepremicnine.csv – {len(vrste_id)} vrstic")

    # 3. LOKACIJA
    lok_map: dict[tuple, int] = {}
    lokacije = []
    lok_ctr = 1
    for og in oglasi:
        k = (og.lokacija_ime or "", og.regija or "", og.lokacija_soseska or "", og.postna_stevilka)
        if k not in lok_map:
            lok_map[k] = lok_ctr
            lokacije.append({
                "id_lokacije":    lok_ctr,
                "ime":            og.lokacija_ime or og.regija or "Neznano",
                "regija":         og.regija or "",
                "soseska":        og.lokacija_soseska or "",
                "postna_stevilka": og.postna_stevilka or "",
            })
            lok_ctr += 1
    with open(f"{OUTPUT_DIR}/lokacija.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_lokacije", "ime", "regija", "soseska", "postna_stevilka"])
        w.writeheader(); w.writerows(lokacije)
    print(f"  lokacija.csv – {len(lokacije)} vrstic")

    # 4. NEPREMICNINA + 5. OGLAS
    nep_vrstice, oglas_vrstice = [], []
    nep_ctr, oglas_ctr = 1, 1

    for og in oglasi:
        m2 = og.m2 if og.m2 and og.m2 > 0 else None
        if m2 is None: continue
        if og.cena is None or og.cena < 0: continue

        lok_k = (og.lokacija_ime or "", og.regija or "", og.lokacija_soseska or "", og.postna_stevilka)
        id_lok   = lok_map.get(lok_k, 1)
        id_vrste = vrste_id.get(og.vrsta_ime, 1)

        nep_vrstice.append({
            "id_nepremicnine": nep_ctr,
            "id_vrste":        id_vrste,
            "id_lokacije":     id_lok,
            "opis":            (og.opis or "").replace("\n", " ")[:1000],
            "leto_gradnje":    og.leto_gradnje or "",
            "stevilo_sob":     og.stevilo_sob or "",
            "nadstropje":      og.nadstropje or "",
            "m2":              m2,
        })
        oglas_vrstice.append({
            "id_oglasa":       oglas_ctr,
            "id_vira":         1,
            "id_nepremicnine": nep_ctr,
            "naslov":          (og.naslov or "Brez naslova")[:500],
            "url_oglasa":      og.url_oglasa or "",
            "cena":            og.cena,
            "datum_objave":    og.datum_objave or date.today().isoformat(),
        })
        nep_ctr += 1; oglas_ctr += 1

    with open(f"{OUTPUT_DIR}/nepremicnina.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_nepremicnine","id_vrste","id_lokacije",
                                           "opis","leto_gradnje","stevilo_sob","nadstropje","m2"])
        w.writeheader(); w.writerows(nep_vrstice)
    print(f"  nepremicnina.csv – {len(nep_vrstice)} vrstic")

    with open(f"{OUTPUT_DIR}/oglas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_oglasa","id_vira","id_nepremicnine",
                                           "naslov","url_oglasa","cena","datum_objave"])
        w.writeheader(); w.writerows(oglas_vrstice)
    print(f"  oglas.csv – {len(oglas_vrstice)} vrstic")

    print(f"\nVse datoteke shranjene v: {OUTPUT_DIR}/")
    print("\n── UVOZ V BAZO (psql) ──────────────────────────────────────────────")
    for tabela, csv_ime in [
        ("vir", "vir.csv"),
        ("vrsta_nepremicnine", "vrsta_nepremicnine.csv"),
        ("lokacija", "lokacija.csv"),
        ("nepremicnina(id_nepremicnine,id_vrste,id_lokacije,opis,leto_gradnje,stevilo_sob,nadstropje,m2)", "nepremicnina.csv"),
        ("oglas", "oglas.csv"),
    ]:
        print(f"  \\copy {tabela} FROM 'Data/csv/{csv_ime}' CSV HEADER;")
    print("\n── PONASTAVI ZAPOREDJA ─────────────────────────────────────────────")
    for seq, tabela, stolpec in [
        ("vir_id_vira_seq", "vir", "id_vira"),
        ("lokacija_id_lokacije_seq", "lokacija", "id_lokacije"),
        ("vrsta_nepremicnine_id_vrste_seq", "vrsta_nepremicnine", "id_vrste"),
        ("nepremicnina_id_nepremicnine_seq", "nepremicnina", "id_nepremicnine"),
        ("oglas_id_oglasa_seq", "oglas", "id_oglasa"),
    ]:
        print(f"  SELECT setval('{seq}', (SELECT MAX({stolpec}) FROM {tabela}));")

# ─── GLAVNA FUNKCIJA ───────────────────────────────────────────────────────────

def main():
    vse_surovo: list[SurovjOglas] = []

    print("=== Začenjam scraping nepremicnine.net (Playwright) ===\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="sl-SI",
        )
        # Skrij znake avtomatizacije
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = ctx.new_page()

        for vrsta_url, vrsta_ime in VRSTE_MAP.items():
            for regija in REGIJE:
                for stran in range(1, MAX_STRANI + 1):
                    url = (
                        f"https://www.nepremicnine.net/oglasi-oddaja/"
                        f"{regija}/{vrsta_url}/{stran}/"
                    )
                    print(f"[{vrsta_ime}] {regija} – stran {stran}: {url}")
                    oglasi = scrape_seznam(page, url, vrsta_ime, regija)

                    for i, og in enumerate(oglasi):
                        print(f"  ({i+1}/{len(oglasi)}) {og.url_oglasa}")
                        og = scrape_podrobnosti(page, og)
                        vse_surovo.append(og)
                        time.sleep(ZAMIK)

                    time.sleep(ZAMIK_STRAN)

                    if not oglasi:
                        print("  -> Ni oglasov, končujem to kombinacijo.")
                        break

        browser.close()

    print(f"\nSkupaj pobranih oglasov: {len(vse_surovo)}")
    print("Generiram CSV datoteke...\n")
    generiraj_csv(vse_surovo)


if __name__ == "__main__":
    main()