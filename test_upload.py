# -*- coding: utf-8 -*-
"""Pruebas de la carga de documentos y de las reglas que la tocan.

No llama a ninguna API y no gasta un solo token: genera las imagenes que
necesita y verifica el comportamiento local. Por eso se puede correr en
cada cambio sin pensarlo dos veces.

    python test_upload.py

Lo que prueba y por que:

- Que los documentos subidos cumplan el MISMO contrato que los que vienen
  de GitHub. Si una de las dos fuentes cambia de forma, el pipeline recibe
  algo distinto segun de donde vino, y esa clase de divergencia no falla,
  solo entrega resultados raros.
- Que la regla 1 del validador no invente problemas cuando no hay tipo
  esperado. Ese era un bug real: la cadena 'desconocido' es verdadera, asi
  que todo archivo con nombre no reconocible producia un problema falso.
  Casi no se veia con los documentos de prueba, porque se llaman
  cedula.jpg y diploma.png, pero con archivos que sube cualquiera un
  nombre como IMG_4821.jpg es lo normal.
- Que esa misma regla SI siga disparando cuando el desajuste es real. Un
  arreglo que apaga la regla entera no es un arreglo.
"""

import base64
import io
import sys

from PIL import Image

from document_validator import validate_document
from github_client import SIN_TIPO_ESPERADO, infer_type_from_filename
from upload_client import LADO_MAXIMO, MAX_ARCHIVOS, MAX_BYTES_ORIGEN, construir_documentos


fallos = []


def verificar(descripcion, condicion, detalle=""):
    if condicion:
        print("  OK     {}".format(descripcion))
    else:
        print("  FALLA  {}".format(descripcion))
        if detalle:
            print("         {}".format(detalle))
        fallos.append(descripcion)


def imagen(nombre, tamano=(800, 600), formato="JPEG", modo="RGB", exif_orientacion=None):
    """Arma un archivo en memoria que se comporta como uno subido."""
    color = (200, 200, 200) if modo == "RGB" else (200, 200, 200, 128)
    img = Image.new(modo, tamano, color)

    buffer = io.BytesIO()
    if exif_orientacion is not None:
        datos_exif = img.getexif()
        datos_exif[274] = exif_orientacion  # 274 = Orientation
        img.save(buffer, format=formato, exif=datos_exif)
    else:
        img.save(buffer, format=formato)

    buffer.name = nombre
    buffer.seek(0)
    return buffer


print("\n--- Inferencia del tipo desde el nombre ---\n")

verificar(
    "'cedula_ferney.jpg' se reconoce como cedula",
    infer_type_from_filename("cedula_ferney.jpg") == "cedula",
)
verificar(
    "'inscripcion.png' con tilde se reconoce igual",
    infer_type_from_filename("inscripción.png") == "inscripcion",
    "sin normalizar acentos esto devolvia 'desconocido'",
)
verificar(
    "'Comprobante de Pago.JPG' se reconoce pese a mayusculas",
    infer_type_from_filename("Comprobante de Pago.JPG") == "pago",
)
verificar(
    "'IMG_4821.jpg' no se fuerza a ningun tipo",
    infer_type_from_filename("IMG_4821.jpg") == SIN_TIPO_ESPERADO,
)
verificar(
    "'documento1.jpg' tampoco, porque 'documento' es demasiado generico",
    infer_type_from_filename("documento1.jpg") == SIN_TIPO_ESPERADO,
)


print("\n--- Contrato del documento construido ---\n")

docs, rechazos = construir_documentos([imagen("cedula.jpg")])

verificar("se construye un documento", len(docs) == 1, str(rechazos))

if docs:
    doc = docs[0]
    verificar(
        "trae las cuatro claves que espera el pipeline",
        set(doc) >= {"id", "filename", "url", "expected_type"},
        "claves: {}".format(sorted(doc)),
    )
    verificar(
        "el url es un data URI de JPEG, que es lo que la API acepta",
        doc["url"].startswith("data:image/jpeg;base64,"),
        doc["url"][:40],
    )
    verificar("el id sigue el formato doc_NNN", doc["id"] == "doc_001", doc["id"])


print("\n--- Normalizacion de la imagen ---\n")

docs, _ = construir_documentos([imagen("grande.jpg", tamano=(4000, 3000))])
verificar(
    "una foto de 4000 px se reescala al lado maximo",
    docs and max(docs[0]["_tamano"]) == LADO_MAXIMO,
    "tamano: {}".format(docs[0]["_tamano"] if docs else None),
)

docs, _ = construir_documentos([imagen("chica.jpg", tamano=(640, 480))])
verificar(
    "una imagen chica NO se amplia",
    docs and docs[0]["_tamano"] == (640, 480),
    "ampliarla le inventaria pixeles que el modelo lee como ruido",
)

# Orientacion 6 significa "rotar para ver derecha". Los pixeles estan
# acostados y el metadato es el que lo corrige.
docs, _ = construir_documentos([imagen("rotada.jpg", tamano=(1000, 500), exif_orientacion=6)])
verificar(
    "se aplica la rotacion EXIF, asi que 1000x500 queda 500x1000",
    docs and docs[0]["_tamano"] == (500, 1000),
    "tamano: {}".format(docs[0]["_tamano"] if docs else None),
)

docs, rechazos = construir_documentos([imagen("transparente.png", formato="PNG", modo="RGBA")])
verificar(
    "un PNG con transparencia no rompe la conversion a JPEG",
    len(docs) == 1,
    str(rechazos),
)


print("\n--- Los metadatos no viajan ---\n")

# El EXIF de una foto de celular puede traer coordenadas GPS, modelo del
# equipo y fecha. Nada de eso hace falta para leer un documento. Se
# verifica sobre los bytes que de verdad se envian: se decodifica el data
# URI de vuelta y se reabre la imagen.
con_metadatos = imagen("con_exif.jpg", tamano=(900, 700), exif_orientacion=6)
img_fuente = Image.open(con_metadatos)
exif_fuente = img_fuente.getexif()
exif_fuente[271] = "MarcaDelCelular"  # 271 = Make
buffer_fuente = io.BytesIO()
img_fuente.save(buffer_fuente, format="JPEG", exif=exif_fuente)
buffer_fuente.name = "con_exif.jpg"
buffer_fuente.seek(0)

verificar(
    "la imagen de entrada si traia metadatos",
    Image.open(io.BytesIO(buffer_fuente.getvalue())).getexif().get(271) == "MarcaDelCelular",
)

buffer_fuente.seek(0)
docs, _ = construir_documentos([buffer_fuente])

if docs:
    cabecera, codificado = docs[0]["url"].split(",", 1)
    enviados = base64.b64decode(codificado)
    exif_enviado = Image.open(io.BytesIO(enviados)).getexif()

    verificar(
        "los bytes enviados ya no traen la marca del equipo",
        exif_enviado.get(271) is None,
        "EXIF que sobrevivio: {}".format(dict(exif_enviado)),
    )
    verificar(
        "ni el resto del EXIF",
        len(dict(exif_enviado)) == 0,
        "EXIF que sobrevivio: {}".format(dict(exif_enviado)),
    )
    verificar(
        "pero la rotacion que pedia el EXIF si quedo aplicada en los pixeles",
        docs[0]["_tamano"] == (700, 900),
        "tamano: {}".format(docs[0]["_tamano"]),
    )


print("\n--- Archivos que no deben entrar ---\n")

corrupto = io.BytesIO(b"esto no es una imagen, solo texto disfrazado")
corrupto.name = "falso.jpg"
docs, rechazos = construir_documentos([imagen("buena.jpg"), corrupto])
verificar(
    "un archivo corrupto se rechaza pero el bueno sigue entrando",
    len(docs) == 1 and len(rechazos) == 1,
    "docs={} rechazos={}".format(len(docs), rechazos),
)

pesado = io.BytesIO(b"\x00" * (MAX_BYTES_ORIGEN + 1))
pesado.name = "pesado.jpg"
docs, rechazos = construir_documentos([pesado])
verificar(
    "un archivo sobre el tope de peso se rechaza antes de abrirlo",
    len(docs) == 0 and len(rechazos) == 1 and "tope" in rechazos[0][1],
    str(rechazos),
)

pdf = io.BytesIO(b"%PDF-1.4")
pdf.name = "diploma.pdf"
docs, rechazos = construir_documentos([pdf])
verificar(
    "una extension no admitida se rechaza con su motivo",
    len(docs) == 0 and "extension" in rechazos[0][1],
    str(rechazos),
)

muchos = [imagen("doc{}.jpg".format(i)) for i in range(MAX_ARCHIVOS + 3)]
docs, rechazos = construir_documentos(muchos)
verificar(
    "pasado el maximo de {} documentos, los extras se rechazan".format(MAX_ARCHIVOS),
    len(docs) == MAX_ARCHIVOS and len(rechazos) == 3,
    "docs={} rechazos={}".format(len(docs), len(rechazos)),
)
verificar(
    "cada rechazo explica su motivo, no desaparece en silencio",
    all(motivo for _, motivo in rechazos),
)


print("\n--- El tipo que elige el usuario manda sobre el nombre ---\n")

docs, _ = construir_documentos([imagen("IMG_4821.jpg")], tipos_esperados=["diploma"])
verificar(
    "lo elegido en la interfaz gana sobre lo inferido del nombre",
    docs and docs[0]["expected_type"] == "diploma",
    "el nombre del archivo no es un dato institucional; la eleccion si",
)

docs, _ = construir_documentos([imagen("cedula.jpg")], tipos_esperados=["invento"])
verificar(
    "un tipo que no existe se descarta y se vuelve a inferir",
    docs and docs[0]["expected_type"] == "cedula",
)


print("\n--- Regla 1 del validador: el bug que arreglamos ---\n")

extraido_limpio = {
    "tipo_detectado": "cedula",
    "nombre_completo": "Ferney Quintero",
    "numero_identificacion": "1098765432",
    "fecha_documento": "2015-03-10",
    "confianza": 0.93,
    "legibilidad": "alta",
    "problemas_detectados": [],
}

resultado = validate_document(
    {"id": "doc_001", "filename": "IMG_4821.jpg", "expected_type": SIN_TIPO_ESPERADO},
    dict(extraido_limpio),
)
verificar(
    "sin tipo esperado NO se inventa un problema de tipo",
    not any("no coincide" in p for p in resultado["problemas_detectados"]),
    "problemas: {}".format(resultado["problemas_detectados"]),
)
verificar(
    "y por lo tanto el documento puede quedar APROBADO",
    resultado["estado"] == "APROBADO",
    "estado: {}".format(resultado["estado"]),
)

resultado = validate_document(
    {"id": "doc_001", "filename": "diploma.jpg", "expected_type": "diploma"},
    dict(extraido_limpio),
)
verificar(
    "un desajuste real SI se reporta, la regla no quedo apagada",
    any("no coincide" in p for p in resultado["problemas_detectados"]),
    "problemas: {}".format(resultado["problemas_detectados"]),
)

resultado = validate_document(
    {"id": "doc_001", "filename": "cedula.jpg", "expected_type": "cedula"},
    dict(extraido_limpio),
)
verificar(
    "cuando coincide tampoco hay problema",
    resultado["problemas_detectados"] == [],
    "problemas: {}".format(resultado["problemas_detectados"]),
)


print("")
if fallos:
    print("  {} prueba(s) fallaron:".format(len(fallos)))
    for f in fallos:
        print("    - {}".format(f))
    sys.exit(1)

print("  Todas las pruebas pasaron.")
