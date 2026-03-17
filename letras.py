# Cargamos las librerías necesarias
import csv
import re
import time
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


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


# Descarta letras demasiado cortas que suelen ser instrumentales o tracks sin contenido real
def es_ruido(letra, umbral=250):
    return letra is None or len(letra) < umbral


# Guarda una lista de diccionarios como CSV, usando las claves del primero como cabecera
def guardar_canciones_csv(canciones, ruta):
    columnas = list(canciones[0].keys())
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columnas)
        for cancion in canciones:
            writer.writerow([cancion.get(col, "") for col in columnas])


# Headers para las peticiones a letras.com
_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}

# Cache del índice alfabético de artistas para no repetir peticiones a la misma inicial
_cache_indices = {}


# Extrae el título, el artista y la letra de una canción desde su URL en letras.com
def extraer_letra(url):
    response = requests.get(url, headers=_headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # El título está en el header uno de la página
    h1 = soup.find("h1")
    titulo = h1.get_text(strip=True) if h1 else None

    # El artista está dentro de un enlace con la clase title-secondary
    link_artista = soup.find("a", class_="title-secondary")
    artista = link_artista.get_text(strip=True) if link_artista else None

    # El contenedor de la letra puede tener dos clases distintas según la versión de la página
    container = soup.find("div", class_="lyric-original") or soup.find("div", class_="cnt-letra")

    # Sacamos cada párrafo por separado y los unimos con doble salto de línea para preservar las estrofas
    if container is not None:
        parrafos = [p.get_text(separator="\n", strip=True) for p in container.find_all("p")]
        letra = "\n\n".join(parrafos) if parrafos else container.get_text(separator="\n", strip=True)
    else:
        letra = None

    return {
        "titulo": titulo,
        "artista": artista,
        "letra": letra,
    }


# Busca un artista por nombre en el índice alfabético de letras.com y devuelve las URLs candidatas
def buscar_artista(nombre):
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
    candidatos = buscar_artista(artista)

    for url_artista in candidatos:
        try:
            url_cancion = buscar_en_artista(url_artista, titulo)
        except Exception:
            continue

        if url_cancion is not None:
            resultado = extraer_letra(url_cancion)
            time.sleep(0.3)
            return resultado["letra"] if resultado else None

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
    with open(ruta, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columnas = list(reader.fieldnames)
        filas = list(reader)

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
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            writer.writeheader()
            writer.writerows(filas)


# Recorre la discografía de un artista en letras.com y devuelve todas sus canciones con metadatos
def obtener_discografia(url_artista):
    response = requests.get(url_artista, headers=_headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Recogemos todos los lanzamientos y los invertimos para procesarlos en orden cronológico
    lanzamientos = soup.find_all("div", class_="albumItem")
    lanzamientos.reverse()

    # Aplanamos todas las canciones en una única lista para poder mostrar el progreso global
    entradas = []
    for lanzamiento in lanzamientos:
        nombre_album = lanzamiento.find("h1", class_="songList-header-name").get_text(strip=True)
        info = lanzamiento.find("div", class_="songList-header-info").get_text(separator="|", strip=True)
        año = info.split("|")[0].strip()

        # Clasificamos el tipo de lanzamiento
        tipo_raw = lanzamiento.get("data-type", "single").lower()
        tipo = "album" if tipo_raw == "album" else "single_ep"

        filas = lanzamiento.select("ul.songList-table-content li.songList-table-row")
        for fila in filas:
            titulo_listado = fila.find("div", class_="songList-table-songName").get_text(strip=True)
            link = fila.find("a", class_="songList-table-playButton")
            if link is None:
                continue
            url_cancion = link["href"]
            entradas.append((nombre_album, año, tipo, titulo_listado, url_cancion))

    # Descargamos las letras con deduplicación por raíz canónica
    catalogo = {}
    for nombre_album, año, tipo, titulo_listado, url_cancion in tqdm(entradas, desc="Descargando letras"):
        raiz = raiz_canonica(titulo_listado)

        if raiz not in catalogo:
            # Canción nueva, descargamos su letra
            datos = extraer_letra(url_cancion)
            if es_ruido(datos["letra"]):
                time.sleep(0.3)
                continue
            datos["titulo"] = titulo_listado
            datos["album"] = nombre_album
            datos["año"] = año
            datos["tipo"] = tipo
            catalogo[raiz] = datos
            time.sleep(0.3)

        elif tipo == "album" and catalogo[raiz].get("tipo") != "album":
            # La canción ya existía como single pero ahora aparece en un álbum oficial
            datos = extraer_letra(url_cancion)
            if es_ruido(datos["letra"]):
                time.sleep(0.3)
                continue
            datos["titulo"] = titulo_listado
            datos["album"] = nombre_album
            datos["año"] = año
            datos["tipo"] = tipo
            catalogo[raiz] = datos
            time.sleep(0.3)

    return list(catalogo.values())
