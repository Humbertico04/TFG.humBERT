# Detección de canciones duplicadas comparando el vocabulario de las letras
# Usa similitud de Jaccard sobre CountVectorizer binario, ignorando palabras vacías
import nltk
import numpy as np
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import CountVectorizer
from utilities import leer_csv, escribir_csv

# Descargamos las stopwords de NLTK la primera vez si hace falta
try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords")

# Palabras vacías estándar del inglés
stop_words = stopwords.words("english")


# Construye un CountVectorizer binario que ignora stopwords y palabras de menos de tres letras
def crear_vectorizador():
    return CountVectorizer(
        stop_words=stop_words,
        token_pattern=r"(?u)\b[a-zA-Z]{3,}\b",
        binary=True,
    )


# Calcula la matriz de Jaccard entre dos conjuntos de vectores binarios de palabras
def jaccard(matriz_a, matriz_b):
    interseccion = (matriz_a @ matriz_b.T).toarray().astype(float)
    sumas_a = matriz_a.sum(axis=1).A1
    sumas_b = matriz_b.sum(axis=1).A1
    union = sumas_a[:, None] + sumas_b[None, :] - interseccion
    return interseccion / union


# Vectoriza las letras y devuelve los pares por encima del umbral, ordenados por similitud
def encontrar_duplicados(filas, umbral=0.35):
    letras = [fila.get("lyrics", "") for fila in filas]
    matriz = crear_vectorizador().fit_transform(letras)
    matriz_sim = jaccard(matriz, matriz)

    # Triángulo superior para no contar el par (i,j) y el (j,i) como dos
    triangulo = np.triu(np.ones_like(matriz_sim), k=1).astype(bool)
    filas_idx, cols_idx = np.where((matriz_sim > umbral) & triangulo)

    pares = [(int(i), int(j), float(matriz_sim[i, j])) for i, j in zip(filas_idx, cols_idx)]
    pares.sort(key=lambda p: p[2], reverse=True)
    return pares


# Recorre los pares duplicados y deja al usuario decidir cuál se queda y cuál se elimina
def eliminar_duplicados(ruta_csv, umbral=0.35):
    columnas, filas = leer_csv(ruta_csv)
    pares = encontrar_duplicados(filas, umbral=umbral)

    print(f"{len(pares)} pares por encima de {umbral}")

    a_eliminar = set()
    for n, (i, j, sim) in enumerate(pares, start=1):
        # Si una de las dos canciones del par ya se ha marcado, no preguntamos otra vez
        if i in a_eliminar or j in a_eliminar:
            continue

        a, b = filas[i], filas[j]
        print(f"\n{'=' * 60}")
        print(f"[{n}/{len(pares)}] similitud {sim:.2f}")
        print(f"  A (idx {i}): {a['track']} — {a['artist']}")
        print(f"  B (idx {j}): {b['track']} — {b['artist']}")
        print(f"\n--- Letra A ---\n{a['lyrics'][:300]}")
        print(f"\n--- Letra B ---\n{b['lyrics'][:300]}")

        eleccion = input("\n¿Cuál mantener? [a] solo A / [b] solo B / [s] saltar: ").strip().lower()
        if eleccion == "a":
            a_eliminar.add(j)
        elif eleccion == "b":
            a_eliminar.add(i)

    filas_limpias = [fila for k, fila in enumerate(filas) if k not in a_eliminar]
    escribir_csv(ruta_csv, columnas, filas_limpias)
    print(f"\nEliminadas {len(a_eliminar)} canciones, quedan {len(filas_limpias)}")


# Detecta qué canciones de un CSV nuevo ya están en un CSV master
def encontrar_solapamiento(filas_master, filas_nuevas, umbral=0.35):
    letras_master = [fila.get("lyrics", "") for fila in filas_master]
    letras_nuevas = [fila.get("lyrics", "") for fila in filas_nuevas]

    # Ajustamos el vocabulario sobre ambos CSVs para que las representaciones sean comparables
    vectorizador = crear_vectorizador()
    vectorizador.fit(letras_master + letras_nuevas)

    matriz_master = vectorizador.transform(letras_master)
    matriz_nuevas = vectorizador.transform(letras_nuevas)

    # Jaccard cruzado: filas = canciones nuevas, columnas = canciones del master
    matriz_sim = jaccard(matriz_nuevas, matriz_master)

    nuevas_idx, master_idx = np.where(matriz_sim > umbral)
    pares = [(int(i), int(j), float(matriz_sim[i, j])) for i, j in zip(nuevas_idx, master_idx)]
    pares.sort(key=lambda p: p[2], reverse=True)
    return pares


# Elimina de un CSV nuevo todas las canciones que ya están en un CSV master
def eliminar_solapamiento(ruta_master, ruta_nuevas, umbral=0.35):
    _, filas_master = leer_csv(ruta_master)
    columnas, filas_nuevas = leer_csv(ruta_nuevas)

    pares = encontrar_solapamiento(filas_master, filas_nuevas, umbral=umbral)
    a_eliminar = {i for i, _, _ in pares}

    filas_limpias = [fila for k, fila in enumerate(filas_nuevas) if k not in a_eliminar]
    escribir_csv(ruta_nuevas, columnas, filas_limpias)
    return len(a_eliminar)
