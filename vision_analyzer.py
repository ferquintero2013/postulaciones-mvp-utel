import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

# Crear cliente OpenAI usando la API key del .env
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


SYSTEM_PROMPT = """Eres un asistente experto en validacion de documentos de admision universitaria colombianos. Analizas imagenes de documentos y extraes informacion estructurada en formato JSON.

Debes responder SIEMPRE con un JSON valido, sin texto adicional antes o despues, con esta estructura exacta:

{
  "tipo_detectado": "cedula" | "diploma" | "notas" | "inscripcion" | "pago" | "desconocido",
  "nombre_completo": "string o null si no es legible",
  "numero_identificacion": "string o null si no aparece",
  "fecha_documento": "YYYY-MM-DD. Para CEDULA usa fecha de expedicion. Para DIPLOMA usa fecha de grado. Para NOTAS usa fecha de emision. Para INSCRIPCION usa fecha del formulario. Para PAGO usa fecha de la transaccion. Null si no aparece.",
  "campos_adicionales": {},
  "confianza": 0.0 a 1.0,
  "problemas_detectados": [],
  "legibilidad": "alta" | "media" | "baja"
}"""


def analyze_document_with_vision(document):
    """Envia una imagen a GPT-4o Vision y devuelve extraccion estructurada."""
    user_text = f"Analiza este documento. Tipo esperado: {document['expected_type']}"
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": document['url']}}
            ]}
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1000
    )
    
    raw_content = response.choices[0].message.content
    return json.loads(raw_content)


if __name__ == "__main__":
    # Test: analizar el primer documento del aspirante ferney
    from github_client import fetch_documents_from_github
    
    print("Consultando documentos...")
    documentos = fetch_documents_from_github("ferney")
    
    # Analizar solo el primero para probar
    primer_doc = documentos[0]
    print(f"\nAnalizando: {primer_doc['filename']}")
    print(f"Tipo esperado: {primer_doc['expected_type']}\n")
    
    resultado = analyze_document_with_vision(primer_doc)
    
    print("Resultado:")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
