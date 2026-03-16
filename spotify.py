# Cargamos las librerías necesarias
import os
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

# Cargamos las credenciales del archivo .env
load_dotenv()

# Autenticación con OAuth para poder acceder a mis playlists privadas y crear playlists
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="playlist-read-private playlist-modify-public playlist-modify-private",
))


# Extrae las canciones de una playlist de Spotify y devuelve una lista de diccionarios
def obtener_playlist(playlist_id):
    resultados = sp.playlist_items(playlist_id)
    tracks = resultados["items"]

    # Si la playlist tiene más de cien canciones, Spotify las entrega en varias páginas
    while resultados["next"]:
        resultados = sp.next(resultados)
        tracks.extend(resultados["items"])

    canciones = []
    for item in tracks:
        track = item["track"]
        canciones.append({
            "track": track["name"],
            "artist": track["artists"][0]["name"],
            "album": track["album"]["name"],
            "release_date": track["album"]["release_date"],
            "spotify_id": track.get("id", ""),
            "isrc": track.get("external_ids", {}).get("isrc", ""),
        })

    return canciones
