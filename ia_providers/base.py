from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ResultadoAnalisis:
    es_pedido: bool
    detalle_pedido: Optional[str] = None
    direccion: Optional[str] = None
    razon_rechazo: Optional[str] = None
    confianza: float = 0.0

    def to_dict(self):
        return {
            "es_pedido": self.es_pedido,
            "detalle_pedido": self.detalle_pedido,
            "direccion": self.direccion,
            "razon": self.razon_rechazo,
            "confianza": self.confianza,
        }

class ProveedorIA(ABC):
    @property
    @abstractmethod
    def nombre(self) -> str:
        pass

    @abstractmethod
    def analizar_pedido(self, mensaje_usuario: str) -> Optional[ResultadoAnalisis]:
        pass

    def esta_disponible(self) -> bool:
        return True