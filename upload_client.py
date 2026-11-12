# -*- coding: utf-8 -*-
"""Convierte archivos que adjunta el usuario en documentos para el pipeline.

Este modulo es el espejo de `github_client.py`. Ese consulta el sistema
institucional simulado y devuelve una lista de documentos; este hace lo
mismo a partir de archivos que el visitante sube desde la interfaz. Los
dos devuelven exactamente la misma estructura, con las mismas cuatro
claves:

    {'id', 'filename', 'url', 'expected_type'}

Mantener identico ese contrato es lo que permite que el resto del
sistema no cambie ni una linea. `vision_analyzer.py` toma
`documento['url']` y lo pasa a la API de OpenAI en el campo `image_url`.
Ese campo no exige una direccion http: acepta tambien un data URI, o sea
la imagen misma codificada en base64 dentro de la cadena. Para la API lo
unico que cambia es de donde saca los bytes. Para el pipeline no cambia
nada.

Las imagenes no se escriben en disco en ningun momento. Streamlit
entrega los bytes en memoria, aqui se reescalan en memoria, y de ahi
salen hacia la API. Lo que si hay que decir de frente, y esta advertido
en la interfaz, es que la imagen viaja a un servicio de terceros.

Antes de enviarla, cada imagen se reempaqueta como JPEG, por tres
razones distintas:

1. Orientacion. Las fotos de celular suelen venir derechas solo por un
   metadato EXIF, no por como estan guardados los pixeles. Si esa
   rotacion no se aplica, el modelo recibe una cedula acostada y la lee
   bastante peor.
2. Costo. Una foto de 4000 px no se lee mejor que una de 2000 px cuando
   lo que hay que leer es un numero de documento, pero cuesta mas: la
   API cobra las imagenes por mosaicos y los mosaicos crecen con la
   resolucion.
3. Metadatos. Reempaquetar descarta el EXIF, y el EXIF de una foto de
   celular puede traer coordenadas GPS, modelo del equipo y fecha. Nada
   de eso hace falta para leer un documento, y lo que no se envia no hay
   que explicarlo despues. Esta en `test_upload.py` como prueba, no como
   promesa.

Lo que NO se gana es peso, y vale la pena decirlo porque la primera
version de este comentario afirmaba lo contrario. Se midio con una cedula
real del repositorio de prueba: 129 KB en PNG salieron como 327 KB en
JPEG. Reescalar una foto grande si aliviana mucho, pero una imagen que ya
estaba por debajo del lado maximo solo se reempaqueta, y un JPEG de
calidad 85 sobre un escaneo de colores planos puede pesar mas que el PNG
original. Se acepta ese costo porque la razon 3 vale mas que 200 KB de
subida, y porque los tokens de la API los fija el tamano en pixeles, no
los bytes del archivo.

Los limites de abajo tambien son control de gasto. El demo es publico y
no tiene autenticacion, asi que cada documento que entra es una llamada
a GPT-4o que alguien paga. Topar los archivos por corrida acota el costo
de una corrida, no el de un visitante insistente: para eso el unico
freno real es el tope de gasto de la cuenta de OpenAI.
"""

import base64
import hashlib
import io

from PIL import Image, ImageOps

# El tipo esperado se infiere del nombre del archivo con la misma funcion
# que usa la ruta de GitHub. Se importa en vez de copiarse: dos copias de
# la misma tabla de tipos es justo la clase de error que duele cuando ya
# se desincronizaron.
from github_client import TIPOS, infer_type_from_filename

# Lado mayor al que se reescala la imagen antes de enviarla.
LADO_MAXIMO = 2000
CALIDAD_JPEG = 85

# Techo del archivo original, antes de abrirlo. Protege la memoria del
# servidor: una imagen comprimida de 15 MB se expande a bastante mas al
# descomprimirla en memoria.
MAX_BYTES_ORIGEN = 15 * 1024 * 1024

# Documentos por corrida. Un expediente completo son cinco, asi que seis
# deja margen sin volver barata una corrida de cien.
MAX_ARCHIVOS = 6

EXTENSIONES = (".jpg", ".jpeg", ".png", ".webp")


def _leer_bytes(archivo):
    """Saca los bytes de un archivo subido sin asumir que es de Streamlit.

    Streamlit entrega un objeto tipo BytesIO, que tiene `getvalue()`. Se
    acepta tambien cualquier cosa con `read()`, para poder probar este
    modulo sin levantar la interfaz.
    """
    if hasattr(archivo, "getvalue"):
        return archivo.getvalue()
    archivo.seek(0)
    return archivo.read()


def normalizar_imagen(datos):
    """Devuelve la imagen como JPEG, derecha y de un tamano razonable.

    Devuelve la tupla (bytes_jpeg, (ancho, alto)) con el tamano final,
    que es el que la interfaz muestra para que se vea que el reescalado
    si ocurrio.
    """
    imagen = Image.open(io.BytesIO(datos))

    # Aplica la rotacion que el celular dejo anotada en EXIF. Si no hay
    # EXIF devuelve la imagen igual.
    imagen = ImageOps.exif_transpose(imagen) or imagen

    # JPEG no tiene canal alfa. Un PNG con transparencia se aplana sobre
    # blanco, en vez de dejar que Pillow falle o pinte el fondo en negro,
    # que sobre un documento escaneado taparia el texto.
    if imagen.mode in ("RGBA", "LA", "P"):
        imagen = imagen.convert("RGBA")
        fondo = Image.new("RGB", imagen.size, (255, 255, 255))
        fondo.paste(imagen, mask=imagen.split()[-1])
        imagen = fondo
    elif imagen.mode != "RGB":
        imagen = imagen.convert("RGB")

    # thumbnail solo reduce, nunca amplia: una imagen chica se queda como
    # esta, en vez de que le inventemos pixeles que el modelo leeria como
    # ruido.
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)

    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
    return buffer.getvalue(), imagen.size


def a_data_uri(datos_jpeg):
    """Empaqueta los bytes como data URI, que es lo que la API acepta."""
    codificado = base64.b64encode(datos_jpeg).decode("ascii")
    return f"data:image/jpeg;base64,{codificado}"


def construir_documentos(archivos, tipos_esperados=None):
    """Arma la lista de documentos a partir de los archivos subidos.

    `archivos` es la lista que devuelve el file_uploader de Streamlit.
    `tipos_esperados` es una lista paralela con el tipo que el usuario
    confirmo para cada archivo; donde venga vacio se infiere del nombre.

    Devuelve (documentos, rechazos). Los rechazos no se tragan en
    silencio: son una lista de (nombre, motivo) que la interfaz muestra,
    porque un archivo que desaparece sin explicacion se lee como una
    falla del sistema.
    """
    documentos = []
    rechazos = []

    if not archivos:
        return documentos, rechazos

    for idx, archivo in enumerate(archivos):
        nombre = getattr(archivo, "name", "archivo_{}".format(idx + 1))

        if len(documentos) >= MAX_ARCHIVOS:
            rechazos.append(
                (nombre, "se paso del maximo de {} documentos por corrida".format(MAX_ARCHIVOS))
            )
            continue

        if not nombre.lower().endswith(EXTENSIONES):
            rechazos.append(
                (nombre, "extension no admitida, se aceptan {}".format(", ".join(EXTENSIONES)))
            )
            continue

        datos = _leer_bytes(archivo)

        if len(datos) > MAX_BYTES_ORIGEN:
            mb = len(datos) / (1024 * 1024)
            tope = MAX_BYTES_ORIGEN / (1024 * 1024)
            rechazos.append((nombre, "pesa {:.1f} MB y el tope es {:.0f} MB".format(mb, tope)))
            continue

        try:
            jpeg, tamano = normalizar_imagen(datos)
        except Exception as e:
            # Un archivo corrupto, o renombrado a .jpg sin serlo, no debe
            # tumbar la corrida completa de los demas documentos.
            rechazos.append(
                (nombre, "no se pudo abrir como imagen ({})".format(type(e).__name__))
            )
            continue

        esperado = None
        if tipos_esperados and idx < len(tipos_esperados):
            esperado = tipos_esperados[idx]
        if esperado not in TIPOS:
            esperado = infer_type_from_filename(nombre)

        documentos.append(
            {
                "id": "doc_{:03d}".format(len(documentos) + 1),
                "filename": nombre,
                "url": a_data_uri(jpeg),
                "expected_type": esperado,
                # Las claves con guion bajo no son parte del contrato que
                # consume el pipeline: son para la interfaz y para la
                # cache.
                "_origen": "subido",
                "_bytes_enviados": len(jpeg),
                "_tamano": tamano,
                # Huella del contenido, no del nombre. Es lo que permite
                # agregar un documento al expediente sin volver a pagar
                # la lectura de los que ya se leyeron: el mismo archivo
                # da la misma huella aunque se vuelva a subir con otro
                # nombre, y un archivo distinto da otra aunque se llame
                # igual.
                "_huella": hashlib.sha256(jpeg).hexdigest(),
            }
        )

    return documentos, rechazos


if __name__ == "__main__":
    # Prueba sin interfaz: genera una imagen sintetica, la pasa por el
    # mismo camino que un archivo subido y verifica el contrato.
    import sys

    prueba = Image.new("RGB", (3200, 2400), (240, 240, 240))
    buffer = io.BytesIO()
    prueba.save(buffer, format="PNG")
    buffer.name = "cedula_de_prueba.png"
    buffer.seek(0)

    docs, rechazados = construir_documentos([buffer])

    if not docs:
        print("FALLO: no se construyo ningun documento")
        print(rechazados)
        sys.exit(1)

    doc = docs[0]
    print("  id             {}".format(doc["id"]))
    print("  filename       {}".format(doc["filename"]))
    print("  expected_type  {}".format(doc["expected_type"]))
    print("  tamano final   {}x{} px".format(doc["_tamano"][0], doc["_tamano"][1]))
    print("  bytes enviados {:.1f} KB".format(doc["_bytes_enviados"] / 1024))
    print("  url            {}... ({} chars)".format(doc["url"][:48], len(doc["url"])))

    assert doc["url"].startswith("data:image/jpeg;base64,"), "el url no es un data URI"
    assert max(doc["_tamano"]) == LADO_MAXIMO, "no se reescalo al lado maximo"
    assert doc["expected_type"] == "cedula", "no infirio el tipo desde el nombre"
    assert set(doc) >= {"id", "filename", "url", "expected_type"}, "contrato incompleto"

    print("")
    print("  OK: el contrato coincide con el de github_client.")
