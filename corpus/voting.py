# Sistema de voting para agregar las tres clasificaciones de Together AI por canción
# Aplica puntos (primaria=3, secundaria=1) y decide nivel GOLD / SILVER / BRONZE
import re
from utilities import leer_csv, escribir_csv


# Convierte un vector ###[...]### en un dict con sus campos, o None si no se puede parsear
def parsear_vector(texto):
    if not texto or "ERROR" in str(texto):
        return None

    match = re.search(r"###\[(.*?)\]###", str(texto))
    if not match:
        return None

    partes = [p.strip() for p in match.group(1).split(",")]

    try:
        # Vector completo: [primaria, conf_primaria, secundaria, conf_secundaria, usabilidad]
        if len(partes) == 5:
            cat_prim = int(partes[0])
            conf_prim = float(partes[1])
            cat_sec, conf_sec = parsear_secundaria(partes[2], partes[3])
            usab = float(partes[4])

        # Vector medio: [primaria, conf_primaria, secundaria, usabilidad]
        elif len(partes) == 4:
            cat_prim = int(partes[0])
            conf_prim = float(partes[1])
            cat_sec, _ = parsear_secundaria(partes[2], "0")
            conf_sec = 0.0
            usab = float(partes[3])

        # Vector corto: [primaria, conf_primaria, usabilidad]
        elif len(partes) == 3:
            cat_prim = int(partes[0])
            conf_prim = float(partes[1])
            cat_sec, conf_sec = None, 0.0
            usab = float(partes[2])

        else:
            return None

        return {
            "primaria": cat_prim,
            "conf_primaria": conf_prim,
            "secundaria": cat_sec,
            "conf_secundaria": conf_sec,
            "usabilidad": usab,
        }
    except (ValueError, IndexError):
        return None


# Interpreta el campo de secundaria, que puede venir como número, 0, N, None, etc.
def parsear_secundaria(cat_str, conf_str):
    try:
        cat = int(cat_str)
        if cat < 1 or cat > 16:
            return None, 0.0
        return cat, float(conf_str)
    except ValueError:
        return None, 0.0


VACIO = {"nivel": "", "primaria": None, "secundaria": None, "pts_primaria": 0, "pts_secundaria": 0}


# Aplica el voting sobre los runs parseados de una canción y devuelve el resultado de la votación
def votar(runs):
    # La tabla de niveles está calibrada para 3 runs, con menos la canción se queda sin etiqueta
    if len(runs) != 3:
        return dict(VACIO)

    # Suma de puntos: cada primaria vale 3, cada secundaria vale 1
    puntos = {}
    for run in runs:
        if run.get("primaria"):
            puntos[run["primaria"]] = puntos.get(run["primaria"], 0) + 3
        if run.get("secundaria"):
            puntos[run["secundaria"]] = puntos.get(run["secundaria"], 0) + 1

    if not puntos:
        return dict(VACIO)

    ordenadas = sorted(puntos.items(), key=lambda x: x[1], reverse=True)

    # La primaria ganadora tiene que haber sido primaria al menos una vez
    primaria, pts_primaria = None, 0
    for cat, pts in ordenadas:
        if any(r.get("primaria") == cat for r in runs):
            primaria, pts_primaria = cat, pts
            break

    if primaria is None:
        return dict(VACIO)

    # La secundaria es la siguiente con más puntos (puede no haber)
    secundaria, pts_secundaria = None, 0
    for cat, pts in ordenadas:
        if cat != primaria:
            secundaria, pts_secundaria = cat, pts
            break

    # Empates a 4: tres categorías con 4 puntos cada una, o dos con 4
    if pts_primaria == 4:
        cuatros = [c for c, p in puntos.items() if p == 4]
        if len(cuatros) == 3:
            return {"nivel": "GOLD", "primaria": cuatros, "secundaria": None, "pts_primaria": 4, "pts_secundaria": 0}
        if len(cuatros) == 2:
            return {"nivel": "SILVER", "primaria": cuatros, "secundaria": None, "pts_primaria": 4, "pts_secundaria": 0}
        return {"nivel": "BRONZE", "primaria": primaria, "secundaria": None, "pts_primaria": 4, "pts_secundaria": pts_secundaria}

    # Tabla principal: nivel y secundaria según puntos de primaria y secundaria
    if pts_primaria == 9:
        sec = secundaria if pts_secundaria == 3 else None
        return {"nivel": "GOLD", "primaria": primaria, "secundaria": sec, "pts_primaria": 9, "pts_secundaria": pts_secundaria}

    if pts_primaria == 7:
        sec = secundaria if pts_secundaria >= 4 else None
        return {"nivel": "GOLD", "primaria": primaria, "secundaria": sec, "pts_primaria": 7, "pts_secundaria": pts_secundaria}

    if pts_primaria == 6:
        sec = secundaria if pts_secundaria >= 4 else None
        nivel = "GOLD" if pts_secundaria >= 4 else "SILVER"
        return {"nivel": nivel, "primaria": primaria, "secundaria": sec, "pts_primaria": 6, "pts_secundaria": pts_secundaria}

    if pts_primaria == 5:
        sec = secundaria if pts_secundaria == 4 else None
        nivel = "GOLD" if pts_secundaria == 4 else "SILVER"
        return {"nivel": nivel, "primaria": primaria, "secundaria": sec, "pts_primaria": 5, "pts_secundaria": pts_secundaria}

    return {"nivel": "BRONZE", "primaria": primaria, "secundaria": None, "pts_primaria": pts_primaria, "pts_secundaria": pts_secundaria}


# Recorre el CSV agregando los tres vectores de cada canción y devuelve el conteo por nivel
def votar_canciones(ruta_csv):
    columnas, filas = leer_csv(ruta_csv)

    # Creamos las columnas de salida si no existen
    for col in ("cat_primaria", "cat_secundaria", "nivel", "pts_primaria", "pts_secundaria"):
        if col not in columnas:
            columnas.append(col)

    stats = {"GOLD": 0, "SILVER": 0, "BRONZE": 0, "runs_malformados": 0}

    for fila in filas:
        runs = []
        for n in (1, 2, 3):
            parseado = parsear_vector(fila.get(f"vector_{n}"))
            if parseado:
                runs.append(parseado)
            elif fila.get(f"vector_{n}"):
                stats["runs_malformados"] += 1

        resultado = votar(runs)
        primaria = resultado["primaria"]
        fila["cat_primaria"] = str(primaria) if isinstance(primaria, list) else (primaria if primaria is not None else "")
        fila["cat_secundaria"] = resultado["secundaria"] if resultado["secundaria"] is not None else ""
        fila["nivel"] = resultado["nivel"]
        fila["pts_primaria"] = resultado["pts_primaria"]
        fila["pts_secundaria"] = resultado["pts_secundaria"]

        if resultado["nivel"]:
            stats[resultado["nivel"]] += 1

    escribir_csv(ruta_csv, columnas, filas)
    return stats
