# Funciones para la construcción y curación del corpus de entrenamiento
# No forman parte del pipeline de clasificación, son herramientas para generar el dataset
from letras import raiz_canonica
from spotify import sp
from tqdm import tqdm


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
    catalogo = {}
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
                # Primera aparición de esta canción, nos la quedamos
                catalogo[raiz] = cancion
            elif album["release_date"] == catalogo[raiz]["release_date"]:
                # Misma fecha: nos quedamos con el título más corto (sin sufijos)
                if len(track["name"]) < len(catalogo[raiz]["track"]):
                    catalogo[raiz] = cancion
            elif album["album_type"] == "album" and catalogo[raiz]["album_type"] != "album":
                # La canción existía como single pero ahora aparece en un álbum oficial
                catalogo[raiz] = cancion

    return list(catalogo.values())
