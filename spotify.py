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


# Acumula los items de un endpoint paginado de Spotify recorriendo todas las páginas
def todas_paginas(resultado):
    items = resultado["items"]
    while resultado["next"]:
        resultado = sp.next(resultado)
        items.extend(resultado["items"])
    return items


# Extrae las canciones de una playlist de Spotify y devuelve una lista de diccionarios
def obtener_playlist(playlist_id):
    items = todas_paginas(sp.playlist_items(playlist_id))

    canciones = []
    for item in items:
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
