"""
Bot de Agua Única - Trujillo, Perú.
Arquitectura: Buffer de mensajes + Motor local (98%) + IA fallback (2%).
Maneja ráfagas de mensajes, estados complejos y múltiples escenarios reales.
"""
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from config import (
    ID_GRUPO_REPARTIDORES, TIPO_DESTINATARIO_REPARTIDORES,
    logger, BUFFER_TIEMPO_ACUMULACION_MS, BUFFER_MAX_MENSAJES
)
from ia_providers import crear_proveedor_ia, ResultadoAnalisis
from message_buffer import BufferMensajes, MensajeEntrante, LoteMensajes
from whatsapp_api import (
    enviar_mensaje_whatsapp, extraer_datos_webhook, generar_enlace_mapa_direccion,
    mensaje_ya_procesado,
)

# ─────────────────────────────────────────────────────────────
#  INICIALIZACIÓN GLOBAL
# ─────────────────────────────────────────────────────────────
ia_provider = crear_proveedor_ia()
buffer = BufferMensajes(
    tiempo_espera_ms=BUFFER_TIEMPO_ACUMULACION_MS,
    max_mensajes=BUFFER_MAX_MENSAJES
)

# ─────────────────────────────────────────────────────────────
#  MEMORIA DE SESIONES POR USUARIO
# ─────────────────────────────────────────────────────────────
memoria_usuarios: Dict[str, Dict[str, Any]] = {}
TIEMPO_EXPIRACION = 600  # 10 minutos

# ─────────────────────────────────────────────────────────────
#  CATÁLOGO Y SINÓNIMOS
# ─────────────────────────────────────────────────────────────
PRODUCTOS = {
    "bidon de 20 litros": ["bidon", "bidones", "bido", "bido de agua", "bido de 20", "bido 20l", "bido 20 litros", "garrafon", "garrafones"],
    "pack de botellas 600ml": ["botella", "botellas", "botellin", "botellines", "pack", "paquete", "caja", "six pack", "pack 600"],
    "pack de botellas 1L": ["botella litro", "botellas litro", "pack litro", "litro", "litros"],
    "dispensador": ["dispensador", "dispensadores", "base", "soporte", "fuentes", "dispensador de agua"],
}

UNIDADES = {
    "1": ["1", "uno", "un", "una"],
    "2": ["2", "dos", "par", "par de"],
    "3": ["3", "tres"],
    "4": ["4", "cuatro"],
    "5": ["5", "cinco"],
    "6": ["6", "seis", "media docena"],
    "10": ["10", "diez"],
    "12": ["12", "doce", "docena"],
    "20": ["20", "veinte"],
}

# ─────────────────────────────────────────────────────────────
#  PALABRAS CLAVE POR INTENCIÓN
# ─────────────────────────────────────────────────────────────
SALUDOS = [
    "hola", "buenas", "buenos dias", "buenas tardes", "buenas noches",
    "saludos", "ola", "hey", "hi", "hello", "que tal", "como estas",
    "como va", "todo bien", "buen dia", "buenas noches", "que hay",
    "aloooo", "alo", "wena", "wenas"
]

AFIRMACIONES = [
    "si", "si por favor", "claro", "claro que si", "dale", "va", "ok",
    "okay", "perfecto", "listo", "hagamoslo", "quiero", "deseo", "necesito",
    "mandame", "enviame", "pasame", "traeme", "quiero pedir", "deseo pedir",
    "necesito agua", "quiero agua", "manda agua", "envia agua", "hazme el pedido",
    "haz el pedido", "quiero hacer un pedido", "quiero ordenar", "ordena"
]

PRECIO_KEYWORDS = [
    "precio", "cuanto cuesta", "cuanto esta", "cuanto vale", "valor",
    "tarifa", "costo", "catalogo", "lista", "oferta", "promocion", "descuento",
    "combo", "pack", "formatos", "tamanos", "litros", "cuanto es", "a cuanto",
    "cuanto me sale", "cuanto me cuesta"
]

COBERTURA_KEYWORDS = [
    "reparten", "llegan", "cobertura", "zona", "distrito", "barrio",
    "urbanizacion", "cobran", "envian", "hacen delivery", "delivery",
    "a que zonas", "donde reparten", "llegan hasta", "hasta donde",
    "a que lugares", "que zonas cubren", "cubren"
]

PAGO_KEYWORDS = [
    "yape", "plin", "transferencia", "efectivo", "tarjeta", "pago", "pagar",
    "como pago", "metodo de pago", "formas de pago", "puedo pagar",
    "aceptan", "puedo pagar con", "modo de pago"
]

HORARIO_KEYWORDS = [
    "horario", "hora", "a que hora", "atienden", "abierto", "cerrado",
    "hasta que hora", "desde que hora", "domingo", "feriado", "fin de semana",
    "que dias", "a que hora abren", "a que hora cierran", "hoy atienden"
]

CONFIRMACION = [
    "confirmo", "esta bien", "asi es", "correcto", "exacto", "eso es",
    "eso mismo", "asi mero", "dale adelante", "procede", "envialo",
    "si", "sip", "sii", "ok", "okay", "va", "dale", "listo", "perfecto"
]

CANCELACION = [
    "cancelar", "cancela", "anular", "olvida", "no quiero", "ya no",
    "para", "detente", "borra", "elimina", "descarta", "olvida el pedido",
    "cancela el pedido", "ya no quiero", "no ya", "noooo"
]

CAMBIO_PEDIDO = [
    "cambiar", "cambia", "en vez de", "en lugar de", "mejor", "quiero cambiar",
    "cambie", "cambialo", "actualiza", "actualizar", "modifica", "modificar",
    "otra cosa", "otro", "otra", "diferente", "cambio de opinion"
]

REPETIR_PEDIDO = [
    "otra vez", "de nuevo", "lo mismo", "igual", "repite", "repetir",
    "el mismo", "lo de siempre", "lo de la vez pasada", "como la ultima vez"
]

ESTADO_PEDIDO = [
    "donde esta", "donde quedo", "que paso con", "llego", "ya viene",
    "cuanto falta", "demora", "tardanza", "se demora", "donde va",
    "rastrear", "seguimiento", "tracking", "mi pedido", "mi orden",
    "el repartidor", "el motorizado", "el delivery"
]

AGRADECIMIENTO = [
    "gracias", "muchas gracias", "te agradezco", "mil gracias", "genial",
    "excelente", "perfecto", "super", "bien", "muy bien", "que bueno",
    "me sirvio", "me ayudo", "eres lo maximo", "gracias bot"
]

DESPEDIDA = [
    "chao", "adios", "hasta luego", "nos vemos", "bye", "bai", "cuidate",
    "que tengas buen dia", "hasta pronto", "nos hablamos", "cuidese"
]

# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def limpiar_texto(mensaje: str) -> str:
    msg = mensaje.lower().strip()
    reemplazos = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnn")
    msg = msg.translate(reemplazos)
    msg = re.sub(r'[^a-z0-9\s]', '', msg)
    return msg

def _tiene_palabra(texto: str, lista: List[str]) -> bool:
    return any(p in texto for p in lista)

def _extraer_cantidad(texto: str) -> Optional[str]:
    for num, sinonimos in UNIDADES.items():
        if any(s in texto for s in sinonimos):
            return num
    match = re.search(r'\b(\d+)\s*(?:bidones?|botellas?|bidos?|packs?|garrafones?|dispensadores?)\b', texto)
    if match:
        return match.group(1)
    # Número suelto al inicio
    match = re.search(r'^\s*(\d+)\s+', texto)
    if match:
        return match.group(1)
    return None

def _extraer_producto(texto: str) -> Optional[str]:
    for producto, sinonimos in PRODUCTOS.items():
        if any(s in texto for s in sinonimos):
            return producto
    return None

def _extraer_direccion(texto: str) -> Optional[str]:
    # Patrones de dirección en Perú/Trujillo
    patrones = [
        r'(?:calle|jr\.?|jiron|av\.?|avenida|urb\.?|urbanizacion|mz\.?|manzana|lt\.?|lote|psj\.?|pasaje|residencial|condominio|dpto|departamento|of|oficina)\s+[a-z0-9\s]+(?:\d+)?',
        r'(?:en|a|hacia|para)\s+([a-z0-9\s]+(?:calle|avenida|jr|jiron|urb|urbanizacion|barrio|zona)\s+[a-z0-9\s]+)',
        r'\b(?:cerca de|frente a|detras de|al lado de|esquina|proximo a|entre)\s+[a-z0-9\s]+',
        r'\b(?:cuadra|cdra|cdras|cuadras)\s+\d+\b',
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None

def _tiene_indicadores_direccion(texto: str) -> bool:
    indicadores = [
        "calle", "jr", "jiron", "avenida", "av", "urb", "urbanizacion",
        "mz", "manzana", "lt", "lote", "cerca de", "frente a", "detras de",
        "al lado de", "esquina", "cuadra", "cdra", "mza", "pasaje", "psj",
        "residencial", "condominio", "departamento", "dpto", "piso", "oficina",
        "of", "prolongacion", "prol", "mza", "sector", "etapa"
    ]
    return any(ind in texto for ind in indicadores)

def _despachar_pedido(telefono: str, detalle: str, direccion: str, es_gps: bool = False):
    enlace = (
        f"https://www.google.com/maps/search/?api=1&query={direccion}"
        if es_gps else generar_enlace_mapa_direccion(direccion)
    )
    enviar_mensaje_whatsapp(
        telefono,
        "¡Excelente pedido confirmado! Tu solicitud de Agua Única ya ha sido transferida a nuestro equipo de repartidores. 🛵💨"
    )
    tipo_label = "GPS" if es_gps else "DIRECCION"
    mensaje_reparto = (
        f"🚨 *NUEVO PEDIDO DE AGUA ÚNICA ({tipo_label})* 🚨\n"
        f"- *Detalle:* {detalle}\n"
        f"- {'*Coordenadas*' if es_gps else '*Direccion*'}: {direccion}\n"
        f"- *Ruta en Google Maps:* {enlace}"
    )
    enviar_mensaje_whatsapp(
        ID_GRUPO_REPARTIDORES,
        f"📞 *Contacto Cliente:* {telefono}\n{mensaje_reparto}",
        TIPO_DESTINATARIO_REPARTIDORES
    )

# ─────────────────────────────────────────────────────────────
#  MOTOR LOCAL DE EXTRACCIÓN
# ─────────────────────────────────────────────────────────────
def _intentar_extraer_pedido_local(texto: str) -> Optional[Dict[str, Any]]:
    texto_limpio = limpiar_texto(texto)
    
    cantidad = _extraer_cantidad(texto_limpio)
    producto = _extraer_producto(texto_limpio)
    
    if not producto:
        if cantidad:
            producto = "bidon de 20 litros"  # Default más común
        else:
            return None
    
    cantidad_str = cantidad or "1"
    detalle = f"{cantidad_str} {producto}"
    
    direccion = _extraer_direccion(texto_limpio)
    
    if not direccion and _tiene_indicadores_direccion(texto_limpio):
        return {"detalle": detalle, "direccion": None, "ambigua": True}
    
    if not direccion:
        return {"detalle": detalle, "direccion": None, "ambigua": False}
    
    return {"detalle": detalle, "direccion": direccion, "ambigua": False}

# ─────────────────────────────────────────────────────────────
#  MÁQUINA DE ESTADOS
# ─────────────────────────────────────────────────────────────
def _limpiar_expirados(telefono: str):
    ahora = time.time()
    if telefono in memoria_usuarios:
        if ahora - memoria_usuarios[telefono]["timestamp"] > TIEMPO_EXPIRACION:
            del memoria_usuarios[telefono]

def _set_estado(telefono: str, estado: str, datos: Dict[str, Any]):
    memoria_usuarios[telefono] = {
        "estado": estado,
        "datos": datos,
        "timestamp": time.time(),
        "historial": memoria_usuarios.get(telefono, {}).get("historial", []) + [estado]
    }

def _get_estado(telefono: str) -> Optional[str]:
    _limpiar_expirados(telefono)
    return memoria_usuarios.get(telefono, {}).get("estado")

def _get_datos(telefono: str) -> Dict[str, Any]:
    return memoria_usuarios.get(telefono, {}).get("datos", {})

def _get_historial(telefono: str) -> List[str]:
    return memoria_usuarios.get(telefono, {}).get("historial", [])

# ─────────────────────────────────────────────────────────────
#  CONSOLIDACIÓN DE MENSAJES
# ─────────────────────────────────────────────────────────────
def _consolidar_mensajes(lote: LoteMensajes) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Une todos los mensajes del lote en un solo texto coherente.
    Retorna: (texto_consolidado, coordenadas_gps, tipo_dominante)
    """
    partes_texto = []
    coordenadas = None
    tipos = []
    
    for msg in lote.mensajes:
        tipos.append(msg.tipo)
        if msg.tipo == "texto":
            partes_texto.append(msg.contenido)
        elif msg.tipo == "ubicacion":
            coordenadas = f"{msg.datos_extra.get('latitud')},{msg.datos_extra.get('longitud')}"
    
    texto_final = " ".join(partes_texto).strip()
    
    # Determinar tipo dominante
    if "ubicacion" in tipos and partes_texto:
        tipo_dominante = "mixto"
    elif "ubicacion" in tipos:
        tipo_dominante = "ubicacion"
    else:
        tipo_dominante = "texto"
    
    return texto_final, coordenadas, tipo_dominante

# ─────────────────────────────────────────────────────────────
#  PROCESADOR DE LOTE (callback del buffer)
# ─────────────────────────────────────────────────────────────
def procesar_lote_mensajes(lote: LoteMensajes):
    """
    Función principal que procesa un lote consolidado de mensajes.
    Este es el callback que registra el buffer.
    """
    telefono = lote.telefono
    texto_consolidado, coordenadas_gps, tipo_dominante = _consolidar_mensajes(lote)
    
    logger.info(f"=== PROCESANDO LOTE {telefono} ===")
    logger.info(f"Texto consolidado: {texto_consolidado[:100]}...")
    logger.info(f"GPS: {coordenadas_gps}, Tipo: {tipo_dominante}")
    
    # Caso especial: solo ubicación GPS sin texto
    if tipo_dominante == "ubicacion" and not texto_consolidado:
        _procesar_solo_ubicacion(telefono, coordenadas_gps)
        return
    
    # Caso: mixto (texto + GPS)
    if tipo_dominante == "mixto" and coordenadas_gps:
        _procesar_mixto(telefono, texto_consolidado, coordenadas_gps)
        return
    
    # Caso normal: solo texto
    if texto_consolidado:
        _procesar_texto(telefono, texto_consolidado)
        return
    
    # Fallback
    enviar_mensaje_whatsapp(telefono, "Recibí tu mensaje pero no pude entenderlo bien. ¿Puedes intentar de nuevo? 🙏")

# ─────────────────────────────────────────────────────────────
#  SUB-PROCESADORES POR TIPO
# ─────────────────────────────────────────────────────────────
def _procesar_solo_ubicacion(telefono: str, coordenadas: str):
    estado = _get_estado(telefono)
    
    if estado == "ESPERANDO_UBICACION":
        detalle = _get_datos(telefono)["detalle"]
        _despachar_pedido(telefono, detalle, coordenadas, es_gps=True)
        del memoria_usuarios[telefono]
        return
    
    # GPS inesperado
    _set_estado(telefono, "ESPERANDO_PRODUCTO_GPS", {"ubicacion": coordenadas})
    enviar_mensaje_whatsapp(
        telefono,
        "¡Ubicación guardada! 📍 ¿Cuántos bidones o botellas deseas que te enviemos allí?"
    )

def _procesar_mixto(telefono: str, texto: str, coordenadas: str):
    estado = _get_estado(telefono)
    
    # Si estábamos esperando algo, completar con el texto
    if estado == "ESPERANDO_PRODUCTO_GPS":
        # El usuario ya había enviado GPS y ahora envió texto con el producto
        _despachar_pedido(telefono, texto, coordenadas, es_gps=True)
        del memoria_usuarios[telefono]
        return
    
    # Intentar extraer pedido del texto
    resultado = _intentar_extraer_pedido_local(texto)
    
    if resultado and resultado.get("direccion"):
        # Tiene dirección en texto PERO también envió GPS
        # Priorizar GPS para la ubicación, usar texto para el detalle
        _despachar_pedido(telefono, resultado["detalle"], coordenadas, es_gps=True)
        del memoria_usuarios[telefono]
        return
    
    if resultado:
        _despachar_pedido(telefono, resultado["detalle"], coordenadas, es_gps=True)
        del memoria_usuarios[telefono]
        return
    
    # No se pudo extraer, pedir clarificación
    _set_estado(telefono, "ESPERANDO_PRODUCTO_GPS", {"ubicacion": coordenadas})
    enviar_mensaje_whatsapp(
        telefono,
        "¡Ubicación recibida! 📍 ¿Qué productos deseas que te enviemos allí? (Ej: 2 bidones de 20 litros)"
    )

def _procesar_texto(telefono: str, texto: str):
    texto_limpio = limpiar_texto(texto)
    estado = _get_estado(telefono)
    
    # ═══════════════════════════════════════════════════════
    #  MÁQUINA DE ESTADOS ACTIVA
    # ═══════════════════════════════════════════════════════
    
    # Estado: Esperando producto después de GPS
    if estado == "ESPERANDO_PRODUCTO_GPS":
        ubicacion = _get_datos(telefono)["ubicacion"]
        _despachar_pedido(telefono, texto, ubicacion, es_gps=True)
        del memoria_usuarios[telefono]
        return
    
    # Estado: Esperando dirección
    if estado == "ESPERANDO_DIRECCION":
        detalle = _get_datos(telefono)["detalle"]
        _despachar_pedido(telefono, detalle, texto, es_gps=False)
        del memoria_usuarios[telefono]
        return
    
    # Estado: Esperando confirmación de dirección ambigua
    if estado == "ESPERANDO_CONFIRMACION_DIRECCION":
        if _tiene_palabra(texto_limpio, CONFIRMACION):
            detalle = _get_datos(telefono)["detalle"]
            direccion = _get_datos(telefono)["direccion_candidata"]
            _despachar_pedido(telefono, detalle, direccion, es_gps=False)
            del memoria_usuarios[telefono]
            return
        elif _tiene_palabra(texto_limpio, CANCELACION):
            del memoria_usuarios[telefono]
            enviar_mensaje_whatsapp(telefono, "Pedido cancelado. ¿Deseas hacer uno nuevo?")
            return
        else:
            # Nueva dirección proporcionada
            detalle = _get_datos(telefono)["detalle"]
            _set_estado(telefono, "ESPERANDO_DIRECCION", {"detalle": detalle})
            enviar_mensaje_whatsapp(
                telefono,
                f"Entendido. Enviaremos tu {detalle} a: {texto}. ¿Confirmas? (sí/no)"
            )
            return
    
    # Estado: Esperando confirmación de cambio
    if estado == "ESPERANDO_CONFIRMACION_CAMBIO":
        if _tiene_palabra(texto_limpio, CONFIRMACION):
            # Aplicar cambio
            nuevo_detalle = _get_datos(telefono).get("nuevo_detalle")
            nueva_direccion = _get_datos(telefono).get("nueva_direccion")
            detalle = nuevo_detalle or _get_datos(telefono)["detalle_original"]
            direccion = nueva_direccion or _get_datos(telefono)["direccion_original"]
            
            if not direccion or "falta" in direccion.lower():
                _set_estado(telefono, "ESPERANDO_DIRECCION", {"detalle": detalle})
                enviar_mensaje_whatsapp(
                    telefono,
                    f"¡Cambio aplicado! Ahora enviaremos: {detalle}. ¿A qué dirección? 📍"
                )
                return
            
            _despachar_pedido(telefono, detalle, direccion, es_gps=False)
            del memoria_usuarios[telefono]
            return
        elif _tiene_palabra(texto_limpio, CANCELACION):
            del memoria_usuarios[telefono]
            enviar_mensaje_whatsapp(telefono, "Cambio cancelado. ¿Algo más en lo que pueda ayudarte?")
            return
    
    # ═══════════════════════════════════════════════════════
    #  FILTROS DE INTENCIÓN (100% local, cero costo)
    # ═══════════════════════════════════════════════════════
    
    # 1. Saludos
    if _tiene_palabra(texto_limpio, SALUDOS) and len(texto_limpio.split()) <= 4:
        enviar_mensaje_whatsapp(
            telefono,
            "¡Hola! 👋 Gracias por comunicarte con *Agua Única*, tu agua mineral en Trujillo.\n\n"
            "¿Deseas realizar un pedido de bidones o botellas hoy? 🚰"
        )
        return
    
    # 2. Cancelaciones
    if _tiene_palabra(texto_limpio, CANCELACION):
        if telefono in memoria_usuarios:
            del memoria_usuarios[telefono]
        enviar_mensaje_whatsapp(telefono, "Entendido, pedido cancelado. ¿Algo más en lo que pueda ayudarte?")
        return
    
    # 3. Agradecimientos
    if _tiene_palabra(texto_limpio, AGRADECIMIENTO):
        enviar_mensaje_whatsapp(
            telefono,
            "¡Con gusto! 😊 Estamos aquí para servirte. Si necesitas algo más, no dudes en escribirnos. ¡Que tengas un excelente día! 🌟"
        )
        return
    
    # 4. Despedidas
    if _tiene_palabra(texto_limpio, DESPEDIDA):
        enviar_mensaje_whatsapp(
            telefono,
            "¡Hasta luego! 👋 Gracias por preferir Agua Única. Que tengas un excelente día. ¡Te esperamos pronto! 💧"
        )
        return
    
    # 5. Precios
    if _tiene_palabra(texto_limpio, PRECIO_KEYWORDS):
        enviar_mensaje_whatsapp(
            telefono,
            "💧 *Precios Agua Única:*\n\n"
            "• Bidón de 20L: S/ 12.00\n"
            "• Pack 6 botellas 600ml: S/ 18.00\n"
            "• Pack 6 botellas 1L: S/ 24.00\n"
            "• Dispensador: S/ 85.00\n\n"
            "¿Cuántos deseas y a qué dirección te los enviamos? 🚚"
        )
        return
    
    # 6. Cobertura
    if _tiene_palabra(texto_limpio, COBERTURA_KEYWORDS):
        enviar_mensaje_whatsapp(
            telefono,
            "🚚 *Repartimos en toda Trujillo y alrededores:*\n"
            "La Esperanza, El Porvenir, Florencia de Mora, Huanchaco, Laredo, Moche, y más.\n\n"
            "Escríbenos tu dirección exacta o envíanos tu ubicación para confirmar cobertura inmediata 📍."
        )
        return
    
    # 7. Pagos
    if _tiene_palabra(texto_limpio, PAGO_KEYWORDS):
        enviar_mensaje_whatsapp(
            telefono,
            "💳 *Métodos de pago:*\n\n"
            "• Efectivo al recibir\n"
            "• Yape / Plin\n"
            "• Transferencia bancaria\n\n"
            "¿Deseas hacer un pedido ahora? Indícanos qué necesitas. 🚰"
        )
        return
    
    # 8. Horarios
    if _tiene_palabra(texto_limpio, HORARIO_KEYWORDS):
        enviar_mensaje_whatsapp(
            telefono,
            "🕐 *Horario de atención:*\n\n"
            "• Lunes a Sábado: 8:00 AM - 8:00 PM\n"
            "• Domingos: 9:00 AM - 2:00 PM (pedidos programados)\n\n"
            "¿Para cuándo necesitas tu pedido? 📅"
        )
        return
    
    # 9. Estado de pedido / Tracking
    if _tiene_palabra(texto_limpio, ESTADO_PEDIDO):
        enviar_mensaje_whatsapp(
            telefono,
            "📦 Para verificar el estado de tu pedido, por favor indícame:\n"
            "• Tu nombre o dirección de envío\n"
            "• O la hora aproximada en que hiciste el pedido\n\n"
            "Te conectaré con un asesor para darte seguimiento inmediato. 👨‍💼"
        )
        return
    
    # 10. Cambio de pedido
    if _tiene_palabra(texto_limpio, CAMBIO_PEDIDO):
        if telefono in memoria_usuarios and _get_datos(telefono).get("detalle"):
            detalle_actual = _get_datos(telefono)["detalle"]
            _set_estado(telefono, "ESPERANDO_CONFIRMACION_CAMBIO", {
                "detalle_original": detalle_actual,
                "nuevo_detalle": None,
                "nueva_direccion": None
            })
            enviar_mensaje_whatsapp(
                telefono,
                f"Actualmente tienes: *{detalle_actual}*. ¿Qué deseas cambiar? Puedes decirme el nuevo producto o dirección. 📝"
            )
            return
        enviar_mensaje_whatsapp(
            telefono,
            "No tengo un pedido activo para cambiar. ¿Deseas hacer uno nuevo? 🚰"
        )
        return
    
    # 11. Repetir pedido
    if _tiene_palabra(texto_limpio, REPETIR_PEDIDO):
        # Aquí iría integración con base de datos de pedidos históricos
        enviar_mensaje_whatsapp(
            telefono,
            "¡Claro! Para repetir tu último pedido, necesito que me confirmes:\n"
            "¿Es para la misma dirección de siempre? 📍 (Responde sí o envía nueva dirección)"
        )
        return
    
    # 12. Afirmaciones genéricas
    if _tiene_palabra(texto_limpio, AFIRMACIONES) and len(texto_limpio.split()) <= 5:
        enviar_mensaje_whatsapp(
            telefono,
            "¡Perfecto! Por favor indícanos:\n"
            "1️⃣ ¿Cuántos bidones o botellas deseas?\n"
            "2️⃣ ¿A qué dirección o ubicación lo enviamos? 📍"
        )
        return
    
    # ═══════════════════════════════════════════════════════
    #  EXTRACCIÓN LOCAL DE PEDIDO (motor regex)
    # ═══════════════════════════════════════════════════════
    
    resultado_local = _intentar_extraer_pedido_local(texto_limpio)
    
    if resultado_local:
        detalle = resultado_local["detalle"]
        direccion = resultado_local["direccion"]
        ambigua = resultado_local.get("ambigua", False)
        
        # A. Pedido completo
        if direccion and not ambigua:
            _despachar_pedido(telefono, detalle, direccion, es_gps=False)
            return
        
        # B. Dirección ambigua (necesita confirmación)
        if ambigua:
            _set_estado(
                telefono,
                "ESPERANDO_CONFIRMACION_DIRECCION",
                {"detalle": detalle, "direccion_candidata": _extraer_direccion(texto_limpio) or "la dirección mencionada"}
            )
            enviar_mensaje_whatsapp(
                telefono,
                f"¡Anotado tu {detalle}! 📋 Detecté una dirección pero quiero confirmarla. "
                f"¿Es correcta o puedes darme más detalles? (responde 'sí' o la dirección completa)"
            )
            return
        
        # C. Pedido sin dirección
        _set_estado(telefono, "ESPERANDO_DIRECCION", {"detalle": detalle})
        enviar_mensaje_whatsapp(
            telefono,
            f"¡Anotado tu {detalle}! 📋 Para completar el envío, por favor indícanos tu dirección "
            f"completa (calle, número, urbanización) o envíanos tu ubicación de WhatsApp 📍."
        )
        return
    
    # ═══════════════════════════════════════════════════════
    #  ÚLTIMO RECURSO: IA (2% de casos)
    # ═══════════════════════════════════════════════════════
    logger.info(f"🤖 Motor local agotado. Consultando IA: {ia_provider.nombre}...")
    logger.info(f"Texto enviado a IA: {texto[:200]}...")
    
    resultado_ia: Optional[ResultadoAnalisis] = ia_provider.analizar_pedido(texto)
    
    if not resultado_ia:
        enviar_mensaje_whatsapp(
            telefono,
            "Estamos teniendo dificultades técnicas. Por favor, escríbenos algo como:\n"
            "\"2 bidones para Jr. Gamarra 123, Trujillo\" y te atenderemos de inmediato. 🙏"
        )
        return
    
    if not resultado_ia.es_pedido:
        enviar_mensaje_whatsapp(
            telefono,
            "¡Hola! Para procesar tu pedido de Agua Única, por favor indícanos:\n"
            "• Cantidad (ej: 2 bidones, 1 pack de botellas)\n"
            "• Dirección completa o ubicación GPS 📍"
        )
        return
    
    detalle_ia = resultado_ia.detalle_pedido or ""
    direccion_ia = resultado_ia.direccion or ""
    
    if not direccion_ia or "falta" in direccion_ia.lower():
        _set_estado(telefono, "ESPERANDO_DIRECCION", {"detalle": detalle_ia})
        enviar_mensaje_whatsapp(
            telefono,
            f"¡Anotado! Para enviar tu {detalle_ia}, por favor indícanos tu dirección completa "
            f"o envíanos tu ubicación de WhatsApp 📍."
        )
        return
    
    _despachar_pedido(telefono, detalle_ia, direccion_ia, es_gps=False)

# ─────────────────────────────────────────────────────────────
#  PUNTO DE ENTRADA DEL WEBHOOK
# ─────────────────────────────────────────────────────────────
def ejecutar_ciclo_bot(cuerpo_webhook: Dict[str, Any]) -> str:
    """
    Punto de entrada para cada webhook de Meta.
    NO procesa directamente, delega al buffer de acumulación.
    """
    datos = extraer_datos_webhook(cuerpo_webhook)
    if not datos:
        return "Ignorado (sin datos)"
    
    # Crear objeto de mensaje para el buffer
    msg = MensajeEntrante(
        id=datos.get("id", ""),
        telefono=datos["telefono"],
        contenido=datos.get("contenido", ""),
        tipo=datos["tipo"],
        timestamp=time.time(),  # En producción usar timestamp real de Meta
        datos_extra={
            "latitud": datos.get("latitud"),
            "longitud": datos.get("longitud")
        }
    )
    
    # Delegar al buffer
    resultado = buffer.recibir_mensaje(msg)
    return f"Buffer: {resultado}"

# Registrar el callback de procesamiento en el buffer
buffer.registrar_callback(procesar_lote_mensajes)