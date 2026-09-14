import streamlit as st
from pipeline import process_expedient
from notification_generator import generate_notification
from github_client import fetch_documents_from_github


st.set_page_config(
    page_title="UTEL - Validacion Inteligente",
    page_icon="🎓",
    layout="wide"
)


# Repositorio publico con los expedientes de ejemplo. Quien quiera probar
# el MVP con sus propios documentos clona este repo y crea su carpeta.
REPO_DOCS = "https://github.com/ferquintero2013/TestUtel"
REPO_CODIGO = "https://github.com/ferquintero2013/postulaciones-mvp-utel"


# ============= HEADER =============
st.title("🎓 UTEL - Validacion Inteligente de Documentos")
st.markdown(
    "**MVP de hiperautomatizacion con IA** — Reduce de 14 minutos a 5 segundos "
    "el proceso de validacion de documentos de admision."
)
st.divider()


# ============= SIDEBAR =============
with st.sidebar:
    st.header("Como funciona")
    st.markdown("""
    1. **Ingresa** el nombre del aspirante
    2. El sistema consulta los documentos del expediente
    3. **GPT-4o Vision** extrae datos estructurados
    4. Se aplican **reglas de negocio** por documento
    5. Se hace **cross-check de identidad** entre documentos
    6. Se genera **notificacion automatica** al aspirante
    """)
    st.divider()

    st.header("Documentos de prueba")
    st.markdown(f"""
    Los expedientes viven en un repositorio publico:
    [**TestUtel**]({REPO_DOCS})

    Escribe uno de estos tres nombres en el campo:

    - `ferney`
    - `maira`
    - `Test_general`

    **Quieres probarlo con documentos propios?**
    Clona [TestUtel]({REPO_DOCS}), crea una carpeta con el nombre que
    quieras, mete ahi los documentos del expediente y ejecuta este
    MVP apuntando a tu propio repositorio. El codigo tambien es
    publico: [postulaciones-mvp-utel]({REPO_CODIGO}).
    """)

    st.divider()
    st.caption("**Stack**: Python + Streamlit + OpenAI GPT-4o + GitHub API")
    st.caption("**Autor**: Ferney Quintero")
    st.markdown("[Portafolio](https://ferney-portfolio.vercel.app/)")


# ============= INPUT =============
# El aviso va tambien fuera del sidebar: en movil el sidebar arranca
# colapsado y quien llega no sabe que escribir en el campo.
st.info(
    f"Los expedientes de prueba estan en el repositorio publico "
    f"[TestUtel]({REPO_DOCS}). Escribe uno de estos tres nombres: "
    f"**ferney**, **maira** o **Test_general**. "
    f"Si quieres probarlo con tus propios documentos, clona "
    f"[el repositorio]({REPO_DOCS}) y crea tu propia carpeta.",
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
    analizar = st.button("Analizar expediente", type="primary", use_container_width=True)


# ============= PROCESSING + RESULTS =============
if analizar:
    if not aspirante.strip():
        st.error(
            "Ingresa el nombre del aspirante. Puedes usar ferney, maira "
            "o Test_general."
        )
        st.stop()

    # Validacion previa: verificar que el aspirante existe (fast HTTP check)
    try:
        docs = fetch_documents_from_github(aspirante)
    except Exception as e:
        if "404" in str(e):
            st.error(
                f"⚠️ Aspirante **'{aspirante}'** no encontrado en el sistema "
                "institucional.\n\n"
                "Los expedientes disponibles son **ferney**, **maira** y "
                "**Test_general**. Si quieres probar con documentos propios, "
                f"clona el repositorio [TestUtel]({REPO_DOCS}) "
                "y crea tu carpeta."
            )
        else:
            st.error(f"Error consultando el sistema institucional: {e}")
        st.stop()

    if not docs:
        st.warning(
            f"El aspirante **'{aspirante}'** existe pero no tiene documentos cargados en el sistema."
        )
        st.stop()

    # Ya validado — ahora si procesar con spinner
    with st.spinner(f"Procesando {len(docs)} documentos con IA... esto tarda 20-30 segundos"):
        try:
            expediente = process_expedient(aspirante)
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
    
    st.markdown(f"### Dictamen del expediente")
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
            with st.expander(f"{emoji.get(doc['estado'], '❓')} {doc['filename']} — {doc['estado']}"):
                d1, d2 = st.columns(2)
                d1.write(f"**Tipo esperado**: {doc['tipo_esperado']}")
                d1.write(f"**Tipo detectado**: {doc['tipo_detectado']}")
                d1.write(f"**Nombre**: {doc['nombre_completo']}")
                d2.write(f"**ID**: {doc['numero_identificacion']}")
                d2.write(f"**Fecha**: {doc['fecha_documento']}")
                d2.write(f"**Confianza**: {doc['confianza']}")
                if doc['problemas_detectados']:
                    st.warning(f"**Problemas**: {', '.join(doc['problemas_detectados'])}")
    
    with tab3:
        st.json(expediente)
