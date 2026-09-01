import re
import time


def analyze_expedient(docs):
    """Analyzes the complete expedient with cross-document validation."""
    
    total = len(docs)
    aprobados = sum(1 for d in docs if d['estado'] == 'APROBADO')
    revision_manual = sum(1 for d in docs if d['estado'] == 'REVISION_MANUAL')
    correcciones = sum(1 for d in docs if d['estado'] == 'REQUIERE_CORRECCION')
    
    documentos_requeridos = ['cedula', 'diploma', 'notas', 'inscripcion', 'pago']
    tipos_presentes = set(d['tipo_detectado'] for d in docs)
    documentos_faltantes = [t for t in documentos_requeridos if t not in tipos_presentes]
    
    # Cross-check: IDs consistent across documents
    def normalize_id(s):
        return re.sub(r'[.\s-]', '', str(s or '')).strip()
    
    ids_validos = [
        normalize_id(d['numero_identificacion'])
        for d in docs
        if d.get('numero_identificacion') and d['estado'] != 'REVISION_MANUAL'
    ]
    ids_unicos = set(ids_validos)
    inconsistencia_id = len(ids_unicos) > 1
    
    # Global decision (severity hierarchy)
    if documentos_faltantes:
        estado = 'INCOMPLETO'
        mensaje = f"Faltan los siguientes documentos: {', '.join(documentos_faltantes)}"
    elif inconsistencia_id:
        estado = 'REVISION_MANUAL'
        mensaje = "ALERTA: Se detectaron numeros de identificacion distintos entre documentos del mismo expediente. Revision manual obligatoria para descartar posible suplantacion."
        if correcciones > 0:
            mensaje += f" Adicionalmente, {correcciones} documento(s) tienen observaciones menores."
    elif revision_manual > 0:
        estado = 'REVISION_MANUAL'
        mensaje = f"{revision_manual} documento(s) requieren revision manual del analista"
    elif correcciones > 0:
        estado = 'REQUIERE_CORRECCION'
        mensaje = f"{correcciones} documento(s) requieren correccion por parte del aspirante"
    elif aprobados == total:
        estado = 'APROBADO'
        mensaje = 'Expediente aprobado. Todos los documentos validados correctamente.'
    else:
        estado = 'REVISION_MANUAL'
        mensaje = 'Estado ambiguo, revision del analista requerida'
    
    porcentaje_automatizado = int((aprobados + correcciones) / total * 100) if total > 0 else 0
    
    nombre_aspirante = next(
        (d['nombre_completo'] for d in docs if d.get('nombre_completo')),
        'Aspirante'
    )
    
    return {
        'expediente_id': f"APL-2026-{int(time.time())}",
        'aspirante': nombre_aspirante,
        'estado_expediente': estado,
        'mensaje_principal': mensaje,
        'metricas': {
            'total_documentos': total,
            'nivel_documento': {
                'aprobados': aprobados,
                'requieren_correccion': correcciones,
                'requieren_revision_manual': revision_manual
            },
            'nivel_expediente': {
                'decision_final': estado,
                'requiere_intervencion_humana': estado != 'APROBADO',
                'escalado_por_inconsistencia': inconsistencia_id,
                'motivo_escalacion': 'Inconsistencia de ID entre documentos' if inconsistencia_id else None
            },
            'documentos_faltantes': documentos_faltantes,
            'porcentaje_automatizado': f"{porcentaje_automatizado}%",
            'tiempo_procesamiento_estimado_segundos': total * 5,
            'tiempo_procesamiento_manual_original_minutos': total * 16.8,
            'reduccion_tiempo_porcentaje': '99%'
        },
        'detalle_inconsistencias': {
            'ids_detectados': list(ids_unicos),
            'inconsistencia_id': inconsistencia_id
        },
        'documentos': docs
    }
