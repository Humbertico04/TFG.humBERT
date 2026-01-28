# Cargamos las librerías necesarias
import requests
from bs4 import BeautifulSoup


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
    letra = container.get_text(separator="\n", strip=True) if container else None

    return {
        "titulo": titulo,
        "artista": artista,
        "letra": letra,
    }
