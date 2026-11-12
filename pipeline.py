import time
import json
from github_client import fetch_documents_from_github
from vision_analyzer import analyze_document_with_vision
from document_validator import validate_document
from expedient_analyzer import analyze_expedient


def process_expedient(aspirante_folder, documentos=None):
    """Processes the applicant's complete expedient with expedient-level analysis.

    `documentos` permite inyectar la lista ya construida, que es como
    entran los archivos que sube el usuario desde la interfaz. Cuando
    llega en None se consulta el sistema institucional simulado, que es
    el comportamiento de siempre.

    El pipeline no pregunta de donde vienen los documentos, y eso es a
    proposito: mientras cada uno traiga sus cuatro claves, la fuente es
    irrelevante para los cuatro pasos que siguen. Por eso agregar la
    carga de archivos no toco ni la extraccion ni las reglas.

    La interfaz ademas ya tenia los documentos en la mano antes de
    llamar aqui, porque los usa para validar que el aspirante exista.
    Pasarlos por parametro evita la segunda consulta identica a la API
    de GitHub que se hacia en cada corrida.
    """

    if documentos is None:
        print(f"1. Querying institutional system for '{aspirante_folder}'...")
        documentos = fetch_documents_from_github(aspirante_folder)
        print(f"   Found {len(documentos)} documents.\n")
    else:
        print(f"1. Using {len(documentos)} documents provided by the caller.\n")

    print("2. Processing each document with Vision + Validation...\n")
    
    resultados = []
    start_time = time.time()
    
    for doc in documentos:
        print(f"   Analyzing: {doc['filename']}...")
        
        try:
            extracted = analyze_document_with_vision(doc)
            validated = validate_document(doc, extracted)
            resultados.append(validated)
            
            emoji = {'APROBADO': 'OK', 'REQUIERE_CORRECCION': 'WARN', 'REVISION_MANUAL': 'FAIL'}
            print(f"   [{emoji.get(validated['estado'], '?')}] {validated['estado']}")
            
        except Exception as e:
            print(f"   ERROR: {e}")
    
    elapsed = time.time() - start_time
    print(f"\n3. Document processing completed in {elapsed:.1f} seconds.\n")
    
    print("4. Analyzing complete expedient (cross-check + global decision)...")
    expedient = analyze_expedient(resultados)
    print(f"   Expedient state: {expedient['estado_expediente']}\n")
    
    return expedient


if __name__ == "__main__":
    expedient = process_expedient("ferney")
    
    print("=" * 60)
    print("EXPEDIENT REPORT")
    print("=" * 60)
    print(f"\nExpediente ID: {expedient['expediente_id']}")
    print(f"Aspirante: {expedient['aspirante']}")
    print(f"Estado: {expedient['estado_expediente']}")
    print(f"Mensaje: {expedient['mensaje_principal']}")
    
    print(f"\n--- Metrics ---")
    m = expedient['metricas']
    print(f"Total documentos: {m['total_documentos']}")
    print(f"Nivel documento:")
    print(f"  Aprobados: {m['nivel_documento']['aprobados']}")
    print(f"  Requieren correccion: {m['nivel_documento']['requieren_correccion']}")
    print(f"  Revision manual: {m['nivel_documento']['requieren_revision_manual']}")
    print(f"Nivel expediente:")
    print(f"  Decision final: {m['nivel_expediente']['decision_final']}")
    print(f"  Escalado por inconsistencia: {m['nivel_expediente']['escalado_por_inconsistencia']}")
    print(f"% Automatizado: {m['porcentaje_automatizado']}")
    
    print(f"\n--- Cross-check ---")
    print(f"IDs detectados: {expedient['detalle_inconsistencias']['ids_detectados']}")
    print(f"Inconsistencia de ID: {expedient['detalle_inconsistencias']['inconsistencia_id']}")
