import json
from typing import Optional
from config import CLAVE_API_ANTHROPIC, ANTHROPIC_MODEL, TIMEOUT_IA, logger, session
from .base import ProveedorIA, ResultadoAnalisis

PROMPT_SISTEMA = """
Eres el motor de extracción para "Agua Única" en Trujillo, Perú.
Devuelve ÚNICAMENTE JSON válido:

{
  "es_pedido": true/false,
  "detalle_pedido": "cantidad y producto",
  "direccion": "calle y número",
  "confianza": 0.0-1.0
}

Si no es pedido: {"es_pedido": false, "razon": "falta_datos", "confianza": 0.8}
"""

class AnthropicProvider(ProveedorIA):
    def __init__(self):
        self._clave = CLAVE_API_ANTHROPIC
        self._modelo = ANTHROPIC_MODEL
        self._url = "https://api.anthropic.com/v1/messages"

    @property
    def nombre(self) -> str:
        return f"Anthropic ({self._modelo})"

    def esta_disponible(self) -> bool:
        return bool(self._clave)

    def analizar_pedido(self, mensaje_usuario: str) -> Optional[ResultadoAnalisis]:
        if not self.esta_disponible():
            return None

        payload = {
            "model": self._modelo,
            "max_tokens": 300,
            "temperature": 0.1,
            "system": PROMPT_SISTEMA,
            "messages": [{"role": "user", "content": mensaje_usuario}]
        }
        cabeceras = {
            "x-api-key": self._clave,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        try:
            respuesta = session.post(self._url, json=payload, headers=cabeceras, timeout=TIMEOUT_IA)
            respuesta.raise_for_status()
            texto_ia = respuesta.json()["content"][0]["text"].strip()

            if texto_ia.startswith("```"):
                texto_ia = texto_ia.replace("```json", "").replace("```", "").strip()

            datos = json.loads(texto_ia)
            return ResultadoAnalisis(
                es_pedido=datos.get("es_pedido", False),
                detalle_pedido=datos.get("detalle_pedido"),
                direccion=datos.get("direccion"),
                razon_rechazo=datos.get("razon"),
                confianza=datos.get("confianza", 0.5),
            )
        except Exception as exc:
            logger.error(f"Error crítico Anthropic: {exc}")
            return None