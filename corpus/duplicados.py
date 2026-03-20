# Detección de canciones duplicadas comparando sus letras
# Usa TF-IDF sobre n-gramas de caracteres y similitud de coseno entre todos los pares
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from utilities import leer_csv, escribir_csv


# Vectoriza las letras y devuelve los pares por encima del umbral, ordenados por similitud
def encontrar_duplicados(filas, umbral=0.80):
    letras = [fila.get("lyrics", "") for fila in filas]

    # Trabajamos con n-gramas de caracteres porque toleran mejor erratas y variaciones de formato
    vectorizador = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2)
    matriz_tfidf = vectorizador.fit_transform(letras)

    matriz_sim = cosine_similarity(matriz_tfidf)

    # Triángulo superior para no contar el par (i,j) y el (j,i) como dos
    triangulo = np.triu(np.ones_like(matriz_sim), k=1).astype(bool)
    filas_idx, cols_idx = np.where((matriz_sim > umbral) & triangulo)

    # Ordenamos por similitud descendente para revisar primero los pares más parecidos
    pares = [(int(i), int(j), float(matriz_sim[i, j])) for i, j in zip(filas_idx, cols_idx)]
    pares.sort(key=lambda p: p[2], reverse=True)
    return pares


# Recorre los pares duplicados y deja al usuario decidir cuál se queda y cuál se elimina
def eliminar_duplicados(ruta_csv, umbral=0.80):
    columnas, filas = leer_csv(ruta_csv)
    pares = encontrar_duplicados(filas, umbral=umbral)

    print(f"{len(pares)} pares por encima de {umbral}")

    a_eliminar = set()
    for n, (i, j, sim) in enumerate(pares, start=1):
        # Los duplicados exactos no necesitan revisión humana
        if sim == 1.0:
            a_eliminar.add(j)
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
