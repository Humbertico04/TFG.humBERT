# Clasificación masiva de canciones vía Together AI con ensemble de tres runs
# Procesa runs vacíos y con error en paralelo, con checkpoint tras cada canción
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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


# Devuelve qué runs de una canción necesitan procesarse: los vacíos o los que dieron error
def runs_a_procesar(fila):
    pendientes = []
    for n in range(1, 4):
        vector = (fila.get(f"vector_{n}") or "").strip()
        if not vector or vector.upper().startswith("ERROR"):
            pendientes.append(n)
    return pendientes


# Recorre el CSV procesando en paralelo todos los runs pendientes de cada canción
def clasificar_canciones(ruta_csv, ruta_prompt, workers=50):
    columnas, filas = leer_csv(ruta_csv)

    # Creamos las columnas del ensemble si no existen para mantener el orden
    for n in range(1, 4):
        for col in (f"justificacion_{n}", f"vector_{n}"):
            if col not in columnas:
                columnas.append(col)

    with open(ruta_prompt, "r", encoding="utf-8") as f:
        prompt = f.read()

    pendientes = [(i, runs) for i, fila in enumerate(filas) if (runs := runs_a_procesar(fila))]

    csv_lock = threading.Lock()

    def procesar_una(i, runs):
        fila = filas[i]
        for run in runs:
            try:
                justificacion, vector = clasificar_cancion(
                    fila["artist"], fila["track"], fila["lyrics"], prompt
                )
                fila[f"justificacion_{run}"] = justificacion
                fila[f"vector_{run}"] = vector or "ERROR: No se encontró vector"
            except Exception as e:
                fila[f"justificacion_{run}"] = f"ERROR: {e}"
                fila[f"vector_{run}"] = "ERROR"
        return i

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(procesar_una, i, runs) for i, runs in pendientes]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Clasificando canciones"):
            future.result()
            # Checkpoint thread-safe tras cada canción terminada
            with csv_lock:
                escribir_csv(ruta_csv, columnas, filas)
