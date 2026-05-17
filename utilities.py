# Funciones para leer y escribir CSVs, reutilizadas desde el resto de módulos
import csv
import os


# Lee un CSV y devuelve sus columnas y filas como diccionarios
def leer_csv(ruta):
    with open(ruta, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columnas = list(reader.fieldnames)
        filas = list(reader)
    return columnas, filas


# Escribe un CSV con las columnas y filas indicadas, de forma atómica para que un fallo no destruya el original
def escribir_csv(ruta, columnas, filas):
    # Escribimos primero a un archivo temporal y solo lo movemos al destino si todo va bien
    ruta_temp = ruta + ".tmp"
    try:
        with open(ruta_temp, "w", newline="", encoding="utf-8-sig") as f:
            # quoting=QUOTE_ALL evita que caracteres raros en las celdas rompan el writer a mitad
            writer = csv.DictWriter(f, fieldnames=columnas, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(filas)
        os.replace(ruta_temp, ruta)
    except Exception:
        # Si la escritura falla, dejamos el destino intacto y limpiamos el temporal
        if os.path.exists(ruta_temp):
            try:
                os.remove(ruta_temp)
            except OSError:
                pass
        raise


# Guarda una lista de diccionarios como CSV, usando las claves del primero como cabecera
def guardar_csv(filas, ruta):
    columnas = list(filas[0].keys())
    escribir_csv(ruta, columnas, filas)
