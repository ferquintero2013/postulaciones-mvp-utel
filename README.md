# UTEL MVP: Validacion Inteligente de Documentos con IA

Sistema de hiperautomatizacion con IA para validacion de documentos de admision universitaria. Version Python + Streamlit.

**[Demo en vivo](https://postulaciones-mvp.streamlit.app/)**

---

## Que hace

Procesa los documentos de admision de un aspirante (cedula, diploma, notas, inscripcion, comprobante de pago) y:

1. Recibe los documentos, de un expediente de ejemplo o de archivos que suba el usuario
2. Extrae informacion estructurada con GPT-4o Vision
3. Valida contra reglas de negocio por documento
4. Detecta inconsistencias entre documentos (cross-check de identidad)
5. Genera notificacion personalizada al aspirante con GPT-4o-mini
6. Retorna dictamen del expediente (APROBADO / REQUIERE_CORRECCION / REVISION_MANUAL / INCOMPLETO)

## Las dos formas de probarlo

**Expediente de ejemplo.** Tres expedientes completos viven en un repositorio publico, [TestUtel](https://github.com/ferquintero2013/TestUtel): `ferney`, `maira` y `Test_general`. Se escribe el nombre y listo.

**Documentos propios.** Se suben hasta 6 imagenes desde el equipo y el sistema las procesa igual. No hace falta clonar nada ni crear carpetas.

Las dos rutas entregan al pipeline la misma estructura, con las mismas cuatro claves:

```python
{'id': 'doc_001', 'filename': 'cedula.png', 'url': ..., 'expected_type': 'cedula'}
```

Mantener identico ese contrato es la razon por la que agregar la carga de archivos no toco ni la extraccion ni las reglas de negocio. Lo unico que cambia es el campo `url`: en un caso es una direccion http, y en el otro es un data URI, o sea la imagen misma codificada en base64 dentro de la cadena. El campo `image_url` de la API de OpenAI acepta las dos cosas, asi que para el modelo lo unico que cambia es de donde saca los bytes.

## Impacto vs proceso manual

| Metrica | Proceso manual | Con este MVP | Reduccion |
|---------|----------------|--------------|-----------|
| Tiempo por documento | ~14 min | ~5 seg | **99%** |
| Cross-check de identidad | No existe | Automatico | Capacidad nueva |
| Notificacion al aspirante | Manual | 100% automatica | 100% |
| Errores humanos estimados | ~6% | <1% | 83% menos |

## Stack

- **Python 3.11+**
- **Streamlit**: UI web
- **OpenAI SDK**: GPT-4o Vision (extraccion) + GPT-4o-mini (redaccion)
- **Pillow**: normalizacion de las imagenes que sube el usuario
- **Requests**: GitHub API como fuente institucional simulada
- **python-dotenv**: gestion de variables de entorno

**Herramienta de desarrollo**: construido con Claude Code como companero de desarrollo.

## Arquitectura

```
Expediente de ejemplo              Documentos que sube el usuario
(GitHub API)                       (Pillow, en memoria)
        |                                   |
        +-----------------+-----------------+
                          |
                 [1] lista de documentos
                     id, filename, url, expected_type
                          |
                 [2] GPT-4o Vision
                     JSON estructurado por documento
                          |
                 [3] Reglas de negocio
                     5 reglas por documento, decision individual
                          |
                 [4] Cross-check de expediente
                     deteccion de inconsistencias entre documentos
                          |
                 [5] GPT-4o-mini
                     notificacion al aspirante
                          |
                 Dictamen + metricas + JSON completo
```

Siete modulos con una responsabilidad cada uno:

| Modulo | Responsabilidad |
|--------|-----------------|
| `github_client.py` | Trae los documentos del sistema institucional simulado |
| `upload_client.py` | Convierte los archivos que sube el usuario en el mismo contrato |
| `vision_analyzer.py` | Extraccion con GPT-4o Vision |
| `document_validator.py` | Reglas de negocio por documento |
| `expedient_analyzer.py` | Cross-check y decision global del expediente |
| `notification_generator.py` | Redaccion del mensaje al aspirante |
| `app.py` | Interfaz |

## Decisiones de diseno

- **IA + reglas hibridas**: Vision AI extrae, las reglas deciden. El modelo nunca dictamina: devuelve JSON, y el dictamen sale de reglas deterministas que se pueden auditar linea por linea.
- **La confianza no es una medicion**: el `confianza` que viene en el JSON lo declara el propio modelo sobre su extraccion. No es una probabilidad calibrada y ninguna libreria lo calcula. Por eso no decide sola: es una de cinco reglas, y las otras cuatro si son deterministas (tipo esperado, nombre legible, formato de identificacion, fecha obligatoria en cedula). Esa es la mitigacion de un indice que hereda la variabilidad del modelo que lo emite.
- **Cross-check por ID**: detecta posibles suplantaciones cuando dos documentos del mismo expediente traen identificaciones distintas.
- **Jerarquia de decision**: expediente incompleto > inconsistencia de identidad > baja confianza > correcciones menores.
- **Modelos por caso de uso**: GPT-4o para extraccion, GPT-4o-mini para generacion, que cuesta cerca de 10 veces menos y aqui solo tiene que redactar.
- **El tipo esperado es un dato institucional**: es el documento que se le pidio al aspirante, no algo que se deduzca del archivo. Del nombre del archivo se infiere solo como atajo para ahorrar clics, y en la interfaz se puede corregir o dejar sin especificar.

## Que pasa con los documentos que subes

Esto esta advertido en la interfaz antes de que se pueda subir nada, y conviene que este escrito aqui tambien.

**La imagen viaja a la API de OpenAI**, que es la que la lee. No hay forma de que un sistema como este funcione sin eso. El demo no la guarda en disco ni en base de datos: Streamlit entrega los bytes en memoria, Pillow los reescala en memoria, y de ahi salen hacia la API. Aun asi salen hacia un tercero, asi que **la interfaz pide que no se suban documentos de identidad reales**.

Antes de enviarla, cada imagen se reempaqueta como JPEG por tres razones:

1. **Orientacion.** Las fotos de celular suelen venir derechas solo por un metadato EXIF, no por como estan guardados los pixeles. Sin aplicar esa rotacion, el modelo recibe una cedula acostada y la lee bastante peor.
2. **Costo.** Una foto de 4000 px no se lee mejor que una de 2000 px cuando lo que hay que leer es un numero de documento, pero cuesta mas: la API cobra las imagenes por mosaicos y los mosaicos crecen con la resolucion. Se reescala al lado maximo de 2000 px.
3. **Metadatos.** Reempaquetar descarta el EXIF, y el EXIF de una foto de celular puede traer coordenadas GPS, modelo del equipo y fecha. Nada de eso hace falta para leer un documento. Hay una prueba que lo verifica sobre los bytes que de verdad se envian, no es una promesa.

Lo que no se gana es peso, y vale decirlo porque la primera version de este documento afirmaba lo contrario. Se midio con una cedula real del repositorio de prueba: **129 KB en PNG salieron como 327 KB en JPEG**. Reescalar una foto grande si aliviana mucho, pero una imagen que ya estaba por debajo del lado maximo solo se reempaqueta, y un JPEG de calidad 85 sobre un escaneo de colores planos puede pesar mas que el PNG original. Se acepta ese costo porque la razon 3 vale mas que 200 KB de subida, y porque los tokens los fija el tamano en pixeles, no los bytes del archivo.

## Un expediente se arma por partes

El dictamen INCOMPLETO no es un callejon sin salida. Dice cuales documentos faltan, y se agregan en el mismo cargador para volver a analizar.

Lo que hace que eso sea practico es que **cada lectura se cachea por una huella del contenido**, no del nombre. Agregar la inscripcion a un expediente de cuatro documentos cuesta una llamada a la IA, no cinco. El mismo archivo subido otra vez con otro nombre da la misma huella y se reutiliza; un archivo distinto con el mismo nombre da otra y se lee. Hay una prueba que lo mide contando llamadas, con la lectura real reemplazada por una falsa.

Esto importa por una razon que no es tecnica: la notificacion que genera el sistema es un correo dirigido al aspirante, y pedirle por correo que envie lo que falta tiene todo el sentido. En una pantalla donde el usuario acaba de subir archivos, ese mismo texto se lee como un boton roto. Por eso el dictamen ahora dice, aparte del correo, que hacer y donde.

## Como correrlo localmente

### 1. Clonar el repo

```bash
git clone https://github.com/ferquintero2013/postulaciones-mvp-utel.git
cd postulaciones-mvp-utel
```

### 2. Crear el entorno virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac y Linux
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar la API key

Crear un archivo `.env` en la raiz:

```
OPENAI_API_KEY=sk-tu-api-key-aqui
```

### 5. Correr Streamlit

```bash
streamlit run app.py
```

Se abre en http://localhost:8501

## Pruebas

```bash
python test_upload.py
```

35 verificaciones que no llaman a ninguna API y no gastan un solo token, asi que se pueden correr en cada cambio sin pensarlo. Cubren el contrato compartido entre las dos fuentes de documentos, la normalizacion de imagenes (reescalado, rotacion EXIF, PNG con transparencia, metadatos descartados), los archivos que deben rechazarse y por que, las reglas del validador que toca la carga de archivos, y la cache de lecturas.

Esa ultima parte entro por un bug real. La regla 1 compara el tipo detectado contra el tipo esperado, y la condicion era `if document['expected_type']`. La cadena `'desconocido'` es verdadera en Python, asi que todo archivo sin tipo esperado producia el problema falso "Tipo detectado (cedula) no coincide con esperado (desconocido)". Con los documentos de ejemplo casi no se veia, porque se llaman `cedula.jpg` y `diploma.png`. Con archivos que sube cualquiera, un nombre como `IMG_4821.jpg` es lo normal, y el falso positivo habria pasado a ser la regla en vez de la excepcion. Las pruebas verifican las dos mitades del arreglo: que no se invente el problema cuando no hay expectativa, y que la regla siga disparando cuando el desajuste es real. Un arreglo que apaga la regla entera no es un arreglo.

## Limitaciones conocidas

- **El demo publico no tiene autenticacion.** Cada documento que entra es una llamada a GPT-4o que alguien paga. Hay topes de 6 documentos por corrida y de 20 MB por archivo, pero eso acota el costo de una corrida, no el de un visitante insistente. El unico freno real es el tope de gasto de la cuenta de OpenAI.
- **No hay filtro de confidencialidad.** Esta solucion no decide que puede salir hacia un LLM y que no. En un despliegue real esa es la primera pieza a disenar, y hay tres caminos segun el nivel de exigencia: pactar los terminos de confidencialidad en el contrato con el proveedor, definir desde el principio una lista explicita de que campos pueden salir, o alojar el modelo en infraestructura propia, que es lo mas seguro y tambien lo mas caro.
- **La confianza la declara el modelo**, con lo que eso implica: hereda la variabilidad de quien la emite. Esta mitigada, no resuelta, por las cuatro reglas deterministas que la acompanan.
- **El expediente completo son cinco documentos.** Subir menos da un dictamen INCOMPLETO con la lista de los que faltan. No es un error, es la regla de expediente funcionando: se agregan los que falten y se vuelve a analizar.

## Autor

**Ferney Quintero**, AI Automation Engineer

- Portafolio: [ferney-portfolio.vercel.app](https://ferney-portfolio.vercel.app/)
- LinkedIn: [linkedin.com/in/ferney-quintero](https://linkedin.com/in/ferney-quintero)
- 1er lugar "Best AI Automation", n8n EmprendIA LATAM Hackathon 2025
