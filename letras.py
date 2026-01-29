# Cargamos las librerías necesarias
import csv
import time
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


# Extrae el título, el artista y la letra de una canción desde su URL en letras.com
def obtener_letra(url):
    headers = {"User-Agent": "Mozilla/5.0"}
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


# Recorre la discografía de un artista en letras.com y devuelve todas sus canciones con metadatos
def obtener_discografia(url_artista):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url_artista, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Solo nos interesan los bloques marcados como álbum para evitar duplicados en singles o EP
    albumes = soup.find_all("div", class_="albumItem", attrs={"data-type": "album"})

    # Aplanamos todas las canciones en una única lista para poder mostrar el progreso global
    entradas = []
    for album in albumes:
        nombre_album = album.find("h1", class_="songList-header-name").get_text(strip=True)
        info = album.find("div", class_="songList-header-info").get_text(separator="|", strip=True)
        año = info.split("|")[0].strip()

        filas = album.select("ul.songList-table-content li.songList-table-row")
        for fila in filas:
            link = fila.find("a", class_="songList-table-playButton")
            if link is None:
                continue
            url_cancion = link["href"]
            entradas.append((nombre_album, año, url_cancion))

    canciones = []
    for nombre_album, año, url_cancion in tqdm(entradas, desc="Descargando letras"):
        datos = obtener_letra(url_cancion)
        datos["album"] = nombre_album
        datos["año"] = año
        canciones.append(datos)
        # Pausa breve para no saturar el servidor
        time.sleep(0.3)

    return canciones


# Guarda una lista de canciones como CSV
def guardar_canciones_csv(canciones, ruta):
    columnas = ["titulo", "artista", "album", "año", "letra"]
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columnas)
        for cancion in canciones:
            writer.writerow([cancion.get(col, "") for col in columnas])
