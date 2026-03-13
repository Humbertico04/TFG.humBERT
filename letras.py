# Cargamos las librerías necesarias
import csv
import re
import time
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


# Extrae el título, el artista y la letra de una canción desde su URL en letras.com
def obtener_letra(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}
    response = requests.get(url, headers=headers, timeout=10)
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


# Recorre la discografía de un artista en letras.com y devuelve todas sus canciones con metadatos
def obtener_discografia(url_artista):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}
    response = requests.get(url_artista, headers=headers, timeout=10)
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
            datos = obtener_letra(url_cancion)
            datos["titulo"] = titulo_listado
            datos["album"] = nombre_album
            datos["año"] = año
            datos["tipo"] = tipo
            catalogo[raiz] = datos
            time.sleep(0.3)

        elif tipo == "album" and catalogo[raiz].get("tipo") != "album":
            # La canción ya existía como single pero ahora aparece en un álbum oficial
            datos = obtener_letra(url_cancion)
            datos["titulo"] = titulo_listado
            datos["album"] = nombre_album
            datos["año"] = año
            datos["tipo"] = tipo
            catalogo[raiz] = datos
            time.sleep(0.3)

    return list(catalogo.values())


# Guarda una lista de canciones como CSV
def guardar_canciones_csv(canciones, ruta):
    columnas = ["titulo", "artista", "album", "año", "tipo", "letra"]
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columnas)
        for cancion in canciones:
            writer.writerow([cancion.get(col, "") for col in columnas])
