import requests


def infer_type_from_filename(filename):
    """Infiere el tipo de documento a partir del nombre del archivo."""
    lower = filename.lower()
    if 'cedula' in lower:
        return 'cedula'
    if 'diploma' in lower:
        return 'diploma'
    if 'nota' in lower:
        return 'notas'
    if 'inscripcion' in lower or 'inscripcion' in lower:
        return 'inscripcion'
    if 'pago' in lower or 'comprobante' in lower:
        return 'pago'
    return 'desconocido'


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
