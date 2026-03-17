# Funciones para la construcción y curación del corpus de entrenamiento
# No forman parte del pipeline de clasificación, son herramientas para generar el dataset
import csv
from letras import raiz_canonica, buscar_letra
from spotify import sp
from tqdm import tqdm


# Descarta letras demasiado cortas que suelen ser instrumentales o tracks sin contenido real
def es_ruido(letra, umbral=250):
    return letra is None or len(letra) < umbral


# Busca un artista en Spotify por nombre y devuelve su ID
# Con top_n se muestran los primeros N candidatos para elegir manualmente
def buscar_artista_spotify(artista, top_n=None):
    limite = top_n if top_n else 1
    resultados = sp.search(q="artist:" + artista, type="artist", limit=limite)
    items = resultados["artists"]["items"]
    if not items:
        return None

    if top_n is None:
        return items[0]["id"]

    for i, a in enumerate(items):
        top_tracks = sp.artist_top_tracks(a["id"])["tracks"]
        hit = top_tracks[0]["name"] if top_tracks else "?"
        print(f"  {i + 1}. {a['name']}: {a['followers']['total']:,} seguidores | Hit: {hit}")

    # Elijo a este
    eleccion = int(input(f"Elige artista (1-{len(items)}): ")) - 1
    return items[eleccion]["id"]


# Extrae la discografía completa de un artista desde Spotify, deduplicada por raíz canónica
def obtener_discografia(artista, top_n=None):
    artist_id = buscar_artista_spotify(artista, top_n=top_n)
    if artist_id is None:
        return []

    # Obtenemos todos los lanzamientos (álbumes y singles) con paginación
    albums = []
    resultados = sp.artist_albums(artist_id, album_type="album,single", limit=50)
    albums.extend(resultados["items"])
    while resultados["next"]:
        resultados = sp.next(resultados)
        albums.extend(resultados["items"])

    # Ordenamos del más antiguo al más nuevo para que la versión original se procese primero
    albums.sort(key=lambda x: x["release_date"])

    # Extraemos las canciones de cada álbum y deduplicamos por raíz canónica
    # Guardamos todas las versiones como alternativas para fallback de letras
    catalogo = {}
    alternativas = {}
    for album in tqdm(albums, desc="Extrayendo discografía"):
        tracks_resultado = sp.album_tracks(album["id"])
        tracks = tracks_resultado["items"]
        while tracks_resultado["next"]:
            tracks_resultado = sp.next(tracks_resultado)
            tracks.extend(tracks_resultado["items"])

        for track in tracks:
            raiz = raiz_canonica(track["name"])

            cancion = {
                "track": track["name"],
                "artist": track["artists"][0]["name"],
                "album": album["name"],
                "release_date": album["release_date"],
                "album_type": album["album_type"],
                "spotify_id": track["id"],
            }

            if raiz not in catalogo:
                catalogo[raiz] = cancion
                alternativas[raiz] = []
            elif album["release_date"] == catalogo[raiz]["release_date"]:
                if len(track["name"]) < len(catalogo[raiz]["track"]):
                    # El ganador actual pasa a ser alternativa
                    alternativas[raiz].append(catalogo[raiz]["track"])
                    catalogo[raiz] = cancion
                else:
                    alternativas[raiz].append(track["name"])
            elif album["album_type"] == "album" and catalogo[raiz]["album_type"] != "album":
                alternativas[raiz].insert(0, catalogo[raiz]["track"])
                catalogo[raiz] = cancion
            else:
                alternativas[raiz].append(track["name"])

    # Añadimos las alternativas (sin duplicados) a cada canción
    for raiz, cancion in catalogo.items():
        titulos_unicos = list(dict.fromkeys(
            t for t in alternativas[raiz] if t != cancion["track"]
        ))
        cancion["alternatives"] = "|".join(titulos_unicos)

    return list(catalogo.values())


# Repesca letras vacías o ruidosas en una discografía probando los títulos alternativos
def completar_discografia(ruta):
    with open(ruta, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columnas = list(reader.fieldnames)
        filas = list(reader)

    if "lyrics" not in columnas:
        columnas.append("lyrics")
    if "source" not in columnas:
        columnas.append("source")

    # Revisamos tanto las filas vacías como las que tienen letra ruidosa (instrumentales, etc.)
    pendientes = [i for i, fila in enumerate(filas) if es_ruido(fila.get("lyrics"))]

    for i in tqdm(pendientes, desc="Completando con alternativas"):
        fila = filas[i]
        artista = fila["artist"]

        # Si no hay alternativas guardadas, no hay nada que probar
        if not fila.get("alternatives"):
            continue

        for titulo in fila["alternatives"].split("|"):
            letra, fuente = buscar_letra(titulo, artista)
            if letra and not es_ruido(letra):
                fila["lyrics"] = letra
                fila["source"] = fuente
                # Adoptamos el título alternativo que sí ha funcionado
                fila["track"] = titulo
                break

        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            writer.writeheader()
            writer.writerows(filas)


# Recorre un CSV y elimina las filas cuya letra es ruido (vacía o demasiado corta)
def filtrar_ruido(ruta, umbral=250):
    with open(ruta, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columnas = list(reader.fieldnames)
        filas = list(reader)

    filas_limpias = [fila for fila in filas if not es_ruido(fila.get("lyrics"), umbral)]

    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(filas_limpias)

    return len(filas) - len(filas_limpias)
