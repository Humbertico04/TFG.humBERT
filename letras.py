# Cargamos las librerías necesarias
import re
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
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


# Elimina anotaciones entre corchetes como [Verse 1] o [Chorus] que ensucian la letra
def limpiar_brackets(texto):
    if not texto:
        return texto
    sin_brackets = re.sub(r"\[.*?\]", "", texto)
    # Colapsamos los saltos de línea triples que quedan al borrar [Chorus] entre estrofas
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", sin_brackets).strip()


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
        letra = "\n\n".join(parrafos) if parrafos else container.get_text(separator="\n", strip=True)
        return limpiar_brackets(letra)

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


# Busca la letra en LRCLib con reintentos y devuelve la tupla (letra, status)
def buscar_letra_lrclib(titulo, artista, timeout=30, reintentos=2):
    pausas = (2, 5, 10)

    for intento in range(reintentos + 1):
        try:
            r = requests.get("https://lrclib.net/api/get", params={
                "artist_name": artista,
                "track_name": titulo,
            }, timeout=timeout)

            # Una canción que no existe en LRCLib es estado terminal y no la volvemos a intentar
            if r.status_code == 404:
                return None, "NOT_FOUND"

            if r.status_code == 200:
                data = r.json()
                # Si es instrumental no tiene sentido buscar letra en ningún sitio
                if isinstance(data, dict) and data.get("instrumental"):
                    return None, "INSTRUMENTAL"
                letra = data.get("plainLyrics") if isinstance(data, dict) else None
                if letra:
                    return letra, "FOUND"
            # Cualquier otra respuesta se considera transitoria y se reintenta
        except (requests.RequestException, ValueError):
            pass

        if intento < reintentos:
            time.sleep(pausas[min(intento, len(pausas) - 1)])

    return None, ""


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


# Busca la letra probando primero LRCLib y, si fallback está activado, letras.com como respaldo
def buscar_letra(titulo, artista, fallback=True):
    letra, status = buscar_letra_lrclib(titulo, artista)
    if status == "FOUND":
        return letra, "FOUND"

    # Instrumental es terminal en cualquier caso, no tiene sentido buscar letra en letras.com
    if status == "INSTRUMENTAL":
        return None, "INSTRUMENTAL"

    # Si LRCLib no la encontró o falló y el fallback está activo, probamos letras.com
    if fallback:
        letra = buscar_letra_scraping(titulo, artista)
        if letra:
            return letra, "FOUND"

    return None, status


# Lee un CSV y busca en paralelo las letras de las canciones pendientes
def añadir_letras(ruta, fallback=True, workers=16):
    columnas, filas = leer_csv(ruta)

    # Creamos las columnas si no existen
    for col in ("lyrics", "lyrics_status"):
        if col not in columnas:
            columnas.append(col)

    # Recogemos las filas sin letra y sin estado terminal previo, las NOT_FOUND e INSTRUMENTAL ya verificadas se saltan
    pendientes = [
        i for i, fila in enumerate(filas)
        if not fila.get("lyrics") and not fila.get("lyrics_status")
    ]

    csv_lock = threading.Lock()

    def procesar_una(i):
        fila = filas[i]
        letra, status = buscar_letra(fila["track"], fila["artist"], fallback=fallback)
        fila["lyrics"] = letra or ""
        fila["lyrics_status"] = status
        return i

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(procesar_una, i) for i in pendientes]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Completando letras"):
            future.result()
            # Checkpoint thread-safe tras cada canción terminada
            with csv_lock:
                escribir_csv(ruta, columnas, filas)
