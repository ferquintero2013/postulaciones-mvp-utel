import re


def validate_document(document, extracted):
    """Applies business rules and decides the document state."""
    
    problemas = list(extracted.get('problemas_detectados', []))
    
    # Fallback: rescue date from campos_adicionales if fecha_documento is null
    if not extracted.get('fecha_documento') and extracted.get('campos_adicionales'):
        campos = extracted['campos_adicionales']
        extracted['fecha_documento'] = (
            campos.get('fecha_expedicion') or
            campos.get('fecha_emision') or
            campos.get('fecha_grado') or
            campos.get('fecha_transaccion') or
            campos.get('fecha')
        )
    
    # Rule 1: detected type matches expected type
    if document['expected_type'] and extracted.get('tipo_detectado') != document['expected_type']:
        problemas.append(
            f"Tipo detectado ({extracted.get('tipo_detectado')}) no coincide con esperado ({document['expected_type']})"
        )
    
    # Rule 2: name present with minimum length
    nombre = extracted.get('nombre_completo', '') or ''
    if len(nombre.strip()) < 3:
        problemas.append('Nombre no legible o ausente')
    
    # Rule 3: valid identification number
    tipos_con_id = ['cedula', 'diploma', 'notas', 'inscripcion', 'pago']
    if extracted.get('tipo_detectado') in tipos_con_id:
        id_num = extracted.get('numero_identificacion')
        if not id_num:
            problemas.append('Numero de identificacion ausente')
        else:
            id_clean = re.sub(r'\s', '', str(id_num))
            if not re.match(r'^[\d.]{7,}$', id_clean):
                problemas.append('Formato de identificacion invalido')
    
    # Rule 4: date required for cedula
    if extracted.get('tipo_detectado') == 'cedula' and not extracted.get('fecha_documento'):
        problemas.append('Fecha de expedicion ausente en cedula')
    
    # Rule 5: minimum confidence
    confianza = extracted.get('confianza', 0)
    if confianza < 0.5:
        problemas.append('Confianza baja - imagen posiblemente ilegible')
    
    # Per-document decision
    if not problemas and confianza >= 0.85:
        estado = 'APROBADO'
    elif confianza < 0.5 or extracted.get('legibilidad') == 'baja':
        estado = 'REVISION_MANUAL'
    elif problemas:
        estado = 'REQUIERE_CORRECCION'
    else:
        estado = 'REVISION_MANUAL'
    
    return {
        'documento_id': document['id'],
        'filename': document['filename'],
        'tipo_esperado': document['expected_type'],
        'tipo_detectado': extracted.get('tipo_detectado'),
        'nombre_completo': extracted.get('nombre_completo'),
        'numero_identificacion': extracted.get('numero_identificacion'),
        'fecha_documento': extracted.get('fecha_documento'),
        'confianza': confianza,
        'legibilidad': extracted.get('legibilidad'),
        'problemas_detectados': problemas,
        'estado': estado,
        'campos_adicionales': extracted.get('campos_adicionales', {})
    }
