# Funciones para leer y escribir CSVs, reutilizadas desde el resto de módulos
import csv


# Lee un CSV y devuelve sus columnas y filas como diccionarios
def leer_csv(ruta):
    with open(ruta, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columnas = list(reader.fieldnames)
        filas = list(reader)
    return columnas, filas


# Escribe un CSV con las columnas y filas indicadas
def escribir_csv(ruta, columnas, filas):
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(filas)


# Guarda una lista de diccionarios como CSV, usando las claves del primero como cabecera
def guardar_csv(filas, ruta):
    columnas = list(filas[0].keys())
    escribir_csv(ruta, columnas, filas)
