from typing import List, Optional
from config import logger
from .base import ProveedorIA, ResultadoAnalisis

class FallbackChainProvider(ProveedorIA):
    def __init__(self, proveedores: List[ProveedorIA]):
        self._proveedores = proveedores

    @property
    def nombre(self) -> str:
        return f"Cadena[{', '.join(p.nombre for p in self._proveedores)}]"

    def esta_disponible(self) -> bool:
        return any(p.esta_disponible() for p in self._proveedores)

    def analizar_pedido(self, mensaje_usuario: str) -> Optional[ResultadoAnalisis]:
        for proveedor in self._proveedores:
            if not proveedor.esta_disponible():
                continue

            logger.info(f"Intentando IA: {proveedor.nombre}")
            resultado = proveedor.analizar_pedido(mensaje_usuario)

            if resultado is not None:
                logger.info(f"✅ IA exitosa: {proveedor.nombre}")
                return resultado

            logger.warning(f"⚠️ Falló {proveedor.nombre}, siguiente...")

        logger.error("❌ Todos los proveedores IA fallaron")
        return None