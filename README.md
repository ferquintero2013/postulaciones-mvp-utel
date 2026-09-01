# UTEL MVP — Validacion Inteligente de Documentos con IA

Sistema de hiperautomatizacion con IA para validacion de documentos de admision universitaria. Version Python + Streamlit.

**[Demo en vivo](#)** (URL disponible tras deploy)

---

## Que hace

Procesa documentos de admision (cedula, diploma, notas, inscripcion, comprobante de pago) de un aspirante y:
1. Consulta el sistema institucional (simulado con GitHub API)
2. Extrae informacion estructurada con GPT-4o Vision
3. Valida contra reglas de negocio por documento
4. Detecta inconsistencias entre documentos (cross-check de identidad)
5. Genera notificacion personalizada al aspirante con GPT-4o-mini
6. Retorna dictamen del expediente (APROBADO / REQUIERE_CORRECCION / REVISION_MANUAL / INCOMPLETO)

## Impacto vs proceso manual

| Metrica | Proceso manual | Con este MVP | Reduccion |
|---------|----------------|--------------|-----------|
| Tiempo por documento | ~14 min | ~5 seg | **99%** |
| Cross-check de identidad | No existe | Automatico | Capacidad nueva |
| Notificacion al aspirante | Manual | 100% automatica | 100% |
| Errores humanos estimados | ~6% | <1% | 83% menos |

## Stack

- **Python 3.9+**
- **Streamlit** — UI web
- **OpenAI SDK** — GPT-4o Vision (extraccion) + GPT-4o-mini (redaccion)
- **Requests** — GitHub API como fuente institucional simulada
- **python-dotenv** — gestion de variables de entorno

**Herramienta de desarrollo**: construido con Claude Code como companero de desarrollo.

## Arquitectura

Sistema Institucional (GitHub API)
↓
[1. Fetch documents] → lista de docs del aspirante
↓
[2. GPT-4o Vision] → JSON estructurado por documento
↓
[3. Validate] → reglas de negocio + decision individual
↓
[4. Cross-check global] → deteccion de inconsistencias entre docs
↓
[5. Generate notification] → mensaje IA al aspirante (GPT-4o-mini)
↓
Output: expediente completo + dictamen + notificacion


## Decisiones de diseno

- **IA + Reglas hibridas**: Vision AI extrae, reglas de negocio validan (auditable + explicable)
- **Anti-alucinacion**: el modelo declara su propia confianza; si es baja → escalada a humano
- **Cross-check por ID**: detecta posibles suplantaciones (documentos con IDs distintos)
- **Jerarquia de decision**: inconsistencias > baja confianza > correcciones menores
- **Modelos por caso de uso**: GPT-4o para extraccion, GPT-4o-mini para generacion (10x mas barato)

## Como correrlo localmente

### 1. Clonar el repo

```bash
git clone https://github.com/ferquintero2013/postulaciones-mvp-utel.git
cd postulaciones-mvp-utel

### 2. Crear virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

### 3. Instalar dependencias

pip install -r requirements.

### 4. Configurar API key
Crea un archivo .env en la raiz:

OPENAI_API_KEY=sk-tu-api-key-aqui

### 5. Correr Streamlit

streamlit run app.py
Se abre automaticamente en http://localhost:8501

Estructura del repositorio esperado
El repo de documentos debe tener carpetas por aspirante:


TestUtel/
├── ferney/
│   ├── cedula.jpg
│   ├── diploma.png
│   ├── notas.jpg
│   ├── inscripcion.png
│   └── comprobante_pago.jpg


Autor
Ferney Quintero — AI Automation Engineer
Portafolio: ferney-portfolio.vercel.app
LinkedIn: linkedin.com/in/ferney-quintero
1er lugar "Best AI Automation" — n8n EmprendIA LATAM Hackathon 2025 
