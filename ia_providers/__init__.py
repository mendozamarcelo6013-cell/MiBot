from typing import List, Optional
from config import IA_PROVEEDORES, logger
from .base import ProveedorIA, ResultadoAnalisis
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .fallback_chain import FallbackChainProvider

__all__ = ["ProveedorIA", "ResultadoAnalisis", "crear_proveedor_ia"]

_PROVEEDORES_DISPONIBLES = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}

def crear_proveedor_ia(preferencias: Optional[List[str]] = None) -> ProveedorIA:
    prefs = preferencias or IA_PROVEEDORES
    proveedores_validos = []

    for nombre in prefs:
        nombre = nombre.strip().lower()
        if nombre in _PROVEEDORES_DISPONIBLES:
            try:
                instancia = _PROVEEDORES_DISPONIBLES[nombre]()
                proveedores_validos.append(instancia)
                logger.info(f"✅ Proveedor IA cargado: {nombre}")
            except Exception as exc:
                logger.warning(f"⚠️ No se pudo inicializar {nombre}: {exc}")
        else:
            logger.warning(f"❌ Proveedor desconocido: {nombre}")

    if not proveedores_validos:
        raise RuntimeError("No se pudo inicializar ningún proveedor de IA.")

    if len(proveedores_validos) == 1:
        return proveedores_validos[0]

    return FallbackChainProvider(proveedores_validos)