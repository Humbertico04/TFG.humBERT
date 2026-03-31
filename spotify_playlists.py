# Genera y puebla playlists humBERT en Spotify a partir de un CSV ya clasificado
import time
from tqdm import tqdm
from spotify import sp, todas_paginas
from utilities import leer_csv

# Las dieciséis categorías que el sistema asigna durante el voting del corpus
CATEGORIAS = {
    1:  "Tristeza",
    2:  "Anestesia Emocional",
    3:  "Deseo Incontrolado",
    4:  "Lucha Emocional",
    5:  "Ira",
    6:  "Desamor",
    7:  "Búsqueda de Sentido",
    8:  "Espiritualidad",
    9:  "Esperanza",
    10: "Apoyo",
    11: "Amor",
    12: "Alegría",
    13: "Empoderamiento",
    14: "Sueños",
    15: "Protesta Social",
    16: "Historias Narradas",
}


# Convierte el campo de categoría en lista de ints (puede venir como int único o como "[1, 5]" en empates del voting)
def parsear_cats(valor):
    if valor is None or str(valor).strip() in ("", "nan", "None"):
        return []
    texto = str(valor).strip()
    if texto.startswith("["):
        return [int(x.strip()) for x in texto.strip("[]").split(",") if x.strip()]
    return [int(float(texto))]


# Devuelve {nombre: id} con todas las playlists del usuario
def listar_playlists_usuario():
    user_id = sp.me()["id"]
    items = todas_paginas(sp.user_playlists(user_id, limit=50))
    return {p["name"]: p["id"] for p in items}


# Crea la playlist si no existe y devuelve su id; reutiliza la existente si la encuentra por nombre exacto
def asegurar_playlist(nombre, descripcion, existentes):
    if nombre in existentes:
        return existentes[nombre]
    user_id = sp.me()["id"]
    creada = sp.user_playlist_create(user=user_id, name=nombre, public=False, description=descripcion)
    existentes[nombre] = creada["id"]
    return creada["id"]


# Devuelve los spotify_id ya presentes en una playlist, pidiendo a la API solo los ids para ahorrar transferencia
def ids_en_playlist(playlist_id):
    items = todas_paginas(sp.playlist_items(playlist_id, fields="items(track(id)),next"))
    return {item["track"]["id"] for item in items if item.get("track") and item["track"].get("id")}


# Añade canciones a una playlist en chunks de cien, saltando las que ya estaban
def anadir_a_playlist(playlist_id, spotify_ids):
    ya_presentes = ids_en_playlist(playlist_id)
    nuevas = [sid for sid in spotify_ids if sid and sid not in ya_presentes]
    if not nuevas:
        return 0

    uris = [f"spotify:track:{sid}" for sid in nuevas]
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist_id, uris[i:i + 100])
        time.sleep(0.3)
    return len(nuevas)


# Lee un CSV clasificado y crea/actualiza una playlist por categoría más una de descarte
def generar_playlists(ruta_csv):
    _, filas = leer_csv(ruta_csv)

    # Creamos o recuperamos las playlists del usuario
    existentes = listar_playlists_usuario()
    playlist_ids = {}
    for num, nombre in CATEGORIAS.items():
        nombre_pl = f"humBERT - Cat. {num}: {nombre}"
        playlist_ids[num] = asegurar_playlist(nombre_pl, f"humBERT — Categoría {num}: {nombre}", existentes)
    playlist_ids["BRONZE"] = asegurar_playlist("humBERT - BRONZE", "humBERT — canciones descartadas en el voting", existentes)

    # Agrupamos los spotify_id por playlist según la columna de nivel y las categorías
    por_playlist = {clave: [] for clave in playlist_ids}
    for fila in filas:
        sid = (fila.get("spotify_id") or "").strip()
        if not sid:
            continue
        if (fila.get("nivel") or "").strip().upper() == "BRONZE":
            por_playlist["BRONZE"].append(sid)
            continue
        for cat in parsear_cats(fila.get("cat_primaria")):
            por_playlist[cat].append(sid)
        for cat in parsear_cats(fila.get("cat_secundaria")):
            por_playlist[cat].append(sid)

    # Poblamos cada playlist filtrando las canciones que ya estuvieran dentro
    for clave, ids in tqdm(por_playlist.items(), desc="Poblando playlists"):
        if ids:
            anadir_a_playlist(playlist_ids[clave], ids)
