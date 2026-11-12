import streamlit as st

from github_client import (
    SIN_TIPO_ESPERADO,
    TIPOS,
    fetch_documents_from_github,
    infer_type_from_filename,
)
from notification_generator import generate_notification
from pipeline import process_expedient
from upload_client import MAX_ARCHIVOS, construir_documentos


st.set_page_config(
    page_title="UTEL - Validacion Inteligente",
    page_icon="🎓",
    layout="wide"
)


# Repositorio publico con los expedientes de ejemplo.
REPO_DOCS = "https://github.com/ferquintero2013/TestUtel"
REPO_CODIGO = "https://github.com/ferquintero2013/postulaciones-mvp-utel"

MODO_EJEMPLO = "Usar un expediente de ejemplo"
MODO_SUBIR = "Subir mis propios documentos"

# Etiqueta de la opcion "no se que documento era". Se muestra distinta de
# los cinco tipos a proposito: elegirla no significa que el sistema vaya a
# adivinar menos, significa que no hay nada contra que comparar lo que el
# modelo detecte.
OPCION_SIN_TIPO = "(sin tipo esperado)"
OPCIONES_TIPO = [OPCION_SIN_TIPO] + list(TIPOS)


# ============= HEADER =============
st.title("🎓 UTEL - Validacion Inteligente de Documentos")
st.markdown(
    "**MVP de hiperautomatizacion con IA.** Reduce de 14 minutos a 5 segundos "
    "el proceso de validacion de documentos de admision."
)
st.divider()


# ============= SIDEBAR =============
with st.sidebar:
    st.header("Como funciona")
    st.markdown("""
    1. **Entran** los documentos del expediente, de un expediente de
       ejemplo o de archivos que subas
    2. **GPT-4o Vision** extrae datos estructurados de cada imagen
    3. Se aplican **reglas de negocio** por documento
    4. Se hace **cross-check de identidad** entre documentos
    5. Se genera **notificacion automatica** al aspirante
    """)
    st.caption(
        "La IA extrae, las reglas deciden. El modelo nunca dictamina: "
        "devuelve JSON, y el dictamen sale de reglas deterministas que se "
        "pueden auditar linea por linea."
    )
    st.divider()

    st.header("Las dos formas de probarlo")
    st.markdown(f"""
    **Expediente de ejemplo.** Tres expedientes completos viven en un
    repositorio publico, [TestUtel]({REPO_DOCS}): `ferney`, `maira` y
    `Test_general`.

    **Tus propios documentos.** Subes hasta {MAX_ARCHIVOS} imagenes
    desde tu equipo y el sistema las procesa igual. No hace falta clonar
    nada.
    """)

    st.divider()
    st.caption("**Stack**: Python + Streamlit + OpenAI GPT-4o + Pillow + GitHub API")
    st.caption("**Codigo**: [postulaciones-mvp-utel](%s)" % REPO_CODIGO)
    st.caption("**Autor**: Ferney Quintero")
    st.markdown("[Portafolio](https://ferney-portfolio.vercel.app/)")


# ============= INPUT =============
modo = st.radio(
    "Que quieres analizar",
    [MODO_EJEMPLO, MODO_SUBIR],
    horizontal=True,
)

# `documentos` queda armado por cualquiera de las dos ramas y de ahi en
# adelante el camino es el mismo. El pipeline no pregunta de donde
# salieron, y es la razon por la que subir archivos no toco ni la
# extraccion ni las reglas de negocio.
documentos = None
etiqueta = ""
analizar = False


if modo == MODO_EJEMPLO:
    # El aviso va tambien fuera del sidebar: en movil el sidebar arranca
    # colapsado y quien llega no sabe que escribir en el campo.
    st.info(
        f"Los expedientes de prueba estan en el repositorio publico "
        f"[TestUtel]({REPO_DOCS}). Escribe uno de estos tres nombres: "
        f"**ferney**, **maira** o **Test_general**.",
        icon="📁"
    )

    col1, col2 = st.columns([3, 1])

    with col1:
        aspirante = st.text_input(
            "Nombre de la carpeta del aspirante",
            value="ferney",
            help=(
                "Debe coincidir con una carpeta del repositorio TestUtel. "
                "Disponibles: ferney, maira, Test_general."
            )
        )

    with col2:
        st.write("")
        st.write("")
        analizar = st.button(
            "Analizar expediente", type="primary", use_container_width=True
        )

    if analizar:
        if not aspirante.strip():
            st.error(
                "Ingresa el nombre del aspirante. Puedes usar ferney, maira "
                "o Test_general."
            )
            st.stop()

        # Validacion previa: verificar que el aspirante existe antes de
        # gastar un solo token.
        try:
            documentos = fetch_documents_from_github(aspirante)
        except Exception as e:
            if "404" in str(e):
                st.error(
                    f"⚠️ Aspirante **'{aspirante}'** no encontrado en el sistema "
                    "institucional.\n\n"
                    "Los expedientes disponibles son **ferney**, **maira** y "
                    "**Test_general**. Si quieres probar con documentos propios, "
                    f"usa la opcion **{MODO_SUBIR}** aqui arriba."
                )
            else:
                st.error(f"Error consultando el sistema institucional: {e}")
            st.stop()

        if not documentos:
            st.warning(
                f"El aspirante **'{aspirante}'** existe pero no tiene "
                "documentos cargados en el sistema."
            )
            st.stop()

        etiqueta = aspirante


else:
    # Esto es lo primero que ve quien va a subir algo, y va antes del
    # boton a proposito. La imagen sale de aqui hacia un tercero, y eso
    # se dice de frente en vez de enterrarlo en una politica.
    st.warning(
        "**Antes de subir algo.** La imagen viaja a la API de OpenAI, que "
        "es la que la lee. Este demo no la guarda en disco ni en base de "
        "datos: los bytes se procesan en memoria y se descartan al "
        "terminar. Aun asi sale de aqui hacia un servicio de terceros, asi "
        "que **no subas documentos de identidad reales**. Usa documentos "
        "de prueba, capturas tachadas, o los expedientes de ejemplo.",
        icon="⚠️"
    )

    archivos = st.file_uploader(
        f"Documentos del expediente (hasta {MAX_ARCHIVOS} imagenes)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help=(
            "Fotos o escaneos de los documentos. Se reescalan a 2000 px y "
            "se rotan segun su metadato EXIF antes de enviarse, porque una "
            "imagen acostada se lee bastante peor."
        )
    )

    tipos_elegidos = []

    if archivos:
        st.markdown("**Que documento es cada uno**")
        st.caption(
            "El tipo esperado es un dato institucional: es el documento que "
            "se le pidio al aspirante. Aqui se adivina del nombre del "
            "archivo solo para ahorrarte clics. Si lo dejas en "
            f"`{OPCION_SIN_TIPO}`, el sistema sigue detectando el tipo con "
            "Vision, pero no compara lo detectado contra nada."
        )

        for idx, archivo in enumerate(archivos):
            c_nombre, c_tipo = st.columns([2, 1])
            with c_nombre:
                st.write("")
                st.write(f"`{archivo.name}`")
            with c_tipo:
                inferido = infer_type_from_filename(archivo.name)
                indice = OPCIONES_TIPO.index(inferido) if inferido in TIPOS else 0
                elegido = st.selectbox(
                    "Tipo esperado",
                    OPCIONES_TIPO,
                    index=indice,
                    key=f"tipo_{idx}_{archivo.name}",
                    label_visibility="collapsed",
                )
            tipos_elegidos.append(
                SIN_TIPO_ESPERADO if elegido == OPCION_SIN_TIPO else elegido
            )

        st.caption(
            "Un expediente completo son cinco documentos: cedula, diploma, "
            "notas, inscripcion y pago. Si subes menos, el dictamen va a "
            "decir **INCOMPLETO** y va a listar los que faltan. Eso no es "
            "un error, es la regla de expediente funcionando."
        )

    analizar = st.button(
        "Analizar documentos",
        type="primary",
        disabled=not archivos,
    )

    if analizar:
        documentos, rechazos = construir_documentos(archivos, tipos_elegidos)

        # Un archivo que desaparece sin explicacion se lee como una falla
        # del sistema, asi que los descartes se muestran uno por uno.
        if rechazos:
            detalle = "\n".join(f"- `{n}`: {motivo}" for n, motivo in rechazos)
            st.warning(f"**Archivos que no entraron:**\n{detalle}")

        if not documentos:
            st.error(
                "Ninguno de los archivos se pudo procesar. Revisa los "
                "motivos de arriba."
            )
            st.stop()

        enviados = sum(d["_bytes_enviados"] for d in documentos) / 1024
        st.caption(
            f"{len(documentos)} documento(s) listos. "
            f"Se envian {enviados:.0f} KB de imagen reescalada."
        )

        etiqueta = "documentos subidos"


# ============= PROCESSING =============
if analizar and documentos:
    with st.spinner(
        f"Procesando {len(documentos)} documentos con IA... "
        "esto tarda 20-30 segundos"
    ):
        try:
            # Los documentos ya estan en la mano, asi que se pasan por
            # parametro. En la rama de ejemplo eso ademas evita la segunda
            # consulta identica a la API de GitHub que se hacia antes.
            expediente = process_expedient(etiqueta, documentos=documentos)
            notificacion = generate_notification(expediente)
        except Exception as e:
            st.error(f"Error procesando expediente: {e}")
            st.stop()

    # Save in session state so results persist
    st.session_state['expediente'] = expediente
    st.session_state['notificacion'] = notificacion


# ============= DISPLAY (only if we have results) =============
if 'expediente' in st.session_state:
    expediente = st.session_state['expediente']
    notificacion = st.session_state['notificacion']

    st.divider()

    # ---- Status badge ----
    estado = expediente['estado_expediente']
    color_map = {
        'APROBADO': 'green',
        'REQUIERE_CORRECCION': 'orange',
        'REVISION_MANUAL': 'red',
        'INCOMPLETO': 'blue'
    }
    color = color_map.get(estado, 'gray')

    st.markdown("### Dictamen del expediente")
    st.markdown(f"# :{color}[{estado}]")
    st.info(expediente['mensaje_principal'])

    # ---- Metrics ----
    st.markdown("### Metricas del proceso")
    m = expediente['metricas']

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total documentos", m['total_documentos'])
    c2.metric("Aprobados", m['nivel_documento']['aprobados'])
    c3.metric("Correcciones", m['nivel_documento']['requieren_correccion'])
    c4.metric("Revision manual", m['nivel_documento']['requieren_revision_manual'])

    c1, c2, c3 = st.columns(3)
    c1.metric("% Automatizado", m['porcentaje_automatizado'])
    c2.metric("Tiempo IA (seg)", m['tiempo_procesamiento_estimado_segundos'])
    c3.metric("Tiempo manual (min)", f"{m['tiempo_procesamiento_manual_original_minutos']:.0f}")

    # ---- Cross-check alert ----
    if expediente['detalle_inconsistencias']['inconsistencia_id']:
        st.error(
            f"⚠️ **Alerta de suplantacion**: Se detectaron IDs distintos en documentos "
            f"del mismo expediente: {expediente['detalle_inconsistencias']['ids_detectados']}"
        )

    st.divider()

    # ---- Tabs: Notification | Documents | JSON ----
    tab1, tab2, tab3 = st.tabs(["📧 Notificacion", "📄 Documentos", "🔍 JSON completo"])

    with tab1:
        st.markdown("**Mensaje que se enviaria al aspirante:**")
        st.markdown(f"> {notificacion}")

    with tab2:
        for doc in expediente['documentos']:
            emoji = {'APROBADO': '✅', 'REQUIERE_CORRECCION': '⚠️', 'REVISION_MANUAL': '🔴'}
            titulo = f"{emoji.get(doc['estado'], '❓')} {doc['filename']}: {doc['estado']}"
            with st.expander(titulo):
                d1, d2 = st.columns(2)
                d1.write(f"**Tipo esperado**: {doc['tipo_esperado']}")
                d1.write(f"**Tipo detectado**: {doc['tipo_detectado']}")
                d1.write(f"**Nombre**: {doc['nombre_completo']}")
                d2.write(f"**ID**: {doc['numero_identificacion']}")
                d2.write(f"**Fecha**: {doc['fecha_documento']}")
                d2.write(f"**Confianza**: {doc['confianza']}")
                if doc['problemas_detectados']:
                    st.warning(f"**Problemas**: {', '.join(doc['problemas_detectados'])}")
        st.caption(
            "**Confianza** es un valor que el propio modelo declara sobre su "
            "extraccion, no una probabilidad calibrada ni una medicion. Por "
            "eso no decide sola: es una de cinco reglas, y las otras cuatro "
            "si son deterministas."
        )

    with tab3:
        st.json(expediente)
