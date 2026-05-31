import psycopg2, psycopg2.extensions, psycopg2.extras
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
import Data.auth_public as auth
import datetime
import os

from Data.models import Vir, Vrsta_nepremicnine, Lokacija, Nepremicnina, Oglas, OglasDTO, OglasFiltriDTO
from typing import List


class Repository:
    def __init__(self):
        pass
 