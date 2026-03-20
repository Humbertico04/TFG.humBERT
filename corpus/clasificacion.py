# Clasificación masiva de canciones vía Together AI con ensemble de tres runs
# Checkpointea tras cada canción para poder reanudar si se interrumpe
import os
import re
from dotenv import load_dotenv
from together import Together
from tqdm import tqdm
from utilities import leer_csv, escribir_csv

load_dotenv()

# Cliente global para reutilizar conexión entre llamadas
cliente = Together(api_key=os.getenv("TOGETHER_API_KEY"))

# Modelo que clasifica bien y además de bajo coste
MODELO = "Qwen/Qwen3.5-9B"


# Extrae el vector ###[...]### que el modelo devuelve al final de la justificación
def extraer_vector(texto):
    match = re.search(r"###\[.*?\]###", texto)
    return match.group(0) if match else None


# Llama al modelo con la letra de una canción y devuelve la justificación completa y el vector
def clasificar_cancion(artista, titulo, letra, prompt):
    entrada = f"{titulo} - {artista}\n{letra}"

    respuesta = cliente.chat.completions.create(
        model=MODELO,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": entrada},
        ],
        stream=True,
        max_tokens=5000,
        reasoning={"enabled": False},
    )

    # El stream llega token a token, los concatenamos para tener la justificación completa
    justificacion = ""
    for token in respuesta:
        if hasattr(token, "choices") and token.choices:
            delta = token.choices[0].delta.content
            if delta:
                justificacion += delta

    return justificacion, extraer_vector(justificacion)


# Cuenta cuántos runs quedan por hacer en una canción, de 0 (completa) a 3 (sin tocar)
def runs_pendientes(fila):
    hechos = 0
    for i in range(1, 4):
        if fila.get(f"justificacion_{i}"):
            hechos += 1
        else:
            break
    return 3 - hechos


# Recorre el CSV haciendo tres runs por canción y guardando después de cada una
def clasificar_canciones(ruta_csv, ruta_prompt):
    columnas, filas = leer_csv(ruta_csv)

    # Creamos las columnas del ensemble si no existen
    for i in range(1, 4):
        for col in (f"justificacion_{i}", f"vector_{i}"):
            if col not in columnas:
                columnas.append(col)

    with open(ruta_prompt, "r", encoding="utf-8") as f:
        prompt = f.read()

    pendientes = [i for i, fila in enumerate(filas) if runs_pendientes(fila) > 0]

    for i in tqdm(pendientes, desc="Clasificando canciones"):
        fila = filas[i]

        # Empezamos por el primer run que falte en esta canción
        run_inicial = 4 - runs_pendientes(fila)
        for run in range(run_inicial, 4):
            try:
                justificacion, vector = clasificar_cancion(
                    fila["artist"], fila["track"], fila["lyrics"], prompt
                )
                fila[f"justificacion_{run}"] = justificacion
                fila[f"vector_{run}"] = vector or "ERROR: No se encontró vector"
            except Exception as e:
                fila[f"justificacion_{run}"] = f"ERROR: {e}"
                fila[f"vector_{run}"] = "ERROR"

        # Checkpoint tras cada canción: si se cae el script no se pierde el trabajo
        escribir_csv(ruta_csv, columnas, filas)
