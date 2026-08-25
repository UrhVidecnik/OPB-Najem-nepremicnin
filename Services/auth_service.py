"""
============================================================================
 OPB – Najem nepremičnin
 Datoteka: Services/auth_service.py

 PRIJAVA IN REGISTRACIJA uporabnikov.

 ZAKAJ bcrypt in ne navadno geslo?
   Če bi gesla shranili v čistopisu, bi vsak, ki pride do baze, videl
   gesla vseh uporabnikov. Zato shranimo samo ZGOŠČENO vrednost (hash).
   Iz hasha gesla ni mogoče izračunati nazaj; ob prijavi vpisano geslo
   zgostimo znova in primerjamo hasha.

 ZAKAJ prav bcrypt?
   Namenoma je POČASEN in vsakemu geslu doda naključno "sol" (salt).
   Zato dve enaki gesli dasta različna hasha, napad s slovarjem pa je
   milijonkrat dražji kot pri npr. MD5.
============================================================================
"""

from typing import List, Optional

import bcrypt

from Data.models import Uporabnik
from Data.repository import Repository

# Najkrajše sprejemljivo geslo.
MIN_DOLZINA_GESLA = 5


class AuthService:
    """Prijava, registracija in preverjanje vlog."""

    def __init__(self, repository: Optional[Repository] = None):
        self.repository = repository or Repository()

    # ── Pomožne metode za gesla ─────────────────────────────────────────────

    @staticmethod
    def zgosti_geslo(geslo: str) -> str:
        """Geslo -> bcrypt hash (niz, ki ga shranimo v bazo).

        bcrypt dela z bajti, zato .encode() pred in .decode() po.
        gensalt() vsakič ustvari novo naključno sol.
        """
        return bcrypt.hashpw(geslo.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def preveri_geslo(geslo: str, hash_iz_baze: str) -> bool:
        """Ali vpisano geslo ustreza shranjenemu hashu?"""
        try:
            return bcrypt.checkpw(geslo.encode("utf-8"), hash_iz_baze.encode("utf-8"))
        except (ValueError, TypeError):
            # Pokvarjen ali prazen hash v bazi -> prijava pač ne uspe.
            return False

    # ── Registracija ────────────────────────────────────────────────────────

    def obstaja_uporabnik(self, uporabnisko_ime: str) -> bool:
        if not uporabnisko_ime:
            return False
        return self.repository.dobi_uporabnika(uporabnisko_ime.strip()) is not None

    def registriraj(
        self, uporabnisko_ime: str, geslo: str, geslo_ponovno: Optional[str] = None,
        vloga: str = "uporabnik",
    ) -> Uporabnik:
        """Ustvari novega uporabnika. Ob napaki vrže ValueError s sporočilom."""
        uporabnisko_ime = (uporabnisko_ime or "").strip()

        if not uporabnisko_ime:
            raise ValueError("Uporabniško ime je obvezno.")
        if len(uporabnisko_ime) < 3:
            raise ValueError("Uporabniško ime mora imeti vsaj 3 znake.")
        if len(uporabnisko_ime) > 50:
            raise ValueError("Uporabniško ime je predolgo (največ 50 znakov).")
        if not geslo:
            raise ValueError("Geslo je obvezno.")
        if len(geslo) < MIN_DOLZINA_GESLA:
            raise ValueError(f"Geslo mora imeti vsaj {MIN_DOLZINA_GESLA} znakov.")
        if geslo_ponovno is not None and geslo != geslo_ponovno:
            raise ValueError("Gesli se ne ujemata.")
        if vloga not in ("admin", "uporabnik"):
            raise ValueError("Neveljavna vloga.")
        if self.obstaja_uporabnik(uporabnisko_ime):
            raise ValueError("Uporabnik s tem imenom že obstaja.")

        uporabnik = Uporabnik(
            uporabnisko_ime=uporabnisko_ime,
            geslo_hash=self.zgosti_geslo(geslo),
            vloga=vloga,
        )
        return self.repository.dodaj_uporabnika(uporabnik)

    # ── Prijava ─────────────────────────────────────────────────────────────

    def prijavi(self, uporabnisko_ime: str, geslo: str) -> Optional[Uporabnik]:
        """Vrne Uporabnika ob uspešni prijavi, sicer None.

        Namenoma NE povemo, ali je bilo napačno uporabniško ime ali geslo –
        s tem bi napadalcu razkrili, katera imena v bazi obstajajo.
        """
        if not uporabnisko_ime or not geslo:
            return None

        uporabnik = self.repository.dobi_uporabnika(uporabnisko_ime.strip())
        if uporabnik is None:
            return None
        if not self.preveri_geslo(geslo, uporabnik.geslo_hash):
            return None

        # Zabeležimo čas prijave. Če to spodleti (npr. bralni dostop),
        # prijava vseeno uspe – gre le za dodatek.
        try:
            self.repository.zabelezi_prijavo(uporabnik.uporabnisko_ime)
        except Exception:
            self.repository.conn.rollback()

        return uporabnik

    # ── Ostalo ──────────────────────────────────────────────────────────────

    def seznam_uporabnikov(self) -> List[Uporabnik]:
        return self.repository.seznam_uporabnikov()

    def je_admin(self, uporabnisko_ime: Optional[str]) -> bool:
        """Ali ima ta uporabnik vlogo 'admin'?

        POZOR: vlogo vedno preberemo IZ BAZE, nikoli iz piškotka.
        Piškotek je pri uporabniku v brskalniku in bi ga znal spremeniti;
        baza je edini vir resnice o tem, kdo je skrbnik.
        """
        if not uporabnisko_ime:
            return False
        uporabnik = self.repository.dobi_uporabnika(uporabnisko_ime)
        return uporabnik is not None and uporabnik.je_admin

    # ── Upravljanje vlog ────────────────────────────────────────────────────

    def nastavi_vlogo(self, uporabnisko_ime: str, vloga: str) -> Uporabnik:
        """Uporabniku nastavi vlogo. Ob napaki vrže ValueError.

        Uporablja jo skripta nastavi_admina.py.
        """
        uporabnisko_ime = (uporabnisko_ime or "").strip()
        if not uporabnisko_ime:
            raise ValueError("Uporabniško ime je obvezno.")
        if vloga not in ("admin", "uporabnik"):
            raise ValueError("Neveljavna vloga (dovoljeni sta 'admin' in 'uporabnik').")

        uporabnik = self.repository.nastavi_vlogo(uporabnisko_ime, vloga)
        if uporabnik is None:
            raise ValueError(f"Uporabnika '{uporabnisko_ime}' ni v bazi.")
        return uporabnik

    def povisaj_v_admina(self, uporabnisko_ime: str) -> Uporabnik:
        return self.nastavi_vlogo(uporabnisko_ime, "admin")

    def odvzemi_admina(self, uporabnisko_ime: str) -> Uporabnik:
        return self.nastavi_vlogo(uporabnisko_ime, "uporabnik")
