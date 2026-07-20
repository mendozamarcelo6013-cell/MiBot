import os
import requests
from typing import Dict, Any, Tuple

# Constantes de configuración (Aisladas e inmutables)
TOKEN_WHATSAPP: str = os.getenv("TOKEN_WHATSAPP", "")
ID_TELEFONO_WHATSAPP: str = os.getenv("ID_TELEFONO_WHATSAPP", "")
ID_GRUPO_REPARTIDORES: str = os.getenv("ID_GRUPO_REPARTIDORES", "") # ID del chat del grupo
CLAVE_API_GEMINI: str = os.getenv("CLAVE_API_GEMINI", "")

URL_GEMINI: str = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={CLAVE_API_GEMINI}"

PROMPT_SISTEMA: str = """
Eres el asistente automatizado de "Agua Única" en Trujillo, La Libertad. 
Eres el asistente de inteligencia artificial automatizado de "Agua Única", una empresa que distribuye agua mineral de manantial en la ciudad de Trujillo, La Libertad. Tu objetivo es procesar pedidos de agua, responder consultas breves y estructurar la información de despacho de forma inmediata y sin errores. Operas de forma "sin estado" (stateless), resolviendo todo con el mensaje actual del usuario.

Analiza el mensaje del usuario y clasifícalo en uno de los siguientes escenarios, respondiendo estrictamente con la estructura indicada:

---
ESCENARIO 1: ATENCIÓN GENERAL O FUERA DE HORARIO
- Si el usuario saluda, hace preguntas de precios/formatos de Agua Única, o si notas por expresiones temporales que está escribiendo de madrugada/fuera de horario.
- Regla de madrugada: Si es evidente que escribe fuera de jornada, recuérdale amablemente que nuestro horario de atención inicia a las 8:00 AM.
- Acción: Responde de manera muy amable, concisa y servicial. Máximo 2 oraciones.

Ejemplo de Respuesta General: "¡Hola! Gracias por comunicarte con Agua Única, tu agua mineral de manantial en Trujillo. ¿Deseas realizar un pedido de bidones o botellas hoy?"
Ejemplo de Respuesta de Madrugada: "Hola. Te informamos que nuestro horario de atención e inicio de repartos es a partir de las 8:00 AM. Puedes dejarnos tu pedido detallado aquí para procesarlo a primera hora."

---
ESCENARIO 2: PEDIDO SIN DIRECCIÓN O CON CONSULTA DE COBERTURA
- Si el usuario pide "Agua Única" pero no menciona dónde se encuentra, o si pregunta si llegan a una zona lejana o dudosa de Trujillo.
- Regla de no cobertura: Si el cliente menciona una zona a la que explícitamente se sabe que no hay acceso, responde con empatía: "Por el momento no contamos con cobertura en esa zona, pero estamos trabajando para implementar repartos por ahí muy pronto."
- Acción: Si solo le falta la dirección, pídesela amablemente indicando que puede escribirla (calle y número) o enviar su ubicación de WhatsApp.

---
ESCENARIO 3: PEDIDO COMPLETO CON DIRECCIÓN TEXTUAL (CRÍTICO)
- Si el usuario solicita productos de Agua Única y proporciona una calle, número o referencia en Trujillo.
- Acción: Debes estructurar el pedido y generar de forma obligatoria un enlace de búsqueda de Google Maps combinando la dirección proporcionada con el término estricto "Trujillo La Libertad Peru". Reemplaza los espacios del enlace por el signo '+'.

Devuelve la respuesta usando exactamente esta estructura de etiquetas para que el sistema pueda separarla:

[MENSAJE_CLIENTE]
¡Excelente pedido confirmado! Tu solicitud de Agua Única ya ha sido transferida a nuestro equipo de repartidores para que llegue lo antes posible a tu dirección. ¡Muchas gracias por tu preferencia!

[DESPACHO_REPARTIDORES]
🚨 *NUEVO PEDIDO DE AGUA ÚNICA* 🚨
- *Detalle:* (Lista detallada de los productos solicitados)
- *Dirección:* (Texto exacto de la dirección o referencias dadas por el cliente)
- *Ruta en Google Maps:* https://www.google.com/maps/search/?api=1&query=(Dirección+del+cliente+aquí)+Trujillo+La+Libertad+Peru
---

REGLA ESTRICTA: No inventes campos ni agregues textos fuera de las etiquetas del Escenario 3 si el caso corresponde a un despacho.
"""
def extraer_datos_webhook(cuerpo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analiza el JSON del webhook de WhatsApp. 
    Detecta si es un texto plano o una ubicación geográfica nativa.
    """
    try:
        cambios = cuerpo["entry"][0]["changes"][0]["value"]
        mensaje = cambios["messages"][0]
        telefono = mensaje["from"]
        tipo_mensaje = mensaje["type"]

        if tipo_mensaje == "text":
            return {
                "telefono": telefono,
                "tipo": "texto",
                "contenido": mensaje["text"]["body"]
            }
        
        elif tipo_mensaje == "location":
            # Si el usuario mandó ubicación nativa de WhatsApp, extraemos coordenadas
            loc = mensaje["location"]
            return {
                "telefono": telefono,
                "tipo": "ubicacion",
                "latitud": loc["latitude"],
                "longitud": loc["longitude"],
                "texto_opcional": loc.get("name", "Ubicación compartida")
            }
            
    except (KeyError, IndexError):
        return {}
    return {}


def dividir_respuesta_ia(respuesta_gemini: str) -> Tuple[str, str]:
    """
    Toma la respuesta estructurada de Gemini en el Escenario 3 
    y la divide en el mensaje para el cliente y el mensaje interno.
    """
    if "[MENSAJE_CLIENTE]" in respuesta_gemini and "[DESPACHO_REPARTIDORES]" in respuesta_gemini:
        partes = respuesta_gemini.split("[DESPACHO_REPARTIDORES]")
        cliente = partes[0].replace("[MENSAJE_CLIENTE]", "").strip()
        reparto = partes[1].strip()
        return cliente, reparto
    
    # Si no es un escenario de despacho, todo el texto va para el cliente
    return respuesta_gemini, ""


def generar_enlace_mapa_coordenadas(latitud: float, longitud: float) -> str:
    """Genera un enlace de Google Maps exacto usando coordenadas."""
    return f"https://www.google.com/maps/search/?api=1&query={latitud},{longitud}"

def consultar_gemini(mensaje_usuario: str) -> str:
    """Envía el prompt del sistema junto al mensaje del cliente a Gemini."""
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{PROMPT_SISTEMA}\n\nMensaje del cliente: {mensaje_usuario}"}]}
        ]
    }
    cabeceras = {"Content-Type": "application/json"}
    
    respuesta = requests.post(URL_GEMINI, json=payload, headers=cabeceras)
    if respuesta.status_code == 200:
        return respuesta.json()["candidates"][0]["content"]["parts"][0]["text"]
    return "Lo siento, tuvimos un problema al procesar tu pedido. Inténtalo de nuevo."


def enviar_mensaje_whatsapp(destinatario_id: str, texto: str) -> int:
    """Envía un mensaje de texto a través de la API de WhatsApp Cloud."""
    url = f"https://graph.facebook.com/v20.0/{ID_TELEFONO_WHATSAPP}/messages"
    cabeceras = {
        "Authorization": f"Bearer {TOKEN_WHATSAPP}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destinatario_id,
        "type": "text",
        "text": {"preview_url": False, "body": texto}
    }
    respuesta = requests.post(url, json=payload, headers=cabeceras)
    return respuesta.status_code

def ejecutar_ciclo_bot(cuerpo_webhook: Dict[str, Any]) -> str:
    """
    Flujo principal sin estado que procesa el webhook y despacha los mensajes correspondientes.
    """
    datos = extraer_datos_webhook(cuerpo_webhook)
    if not datos:
        return "Petición no válida"

    # CASO A: El usuario envió su ubicación nativa por el botón de WhatsApp
    if datos["tipo"] == "ubicacion":
        enlace_mapa = generar_enlace_mapa_coordenadas(datos["latitud"], datos["longitud"])
        
        mensaje_cliente = "¡Ubicación recibida! Ya pasamos las coordenadas exactas a nuestro equipo de repartidores."
        mensaje_repartidores = (
            f"🚨 *NUEVO DESPACHO (UBICACIÓN GPS)* 🚨\n"
            f"- *Cliente:* {datos['telefono']}\n"
            f"- *Ruta en Google Maps:* {enlace_mapa}"
        )
        
        enviar_mensaje_whatsapp(datos["telefono"], mensaje_cliente)
        enviar_mensaje_whatsapp(ID_GRUPO_REPARTIDORES, mensaje_repartidores)
        return "Despacho por coordenadas ejecutado"

    # CASO B: El usuario envió un mensaje de texto normal
    respuesta_ia = consultar_gemini(datos["contenido"])
    msg_cliente, msg_reparto = dividir_respuesta_ia(respuesta_ia)

    # Siempre se le responde al cliente
    enviar_mensaje_whatsapp(datos["telefono"], msg_cliente)

    # Si la IA identificó un pedido completo, mandamos los datos al grupo de repartidores
    if msg_reparto:
        # Añadimos el teléfono del cliente al inicio del reporte para el repartidor
        reporte_final = f"📞 *Contacto Cliente:* {datos['telefono']}\n{msg_reparto}"
        enviar_mensaje_whatsapp(ID_GRUPO_REPARTIDORES, reporte_final)

    return "Procesamiento de texto completado"