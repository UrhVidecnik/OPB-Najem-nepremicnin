"""
Scraper za nepremicnine.net
Pobere vse oglase iz SEARCH_URLS, shrani osnovne podatke v BASIC_CSV, detajle v DETAIL_CSV in na koncu zdruzi v OUTPUT_CSV.

"""

import asyncio
import csv
import os
import random
import re
import sys
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import TimeoutError as PWTimeoutError
from playwright.async_api import async_playwright

load_dotenv()

SEARCH_URLS = [
    url.strip()
    for url in os.getenv("SEARCH_URLS", "").replace("\n", ",").split(",")
    if url.strip()
]
BASIC_CSV = os.getenv("BASIC_CSV", "oglasi_osnovno.csv")
DETAIL_CSV = os.getenv("DETAIL_CSV", "oglasi_lokacije.csv")
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "oglasi_full.csv")
MAX_PAGES = int(os.getenv("MAX_PAGES", "200"))
DETAIL_CONCURRENCY = int(os.getenv("DETAIL_CONCURRENCY", "3"))
DELAY_MIN = float(os.getenv("SCRAPE_DELAY_MIN", "3"))
DELAY_MAX = float(os.getenv("SCRAPE_DELAY_MAX", "6"))
SCRAPE_TIMEOUT_MS = int(os.getenv("SCRAPE_TIMEOUT_MS", "45000"))
SCRAPE_RETRIES = int(os.getenv("SCRAPE_RETRIES", "2"))

BASIC_FIELDS = [
    "id_oglasa", "naslov", "tip_nepremicnine", "stevilo_sob_opis",
    "stevilo_sob", "cena", "valuta", "m2", "leto_gradnje", "nadstropje",
    "opis_kratek", "url_oglasa",
]
DETAIL_FIELDS = [
    "id_oglasa", "opis_poln", "regija", "upravna_enota", "obcina", "naselje",
]
FULL_FIELDS = [
    "id_oglasa", "naslov", "tip_nepremicnine", "stevilo_sob_opis",
    "stevilo_sob", "cena", "valuta", "m2", "leto_gradnje", "nadstropje",
    "opis_kratek", "opis_poln", "regija", "upravna_enota", "obcina",
    "naselje", "url_oglasa",
]


@dataclass
class OglasRaw:
    id_oglasa: Optional[str] = None
    naslov: str = ""
    tip_nepremicnine: str = ""
    stevilo_sob_opis: str = ""
    stevilo_sob: Optional[float] = None
    cena: Optional[float] = None
    valuta: str = ""
    m2: Optional[float] = None
    leto_gradnje: Optional[int] = None
    nadstropje: str = ""
    opis_kratek: str = ""
    url_oglasa: str = ""


ID_RE = re.compile(r"_(\d+)/?$")
ROOM_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*-?\s*sobno", re.IGNORECASE)


def parse_id_from_url(url: str) -> Optional[str]:
    m = ID_RE.search(url)
    return m.group(1) if m else None


def parse_float_si(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.strip().replace(".", "").replace(",", ".")
    m = re.search(r"[\d.]+", text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_stevilo_sob(text: str) -> Optional[float]:
    if not text:
        return None
    m = ROOM_NUM_RE.search(text)
    return parse_float_si(m.group(1)) if m else None


def parse_list_card(card, base_url: str) -> Optional[OglasRaw]:
    link_el = card.select_one("a.url-title-d") or card.select_one("a.url-title-m")
    if not link_el or not link_el.get("href"):
        return None

    href = link_el["href"]
    url_oglasa = href if href.startswith("http") else base_url + href
    og = OglasRaw(url_oglasa=url_oglasa, id_oglasa=parse_id_from_url(url_oglasa))
    if not og.id_oglasa:
        return None

    h2 = link_el.select_one("h2")
    og.naslov = h2.get_text(strip=True) if h2 else link_el.get("title", "").strip()

    tip_el = card.select_one("span.font-roboto")
    if tip_el:
        tip_text = tip_el.get_text(" ", strip=True).split(":", 1)[-1].strip()
        deli = [d.strip() for d in tip_text.split(",")]
        if deli:
            og.tip_nepremicnine = deli[0]

    sobe_el = card.select_one("span.tipi")
    if sobe_el:
        og.stevilo_sob_opis = sobe_el.get_text(strip=True)
        og.stevilo_sob = parse_stevilo_sob(og.stevilo_sob_opis)

    price_el = card.select_one('meta[itemprop="price"]')
    if price_el and price_el.get("content"):
        try:
            og.cena = float(price_el["content"])
        except ValueError:
            pass

    curr_el = card.select_one('meta[itemprop="priceCurrency"]')
    if curr_el and curr_el.get("content"):
        og.valuta = curr_el["content"]

    desc_el = card.select_one('p[itemprop="description"]')
    if desc_el:
        og.opis_kratek = desc_el.get_text(strip=True)

    for li in card.select('ul[itemprop="disambiguatingDescription"] li'):
        img = li.select_one("img")
        src = (img.get("src") or "") if img else ""
        text = li.get_text(strip=True)
        if "velikost" in src:
            og.m2 = parse_float_si(text)
        elif "leto" in src:
            digits = re.sub(r"\D", "", text)
            if digits:
                og.leto_gradnje = int(digits)
        elif "nadstropje" in src:
            og.nadstropje = text

    return og


async def fetch_list_page(browser, url: str) -> list[OglasRaw]:
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    page = await browser.new_page()
    page.set_default_navigation_timeout(SCRAPE_TIMEOUT_MS)
    try:
        await page.goto(url, timeout=SCRAPE_TIMEOUT_MS, wait_until="domcontentloaded")
        try:
            # Cakamo na konkreten element namesto na "networkidle", ker
            # oglasi/sledilni skripti na tej strani mrezo drzijo aktivno
            # skoraj neskoncno - networkidle skoraj vedno odpove po 45s,
            # čeprav so oglasi ze zdavnaj naloženi.
            await page.wait_for_selector("div.property-box", timeout=SCRAPE_TIMEOUT_MS)
        except PWTimeoutError:
            # Morda je stran res prazna (zadnja stran paginacije) - to
            # preverimo spodaj glede na dejansko vsebino, ne vržemo napake.
            pass
        html = await page.content()
    finally:
        await page.close()

    soup = BeautifulSoup(html, "html.parser")
    result = []
    for card in soup.select("div.property-box"):
        og = parse_list_card(card, base_url)
        if og:
            result.append(og)
    return result


MAX_CONSECUTIVE_PAGE_ERRORS = 5


async def scrape_search_all_pages(browser, search_url: str) -> dict[str, OglasRaw]:
    if not search_url.endswith("/"):
        search_url += "/"

    collected: dict[str, OglasRaw] = {}
    page_number = 1
    consecutive_errors = 0

    while page_number <= MAX_PAGES:
        target_url = search_url if page_number == 1 else f"{search_url}{page_number}/"
        print(f"[seznam] stran {page_number}: {target_url}")

        items: list[OglasRaw] = []
        page_had_error = False

        for attempt in range(1, SCRAPE_RETRIES + 1):
            try:
                items = await fetch_list_page(browser, target_url)
                page_had_error = False
                break
            except PWTimeoutError as exc:
                print(f"  Timeout (poskus {attempt}/{SCRAPE_RETRIES}): {exc}")
                page_had_error = True
                if attempt < SCRAPE_RETRIES:
                    await asyncio.sleep(2)
            except Exception as exc:
                print(f"  Napaka na {target_url} (poskus {attempt}/{SCRAPE_RETRIES}): {exc}")
                page_had_error = True
                if attempt < SCRAPE_RETRIES:
                    await asyncio.sleep(2)

        if page_had_error:
            # Tehnicna napaka - to NI zanesljiv znak, da so oglasi koncani.
            # Stran preskocimo in poskusimo naslednjo, a stejemo zaporedne
            # napake, da se ne zataknemo v neskoncno zanko na resnicno
            # nedosegljivem URL-ju.
            consecutive_errors += 1
            print(f"  Stran {page_number} ni uspela ({consecutive_errors}/"
                  f"{MAX_CONSECUTIVE_PAGE_ERRORS} zaporednih napak) - poskusam naslednjo stran.")
            if consecutive_errors >= MAX_CONSECUTIVE_PAGE_ERRORS:
                print("  Prevec zaporednih napak - ustavljam paginacijo za ta URL.")
                break
            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            page_number += 1
            continue

        consecutive_errors = 0

        if not items:
            print(f"  Stran {page_number} uspesno nalozena, a prazna - konec paginacije za ta URL.")
            break

        for og in items:
            collected[og.id_oglasa] = og

        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        page_number += 1

    return collected


def write_basic_csv(items: dict[str, OglasRaw], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BASIC_FIELDS)
        writer.writeheader()
        for og in items.values():
            writer.writerow({k: getattr(og, k) for k in BASIC_FIELDS})
    print(f"[seznam] Zapisano {len(items)} oglasov v {path}")


def load_ids_from_csv(path: str, id_field: str = "id_oglasa") -> set[str]:
    if not os.path.exists(path):
        return set()
    ids = set()
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get(id_field):
                ids.add(row[id_field])
    return ids


def load_basic_rows(path: str) -> dict[str, dict]:
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("id_oglasa"):
                rows[row["id_oglasa"]] = row
    return rows


def parse_detail_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out = {"opis_poln": "", "regija": "", "upravna_enota": "", "obcina": "", "naselje": ""}

    desc_container = soup.select_one('#desc div[itemprop="disambiguatingDescription"]')
    if desc_container:
        paragraphs = [p.get_text(" ", strip=True) for p in desc_container.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        out["opis_poln"] = "\n".join(paragraphs) if paragraphs else desc_container.get_text(" ", strip=True)

    loc_container = soup.select_one("#location-map div.more_info")
    if loc_container:
        loc_text = loc_container.get_text(" ", strip=True)
        for chunk in loc_text.split("|"):
            if ":" not in chunk:
                continue
            key, _, value = chunk.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key == "regija":
                out["regija"] = value
            elif key == "upravna enota":
                out["upravna_enota"] = value
            elif key in ("občina", "obcina"):
                out["obcina"] = value
            elif key == "naselje":
                out["naselje"] = value

    return out


class DetailWriter:
    """Odpre DETAIL_CSV enkrat, pise (in flush-a) po eno vrstico naenkrat."""

    def __init__(self, path: str):
        file_exists = os.path.exists(path)
        self._f = open(path, "a", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._f, fieldnames=DETAIL_FIELDS)
        if not file_exists:
            self._writer.writeheader()
            self._f.flush()
        self._lock = asyncio.Lock()

    async def write(self, row: dict) -> None:
        async with self._lock:
            self._writer.writerow(row)
            self._f.flush()
            os.fsync(self._f.fileno())

    def close(self) -> None:
        self._f.close()


async def fetch_and_write_detail(browser, og_id: str, url: str, semaphore: asyncio.Semaphore,
                                  writer: DetailWriter, counters: dict) -> None:
    """Popolnoma zascitena naloga - noben izjemek tu ne sme podreti glavnega toka."""
    async with semaphore:
        try:
            page = None
            html = None
            for attempt in range(1, SCRAPE_RETRIES + 1):
                try:
                    page = await browser.new_page()
                    page.set_default_navigation_timeout(SCRAPE_TIMEOUT_MS)
                    await page.goto(url, timeout=SCRAPE_TIMEOUT_MS, wait_until="domcontentloaded")
                    try:
                        await page.wait_for_selector("#location-map .more_info", timeout=SCRAPE_TIMEOUT_MS)
                    except PWTimeoutError:
                        pass  # vseeno poberemo, kar je - glej parse_detail_html spodaj
                    html = await page.content()
                    break
                except PWTimeoutError as exc:
                    print(f"  [detajl] Timeout {og_id} (poskus {attempt}/{SCRAPE_RETRIES}): {exc}")
                    if attempt < SCRAPE_RETRIES:
                        await asyncio.sleep(2)
                except Exception as exc:
                    print(f"  [detajl] Napaka pri nalaganju {og_id}: {exc}")
                    break
                finally:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                        page = None

            row = {"id_oglasa": og_id, "opis_poln": "", "regija": "",
                   "upravna_enota": "", "obcina": "", "naselje": ""}
            if html:
                try:
                    parsed = parse_detail_html(html)
                    row.update(parsed)
                except Exception as exc:
                    print(f"  [detajl] Napaka pri parsanju {og_id}: {exc}")

            await writer.write(row)
            counters["done"] += 1
            if counters["done"] % 10 == 0:
                print(f"[detajl] {counters['done']}/{counters['total']} obdelanih ...")

        except Exception as exc:
            # Absolutno zadnja varovalka - ta oglas spodleti, ostali se nadaljujejo.
            print(f"  [detajl] NEPRICAKOVANA napaka pri {og_id}: {exc}")
        finally:
            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def merge_csvs() -> None:
    basic_rows = load_basic_rows(BASIC_CSV)
    detail_rows = {}
    if os.path.exists(DETAIL_CSV):
        with open(DETAIL_CSV, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("id_oglasa"):
                    detail_rows[row["id_oglasa"]] = row

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FULL_FIELDS)
        writer.writeheader()
        for og_id, basic in basic_rows.items():
            detail = detail_rows.get(og_id, {})
            row = {k: basic.get(k, "") for k in BASIC_FIELDS}
            row.update({k: detail.get(k, "") for k in DETAIL_FIELDS if k != "id_oglasa"})
            writer.writerow(row)

    print(f"[zdruzevanje] {OUTPUT_CSV}: {len(basic_rows)} vrstic "
          f"({len(detail_rows)} z izpolnjenimi detajli).")


async def main():
    if not SEARCH_URLS:
        print("Nastavi SEARCH_URLS v .env.")
        return

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)

        # FAZA 1: seznam
        all_items: dict[str, OglasRaw] = {}
        for search_url in SEARCH_URLS:
            items = await scrape_search_all_pages(browser, search_url)
            all_items.update(items)
            print(f"[seznam] {search_url}: skupaj {len(items)} oglasov")

        write_basic_csv(all_items, BASIC_CSV)

        # FAZA 2: detajl - preskoci ze pobrane
        already_done = load_ids_from_csv(DETAIL_CSV)
        to_process = {oid: og for oid, og in all_items.items() if oid not in already_done}
        print(f"[detajl] Ze pobranih detajlov: {len(already_done)}. "
              f"Manjka se {len(to_process)} od skupno {len(all_items)}.")

        writer = DetailWriter(DETAIL_CSV)
        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)
        counters = {"done": 0, "total": len(to_process)}

        tasks = [
            asyncio.create_task(
                fetch_and_write_detail(browser, oid, og.url_oglasa, semaphore, writer, counters)
            )
            for oid, og in to_process.items()
        ]
        if tasks:
            # return_exceptions=True: tudi ce bi kaksna naloga vseeno vrgla
            # izjemek mimo notranje zascite, ostale naloge to ne prizadene.
            await asyncio.gather(*tasks, return_exceptions=True)

        writer.close()
        await browser.close()

    merge_csvs()
    print("Koncano.")


if __name__ == "__main__":
    if "--merge" in sys.argv:
        merge_csvs()
    else:
        asyncio.run(main())