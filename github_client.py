import unicodedata

import requests


# El vocabulario de tipos que entienden las reglas de negocio. Vive aqui
# porque aqui nacio, y se importa desde `upload_client.py` en vez de
# copiarse alla: dos copias de la misma tabla es la clase de error que
# solo se nota cuando ya se desincronizaron.
TIPOS = ('cedula', 'diploma', 'notas', 'inscripcion', 'pago')

# Centinela para "no sabemos que documento se esperaba aqui". No es un
# sexto tipo: es la ausencia de expectativa. El nombre de un archivo no
# es un dato institucional, y cuando no se puede inferir nada, lo
# correcto es no comparar, no inventarse una comparacion.
SIN_TIPO_ESPERADO = 'desconocido'


def _sin_acentos(texto):
    """Normaliza el texto para comparar sin tropezar con tildes.

    Un archivo que sube alguien desde su celular se llama como lo nombro
    su dueno, y en espanol eso trae tildes y enes. Comparar sin
    normalizar hace que 'inscripcion.png' con tilde no coincida nunca.
    """
    descompuesto = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in descompuesto if not unicodedata.combining(c)).lower()


# Palabras que delatan cada tipo. Se evitan las demasiado genericas, como
# "documento", que convertiria cualquier 'documento1.jpg' en una cedula.
PISTAS = (
    ('cedula', ('cedula', 'identidad', 'identificacion')),
    ('diploma', ('diploma', 'titulo', 'grado')),
    ('notas', ('nota', 'calificacion', 'boletin')),
    ('inscripcion', ('inscripcion', 'formulario', 'matricula')),
    ('pago', ('pago', 'comprobante', 'recibo', 'transferencia', 'consignacion')),
)


def infer_type_from_filename(filename):
    """Infiere el tipo de documento a partir del nombre del archivo.

    Devuelve SIN_TIPO_ESPERADO cuando ninguna pista coincide. Eso no es
    una falla: es la respuesta honesta cuando el nombre no dice nada.
    """
    limpio = _sin_acentos(filename)
    for tipo, pistas in PISTAS:
        if any(pista in limpio for pista in pistas):
            return tipo
    return SIN_TIPO_ESPERADO


def fetch_documents_from_github(aspirante_folder):
    """Consulta el sistema institucional y devuelve lista de documentos estructurada."""
    url = f"https://api.github.com/repos/ferquintero2013/TestUtel/contents/{aspirante_folder}"
    response = requests.get(url)
    
    if response.status_code != 200:
        raise Exception(f"Error consultando GitHub: {response.status_code}")
    
    raw_data = response.json()
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    
    documentos = []
    for idx, archivo in enumerate(raw_data):
        # Filtro 1: solo archivos, no carpetas
        if archivo.get('type') != 'file':
            continue
        
        # Filtro 2: solo extensiones validas para Vision
        if not archivo['name'].lower().endswith(valid_extensions):
            continue
        
        # Construir el diccionario limpio
        documento = {
            'id': f"doc_{idx+1:03d}",
            'filename': archivo['name'],
            'url': archivo['download_url'],
            'expected_type': infer_type_from_filename(archivo['name'])
        }
        documentos.append(documento)
    
    return documentos


if __name__ == "__main__":
    documentos = fetch_documents_from_github("ferney")
    print(f"Procesados {len(documentos)} documentos:\n")
    for doc in documentos:
        print(f"  {doc['id']} | {doc['expected_type']:15s} | {doc['filename']}")
