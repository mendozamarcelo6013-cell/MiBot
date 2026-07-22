import hashlib
import hmac
from typing import Any, Dict, Optional, Set
from urllib.parse import quote_plus

from config import (
    GRAPH_API_VERSION, HUB_VERIFY_TOKEN, ID_TELEFONO_WHATSAPP,
    META_APP_SECRET, TOKEN_WHATSAPP, TIMEOUT_WHATSAPP, logger, session
)

_MENSAJES_PROCESADOS: Set[str] = set()
_MAX_CACHE_MENSAJES = 2000

def verificar_firma_webhook(cuerpo_crudo: bytes, firma_header: Optional[str]) -> bool:
    if not META_APP_SECRET or not firma_header or not firma_header.startswith("sha256="):
        return False
    firma_esperada = hmac.new(META_APP_SECRET.encode("utf-8"), cuerpo_crudo, hashlib.sha256).hexdigest()
    firma_recibida = firma_header.split("sha256=", 1)[1]
    return hmac.compare_digest(firma_esperada, firma_recibida)

def extraer_datos_webhook(cuerpo: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cambios = cuerpo["entry"][0]["changes"][0]["value"]
        if "messages" not in cambios:
            return {}

        mensaje = cambios["messages"][0]
        datos_base = {"telefono": mensaje["from"], "id": mensaje.get("id", "")}
        tipo = mensaje["type"]

        if tipo == "text":
            return {**datos_base, "tipo": "texto", "contenido": mensaje["text"]["body"]}
        elif tipo == "location":
            return {**datos_base, "tipo": "ubicacion", "latitud": mensaje["location"]["latitude"], "longitud": mensaje["location"]["longitude"]}
        return {**datos_base, "tipo": "no_soportado"}
    except (KeyError, IndexError, TypeError):
        return {}

def enviar_mensaje_whatsapp(destinatario_id: str, texto: str, tipo_destinatario: str = "individual") -> bool:
    if not texto:
        return False
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ID_TELEFONO_WHATSAPP}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": tipo_destinatario,
        "to": destinatario_id,
        "type": "text",
        "text": {"preview_url": False, "body": texto[:4096]},
    }
    cabeceras = {"Authorization": f"Bearer {TOKEN_WHATSAPP}", "Content-Type": "application/json"}

    try:
        respuesta = session.post(url, json=payload, headers=cabeceras, timeout=TIMEOUT_WHATSAPP)
        return respuesta.status_code < 400
    except Exception as exc:
        logger.error(f"Error enviando WhatsApp a {destinatario_id}: {exc}")
        return False

def mensaje_ya_procesado(mensaje_id: str) -> bool:
    if mensaje_id in _MENSAJES_PROCESADOS:
        return True
    if len(_MENSAJES_PROCESADOS) >= _MAX_CACHE_MENSAJES:
        _MENSAJES_PROCESADOS.clear()
    _MENSAJES_PROCESADOS.add(mensaje_id)
    return False

def generar_enlace_mapa_direccion(direccion: str) -> str:
    consulta = f"{direccion} Trujillo La Libertad Peru"
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(consulta)}"