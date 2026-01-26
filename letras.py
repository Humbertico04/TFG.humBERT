# Cargamos las librerías necesarias
import requests
from bs4 import BeautifulSoup


# Obtiene una letra de letras.com a partir de su URL
def obtener_letra(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    # El contenedor de la letra puede tener dos clases distintas según la versión de la página
    container = soup.find("div", class_="lyric-original") or soup.find("div", class_="cnt-letra")

    if container is None:
        return None

    return container.get_text(separator="\n", strip=True)
