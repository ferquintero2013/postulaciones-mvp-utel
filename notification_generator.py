import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


SYSTEM_PROMPT_NOTIFICATION = """Eres un asistente que redacta mensajes profesionales y empaticos para aspirantes de una universidad. El mensaje debe ser:
- Claro y breve (maximo 200 palabras)
- En espanol formal pero cercano
- Explicar el estado del expediente y proximos pasos si aplican
- Nunca mencionar detalles tecnicos internos (no digas 'REVISION_MANUAL', di 'nuestro equipo revisara personalmente')
- Cerrar con tono positivo o de apoyo segun el caso"""


def generate_notification(expedient):
    """Generates a personalized notification message for the applicant."""
    
    user_msg = (
        f"Redacta un mensaje de notificacion para el siguiente dictamen "
        f"del expediente de admision: {json.dumps(expedient, ensure_ascii=False)}"
    )
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_NOTIFICATION},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.5,
        max_tokens=500
    )
    
    return response.choices[0].message.content


if __name__ == "__main__":
    # Test: full pipeline + notification
    from pipeline import process_expedient
    
    expedient = process_expedient("ferney")
    
    print("\n" + "=" * 60)
    print("NOTIFICATION FOR APPLICANT")
    print("=" * 60)
    notification = generate_notification(expedient)
    print(f"\n{notification}\n")
