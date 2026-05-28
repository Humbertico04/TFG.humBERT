# Funciones para normalizar y limpiar texto de letras de canciones
import re
import unicodedata
from ftfy import fix_text


# Unifica los distintos saltos de línea (CRLF, CR, line separator) en un \n estándar
def normalizar_saltos_linea(texto):
    if not texto:
        return texto
    return "\n".join(texto.splitlines())


# Sustituye separadores Unicode (NBSP, thin space, etc.) por espacio ASCII y colapsa los múltiples
def normalizar_espacios_unicode(texto):
    if not texto:
        return texto
    sustituido = "".join(" " if unicodedata.category(c) == "Zs" else c for c in texto)
    return re.sub(r" +", " ", sustituido)


# Elimina caracteres invisibles como zero-width spaces, BOM o marcas de dirección
def limpiar_invisibles_unicode(texto):
    if not texto:
        return texto
    return "".join(
        ch for ch in texto
        if not (unicodedata.category(ch) in {"Cf", "Cc"} and ch not in {"\n", "\t"})
    )


# Arregla mojibake y normaliza tipografía con ftfy preservando los saltos de línea originales
def normalizar_tipografia_ftfy(texto):
    if not texto:
        return texto
    return fix_text(texto, fix_line_breaks=False)


# Sustituye apóstrofes y comillas raras (´, `, ′) por apóstrofe ASCII
def normalizar_apostrofes(texto):
    if not texto:
        return texto
    return re.sub(r"[´`′]", "'", texto)


# Elimina anotaciones entre corchetes como [Verse 1] o [Chorus] que ensucian la letra
def limpiar_brackets(texto):
    if not texto:
        return texto
    texto = re.sub(r"\[.*?\]", "", texto)
    texto = re.sub(r"\n\s*\n\s*\n+", "\n\n", texto)
    texto = texto.replace("\n ", "\n")
    return texto.strip()


# Aplica todo el pipeline de normalización a una letra cruda y devuelve el texto limpio
def limpiar_letra(texto):
    if not texto:
        return texto
    # ftfy primero sobre el texto crudo para que detecte mojibake en su forma original
    texto = normalizar_tipografia_ftfy(texto)
    texto = normalizar_saltos_linea(texto)
    texto = normalizar_espacios_unicode(texto)
    texto = limpiar_invisibles_unicode(texto)
    texto = normalizar_apostrofes(texto)
    texto = limpiar_brackets(texto)
    return texto.strip()
