import json
from typing import Optional
from config import CLAVE_API_OPENAI, OPENAI_MODEL, TIMEOUT_IA, logger, session
from .base import ProveedorIA, ResultadoAnalisis

PROMPT_SISTEMA = """
Eres el motor de extracción para "Agua Única" en Trujillo, Perú.
Devuelve ÚNICAMENTE JSON válido, sin markdown ni explicaciones:

{
  "es_pedido": true/false,
  "detalle_pedido": "cantidad y producto",
  "direccion": "calle y número",
  "confianza": 0.0-1.0
}

Si no es pedido válido:
{"es_pedido": false, "razon": "falta_datos", "confianza": 0.8}
"""

class OpenAIProvider(ProveedorIA):
    def __init__(self):
        self._clave = CLAVE_API_OPENAI
        self._modelo = OPENAI_MODEL
        self._url = "https://api.openai.com/v1/chat/completions"

    @property
    def nombre(self) -> str:
        return f"OpenAI ({self._modelo})"

    def esta_disponible(self) -> bool:
        return bool(self._clave)

    def analizar_pedido(self, mensaje_usuario: str) -> Optional[ResultadoAnalisis]:
        if not self.esta_disponible():
            return None

        payload = {
            "model": self._modelo,
            "messages": [
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": mensaje_usuario}
            ],
            "temperature": 0.1,
            "max_tokens": 300,
            "response_format": {"type": "json_object"}
        }
        cabeceras = {"Authorization": f"Bearer {self._clave}", "Content-Type": "application/json"}

        try:
            respuesta = session.post(self._url, json=payload, headers=cabeceras, timeout=TIMEOUT_IA)
            respuesta.raise_for_status()
            datos = json.loads(respuesta.json()["choices"][0]["message"]["content"].strip())

            return ResultadoAnalisis(
                es_pedido=datos.get("es_pedido", False),
                detalle_pedido=datos.get("detalle_pedido"),
                direccion=datos.get("direccion"),
                razon_rechazo=datos.get("razon"),
                confianza=datos.get("confianza", 0.5),
            )
        except Exception as exc:
            logger.error(f"Error crítico OpenAI: {exc}")
            return None