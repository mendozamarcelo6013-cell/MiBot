import json
import re
from typing import Optional
from config import CLAVE_API_GEMINI, GEMINI_MODEL, TIMEOUT_IA, logger, session
from .base import ProveedorIA, ResultadoAnalisis

PROMPT_SISTEMA = """
Eres el motor de extracción para "Agua Única" en Trujillo, Perú.
Devuelve ÚNICAMENTE JSON sin markdown:

{
  "es_pedido": true,
  "detalle_pedido": "cantidad y producto exacto",
  "direccion": "calle, número o referencia exacta",
  "confianza": 0.95
}

Si no es pedido claro:
{
  "es_pedido": false,
  "razon": "falta_datos",
  "confianza": 0.8
}
"""

class GeminiProvider(ProveedorIA):
    def __init__(self):
        self._clave = CLAVE_API_GEMINI
        self._modelo = GEMINI_MODEL
        self._url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._modelo}:generateContent"

    @property
    def nombre(self) -> str:
        return f"Gemini ({self._modelo})"

    def esta_disponible(self) -> bool:
        return bool(self._clave)

    def analizar_pedido(self, mensaje_usuario: str) -> Optional[ResultadoAnalisis]:
        if not self.esta_disponible():
            return None

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": f"{PROMPT_SISTEMA}\n\nMensaje del cliente: {mensaje_usuario}"}]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300},
        }
        cabeceras = {"Content-Type": "application/json", "x-goog-api-key": self._clave}

        try:
            respuesta = session.post(self._url, json=payload, headers=cabeceras, timeout=TIMEOUT_IA)
            respuesta.raise_for_status()
            texto_ia = respuesta.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            if texto_ia.startswith("```"):
                texto_ia = texto_ia.split("```")[1]
                if texto_ia.startswith("json"):
                    texto_ia = texto_ia[4:]
            texto_ia = texto_ia.strip()

            try:
                datos = json.loads(texto_ia)
            except json.JSONDecodeError:
                datos = self._rescate_regex(texto_ia, mensaje_usuario)

            return ResultadoAnalisis(
                es_pedido=datos.get("es_pedido", False),
                detalle_pedido=datos.get("detalle_pedido"),
                direccion=datos.get("direccion"),
                razon_rechazo=datos.get("razon"),
                confianza=datos.get("confianza", 0.5),
            )

        except Exception as exc:
            logger.error(f"Error crítico Gemini: {exc}")
            return None

    def _rescate_regex(self, texto: str, original: str) -> dict:
        match_pedido = re.search(r'"es_pedido"\s*:\s*(true|false)', texto, re.IGNORECASE)
        es_pedido = match_pedido and match_pedido.group(1).lower() == 'true'

        if not es_pedido:
            return {"es_pedido": False, "razon": "rescate_fallido", "confianza": 0.3}

        match_detalle = re.search(r'"detalle_pedido"\s*:\s*"([^"]+)"', texto)
        match_dir = re.search(r'"direccion"\s*:\s*"([^"]+)"', texto)
        match_conf = re.search(r'"confianza"\s*:\s*([0-9.]+)', texto)

        return {
            "es_pedido": True,
            "detalle_pedido": match_detalle.group(1) if match_detalle else original,
            "direccion": match_dir.group(1) if match_dir else "",
            "confianza": float(match_conf.group(1)) if match_conf else 0.5
        }