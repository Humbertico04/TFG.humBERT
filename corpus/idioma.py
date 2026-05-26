# Detección de idioma de letras de canciones usando GlotLID v3 sobre bloques con contexto
import re
from collections import defaultdict

import fasttext
from huggingface_hub import hf_hub_download
from tqdm import tqdm

from utilities import leer_csv, escribir_csv

# Modelo GlotLID v3 cacheado a nivel de módulo, se carga la primera vez que se llama analizar_idioma
_modelo_glotlid = None

# Idiomas con más de cinco mil entradas en MusicBrainz (https://musicbrainz.org/statistics/languages-scripts)
# Sirve para limitar GlotLID al espacio de idiomas realmente presentes en música registrada y evitar
# falsos positivos en criollos basados en inglés que el modelo confunde
candidatos_letras = {
    "eng", "jpn", "deu", "spa", "fra", "rus", "ita", "nld", "por", "fin",
    "heb", "swe", "cmn", "yue", "kor", "ell", "pol", "hin", "nob", "nno",
    "tur", "lat", "ind", "lav", "ces", "dan", "hun", "cym", "est", "gsw", "ara",
}


# Descarga el modelo de HuggingFace la primera vez y lo cachea en memoria para llamadas posteriores
def cargar_glotlid():
    global _modelo_glotlid
    if _modelo_glotlid is None:
        ruta = hf_hub_download(repo_id="cis-lmu/glotlid", filename="model_v3.bin")
        _modelo_glotlid = fasttext.load_model(ruta)
    return _modelo_glotlid


# Llama al predict interno de fasttext para evitar la conversión incompatible con NumPy 2 de fasttext-wheel
def predecir_glotlid(modelo, segmento, k=3):
    predicciones = modelo.f.predict(segmento + "\n", k, 0.0, "strict")
    if not predicciones:
        return (), ()
    probabilidades, etiquetas = zip(*predicciones)
    return etiquetas, probabilidades


# Detecta palabras musicales sin contenido léxico como oh, ah, la o alargamientos tipo ohhhh
def es_vocalizacion(palabra):
    if len(palabra) <= 2:
        return True
    if re.search(r"(.)\1{2,}", palabra):
        return True
    return False


# Normaliza una letra solo para detección de idioma sin tocar el original del corpus
# Quita brackets, deduplica líneas idénticas y descarta las que son casi puramente vocalizaciones repetidas
def letra_limpia_para_idioma(letra):
    if not letra:
        return ""

    texto = re.sub(r"\[[^\]]*\]", " ", letra)

    vistas = set()
    lineas_limpias = []
    for linea in texto.splitlines():
        linea = " ".join(linea.split())
        if not linea:
            continue

        clave = linea.lower()
        if clave in vistas:
            continue
        vistas.add(clave)

        palabras = re.findall(r"\b\w+\b", linea.lower())
        if not palabras:
            continue

        # Descartamos líneas formadas por una sola palabra repetida como yeah yeah o hey hey hey
        if len(palabras) >= 2 and len(set(palabras)) == 1:
            continue

        # Descartamos líneas con muy poca variedad léxica como la la la la la la
        if len(palabras) >= 3 and len(set(palabras)) / len(palabras) < 0.3:
            continue

        # Descartamos líneas donde todas las palabras son vocalizaciones, tipo oh oh ohhh
        if all(es_vocalizacion(p) for p in palabras):
            continue

        lineas_limpias.append(linea)

    return "\n".join(lineas_limpias)


# Divide una letra en bloques con suficiente contexto para que GlotLID acierte, agrupando líneas consecutivas
def segmentar_letra(letra, min_caracteres_alfabeticos=100):
    sin_brackets = re.sub(r"\[[^\]]*\]", " ", letra or "")
    lineas = [" ".join(linea.split()) for linea in sin_brackets.splitlines()]
    lineas = [linea for linea in lineas if linea]

    bloques = []
    bloque_actual = ""
    for linea in lineas:
        bloque_actual = f"{bloque_actual} {linea}".strip() if bloque_actual else linea
        if sum(c.isalpha() for c in bloque_actual) >= min_caracteres_alfabeticos:
            bloques.append(bloque_actual)
            bloque_actual = ""

    # Adjuntamos el residuo final al último bloque para no perderlo y evitar bloques sueltos sin contexto
    if bloque_actual:
        if bloques:
            bloques[-1] = f"{bloques[-1]} {bloque_actual}"
        elif sum(c.isalpha() for c in bloque_actual) >= 20:
            bloques.append(bloque_actual)

    return bloques


# Analiza una letra y devuelve un dict con las proporciones estimadas por idioma usando GlotLID v3
def analizar_idioma(letra, candidatos=candidatos_letras):
    if not letra:
        return {}

    # Trabajamos sobre una copia normalizada solo para identificar el idioma, la letra original no se toca
    letra_para_lid = letra_limpia_para_idioma(letra)
    if not letra_para_lid:
        return {}

    modelo = cargar_glotlid()
    totales = defaultdict(float)
    peso_total = 0.0

    for bloque in segmentar_letra(letra_para_lid):
        # Peso por caracteres alfabéticos para no inflar bloques con muchos signos o espacios
        peso = sum(c.isalpha() for c in bloque)
        # Pedimos top-k generoso para cubrir el espacio antes de filtrar y renormalizar
        etiquetas, probabilidades = predecir_glotlid(modelo, bloque, k=20)

        # Las etiquetas vienen como __label__eng_Latn y nos quedamos con el código ISO-639-3
        pares = [
            (etiqueta.removeprefix("__label__").split("_")[0], float(prob))
            for etiqueta, prob in zip(etiquetas, probabilidades)
        ]
        if candidatos is not None:
            pares = [(idioma, prob) for idioma, prob in pares if idioma in candidatos]

        # Renormalizamos las probabilidades restantes para que sumen uno antes de agregar al total
        # Si ningún idioma cae en candidatos, el peso cuenta en el denominador como residuo no candidato
        suma_validos = sum(prob for _, prob in pares)
        if suma_validos > 0:
            for idioma, prob in pares:
                totales[idioma] += peso * (prob / suma_validos)
        peso_total += peso

    if peso_total == 0:
        return {}

    return {
        idioma: valor / peso_total
        for idioma, valor in sorted(totales.items(), key=lambda x: x[1], reverse=True)
    }


# Recorre un CSV y elimina las filas cuya letra no supera el umbral mínimo del idioma indicado
def filtrar_idioma(ruta, idioma="eng", umbral=0.70, candidatos=candidatos_letras):
    columnas, filas = leer_csv(ruta)
    filas_limpias = [
        fila for fila in tqdm(filas, desc=f"Filtrando por idioma {idioma}")
        if analizar_idioma(fila.get("lyrics", ""), candidatos=candidatos).get(idioma, 0.0) >= umbral
    ]
    escribir_csv(ruta, columnas, filas_limpias)
    return len(filas) - len(filas_limpias)
