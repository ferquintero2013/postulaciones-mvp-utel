import re

from github_client import SIN_TIPO_ESPERADO, TIPOS


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
    
    # Rule 1: detected type matches expected type.
    #
    # Solo se compara cuando de verdad habia una expectativa. El tipo
    # esperado es un dato institucional: es el documento que se le pidio
    # al aspirante. Cuando no se conoce, llega como SIN_TIPO_ESPERADO, y
    # entonces no hay nada contra que comparar.
    #
    # Antes la condicion era solo `if document['expected_type']`, y la
    # cadena 'desconocido' es verdadera, asi que todo archivo sin
    # expectativa producia el problema "Tipo detectado (cedula) no
    # coincide con esperado (desconocido)". En la ruta de GitHub casi
    # nunca se veia, porque los archivos de prueba se llaman cedula.jpg
    # y diploma.png. Con documentos que sube cualquiera, un nombre como
    # IMG_4821.jpg es lo normal, y el falso positivo pasaria a ser la
    # regla en vez de la excepcion.
    esperado = document.get('expected_type')
    if esperado and esperado != SIN_TIPO_ESPERADO:
        if extracted.get('tipo_detectado') != esperado:
            problemas.append(
                f"Tipo detectado ({extracted.get('tipo_detectado')}) no coincide con esperado ({esperado})"
            )
    
    # Rule 2: name present with minimum length
    nombre = extracted.get('nombre_completo', '') or ''
    if len(nombre.strip()) < 3:
        problemas.append('Nombre no legible o ausente')
    
    # Rule 3: valid identification number.
    # Aplica a los cinco tipos conocidos, que es exactamente TIPOS. Se
    # usa la constante en vez de repetir la lista aqui, que era la
    # tercera copia del mismo vocabulario.
    if extracted.get('tipo_detectado') in TIPOS:
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
