# Cargamos las librerías necesarias
import re
import time
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from utilities import leer_csv, escribir_csv


# Genera una raíz normalizada del título para detectar duplicados entre versiones de la misma canción
def raiz_canonica(titulo):
    # Cortamos en el primer paréntesis, corchete o guión que venga precedido por un espacio
    match = re.search(r"\s[\(\[\-]", titulo)
    if match:
        titulo = titulo[:match.start()]

    t = titulo.lower().strip()
    # Nos quedamos solo con letras y números para normalizar la comparación
    t = re.sub(r"[^a-z0-9\s]", "", t)
    return " ".join(t.split())


# Headers para las peticiones a letras.com
_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}

# Cache del índice alfabético de artistas para no repetir peticiones a la misma inicial
_cache_indices = {}


# Extrae la letra de una canción desde su URL en letras.com
def extraer_letra(url):
    response = requests.get(url, headers=_headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # El contenedor de la letra puede tener dos clases distintas según la versión de la página
    container = soup.find("div", class_="lyric-original") or soup.find("div", class_="cnt-letra")

    # Sacamos cada párrafo por separado y los unimos con doble salto de línea para preservar las estrofas
    if container is not None:
        parrafos = [p.get_text(separator="\n", strip=True) for p in container.find_all("p")]
        return "\n\n".join(parrafos) if parrafos else container.get_text(separator="\n", strip=True)

    return None


# Busca un artista por nombre en el índice alfabético de letras.com y devuelve las URLs candidatas
def buscar_artista_scraping(nombre):
    letra = nombre[0].upper()

    if letra not in _cache_indices:
        url = f"https://www.letras.com/letra/{letra}/artistas.html"
        response = requests.get(url, headers=_headers, timeout=15)
        response.raise_for_status()
        _cache_indices[letra] = BeautifulSoup(response.text, "html.parser")

    soup = _cache_indices[letra]
    base = "https://www.letras.com"

    return [base + a["href"] for a in soup.find_all("a", href=True)
            if a.get_text(strip=True).lower() == nombre.lower()]


# Busca una canción concreta dentro de un artista y devuelve su URL real
def buscar_en_artista(url_artista, titulo):
    raiz_buscada = raiz_canonica(titulo)

    # Primero buscamos en la discografía, donde las canciones están organizadas por álbum
    url_disco = url_artista.rstrip("/") + "/discografia/"
    response = requests.get(url_disco, headers=_headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Buscamos primero una coincidencia exacta y, si no, por raíz canónica
    mejor = None
    for fila in soup.select("ul.songList-table-content li.songList-table-row"):
        titulo_listado = fila.find("div", class_="songList-table-songName")
        link = fila.find("a", class_="songList-table-playButton")
        if titulo_listado is None or link is None:
            continue

        nombre = titulo_listado.get_text(strip=True)
        if nombre.lower() == titulo.lower():
            return link["href"]
        if mejor is None and raiz_canonica(nombre) == raiz_buscada:
            mejor = link["href"]

    if mejor is not None:
        return mejor

    # Si no aparece en la discografía, buscamos en la página principal del artista
    response = requests.get(url_artista, headers=_headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    base = "https://www.letras.com"
    mejor = None
    for a in soup.find_all("a", class_="songList-table-songName", href=True):
        nombre = a.get_text(strip=True)
        href = a["href"]
        href = href if href.startswith("http") else base + href
        if nombre.lower() == titulo.lower():
            return href
        if mejor is None and raiz_canonica(nombre) == raiz_buscada:
            mejor = href

    return mejor


# Busca la letra de una canción en LRCLib por título y artista
def buscar_letra_lrclib(titulo, artista):
    try:
        r = requests.get("https://lrclib.net/api/get", params={
            "artist_name": artista,
            "track_name": titulo,
        }, timeout=10)
        if r.status_code != 200:
            return None
        return r.json().get("plainLyrics") or None
    except Exception:
        return None


# Busca la letra de una canción en letras.com por título y artista
def buscar_letra_scraping(titulo, artista):
    candidatos = buscar_artista_scraping(artista)

    for url_artista in candidatos:
        try:
            url_cancion = buscar_en_artista(url_artista, titulo)
        except Exception:
            continue

        if url_cancion is not None:
            letra = extraer_letra(url_cancion)
            time.sleep(0.3)
            return letra

    return None


# Busca la letra de una canción probando primero LRCLib y después letras.com como fallback
def buscar_letra(titulo, artista):
    letra = buscar_letra_lrclib(titulo, artista)
    if letra:
        return letra, "lrclib"

    letra = buscar_letra_scraping(titulo, artista)
    if letra:
        return letra, "letras.com"

    return None, None


# Lee un CSV, busca las letras de las canciones que no la tengan y las escribe de vuelta
def añadir_letras(ruta):
    columnas, filas = leer_csv(ruta)

    # Si no existen las columnas de letra y fuente, las creamos
    if "lyrics" not in columnas:
        columnas.append("lyrics")
    if "source" not in columnas:
        columnas.append("source")

    pendientes = [i for i, fila in enumerate(filas) if not fila.get("lyrics")]

    for i in tqdm(pendientes, desc="Completando letras"):
        fila = filas[i]
        letra, fuente = buscar_letra(fila["track"], fila["artist"])
        fila["lyrics"] = letra or ""
        fila["source"] = fuente or ""

        # Guardamos el CSV entero después de cada canción
        escribir_csv(ruta, columnas, filas)
