"""
Sistema de buffer que acumula mensajes del mismo usuario
para evitar que el bot se "ature" con mensajes en ráfaga.
"""
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from config import logger, BUFFER_TIEMPO_ACUMULACION_MS, BUFFER_MAX_MENSAJES

@dataclass
class MensajeEntrante:
    id: str
    telefono: str
    contenido: str
    tipo: str  # "texto", "ubicacion", "no_soportado"
    timestamp: float  # timestamp del webhook de Meta
    datos_extra: dict = field(default_factory=dict)  # latitud, longitud, etc.

@dataclass
class LoteMensajes:
    telefono: str
    mensajes: List[MensajeEntrante]
    timestamp_inicio: float
    timer: Optional[threading.Timer] = None
    en_procesamiento: bool = False

class BufferMensajes:
    """
    Buffer por usuario que acumula mensajes durante una ventana de tiempo.
    Cuando la ventana expira, envía TODOS los mensajes acumulados como un
    único lote para procesamiento.
    """
    
    def __init__(self, tiempo_espera_ms: int = 2500, max_mensajes: int = 10):
        self.tiempo_espera = tiempo_espera_ms / 1000.0  # a segundos
        self.max_mensajes = max_mensajes
        self._buffers: Dict[str, LoteMensajes] = {}
        self._lock = threading.Lock()
        self._callback_procesar: Optional[Callable] = None
        self._mensajes_procesados_ids: set = set()  # Deduplicación global
    
    def registrar_callback(self, callback: Callable):
        """Registra la función que procesará el lote consolidado."""
        self._callback_procesar = callback
    
    def recibir_mensaje(self, mensaje: MensajeEntrante) -> str:
        """
        Punto de entrada para cada mensaje del webhook.
        Retorna estado: "acumulado", "procesando", "ignorado"
        """
        # Deduplicación por ID de mensaje de Meta
        if mensaje.id in self._mensajes_procesados_ids:
            logger.debug(f"Mensaje {mensaje.id} ya fue procesado, ignorando.")
            return "ignorado"
        self._mensajes_procesados_ids.add(mensaje.id)
        
        # Limpiar IDs antiguos si hay muchos (prevenir memory leak)
        if len(self._mensajes_procesados_ids) > 5000:
            self._mensajes_procesados_ids = set(list(self._mensajes_procesados_ids)[-3000:])
        
        with self._lock:
            telefono = mensaje.telefono
            
            # Si ya hay un lote en procesamiento para este usuario,
            # cancelarlo y reiniciar (el usuario escribió algo nuevo)
            if telefono in self._buffers and self._buffers[telefono].en_procesamiento:
                logger.info(f"Usuario {telefono} interrumpió procesamiento anterior. Reiniciando buffer.")
                lote_anterior = self._buffers[telefono]
                if lote_anterior.timer:
                    lote_anterior.timer.cancel()
                del self._buffers[telefono]
            
            # Si no hay buffer activo, crear uno nuevo
            if telefono not in self._buffers:
                self._buffers[telefono] = LoteMensajes(
                    telefono=telefono,
                    mensajes=[mensaje],
                    timestamp_inicio=time.time()
                )
                self._iniciar_timer(telefono)
                logger.info(f"Nuevo buffer iniciado para {telefono} (msg: {mensaje.id})")
                return "acumulado"
            
            # Hay buffer activo: acumular mensaje
            lote = self._buffers[telefono]
            
            # Verificar límite de seguridad
            if len(lote.mensajes) >= self.max_mensajes:
                logger.warning(f"Buffer lleno para {telefono}, forzando procesamiento.")
                self._procesar_lote(telefono)
                return "procesando"
            
            lote.mensajes.append(mensaje)
            logger.info(f"Mensaje acumulado para {telefono}. Total en buffer: {len(lote.mensajes)}")
            
            # Reiniciar timer (la ventana se extiende con cada nuevo mensaje)
            if lote.timer:
                lote.timer.cancel()
            self._iniciar_timer(telefono)
            
            return "acumulado"
    
    def _iniciar_timer(self, telefono: str):
        """Inicia/reinicia el timer de espera para un usuario."""
        def _expirar():
            self._procesar_lote(telefono)
        
        timer = threading.Timer(self.tiempo_espera, _expirar)
        timer.daemon = True
        self._buffers[telefono].timer = timer
        timer.start()
        logger.debug(f"Timer iniciado para {telefono}: {self.tiempo_espera}s")
    
    def _procesar_lote(self, telefono: str):
        """Consolida y envía el lote al procesador."""
        with self._lock:
            if telefono not in self._buffers:
                return
            
            lote = self._buffers[telefono]
            lote.en_procesamiento = True
            
            if lote.timer:
                lote.timer.cancel()
                lote.timer = None
            
            # Ordenar mensajes por timestamp de Meta (cronológico)
            lote.mensajes.sort(key=lambda m: m.timestamp)
            
            # Eliminar del buffer ANTES de procesar (evitar bloqueos)
            del self._buffers[telefono]
        
        logger.info(f"🔄 PROCESANDO LOTE para {telefono}: {len(lote.mensajes)} mensaje(s)")
        for i, m in enumerate(lote.mensajes):
            logger.info(f"  [{i+1}] {m.tipo}: {m.contenido[:50]}...")
        
        # Llamar al callback de procesamiento
        if self._callback_procesar:
            try:
                self._callback_procesar(lote)
            except Exception as exc:
                logger.error(f"Error procesando lote de {telefono}: {exc}")
        else:
            logger.error("No hay callback registrado en el buffer!")
    
    def forzar_procesamiento(self, telefono: str):
        """Forzar procesamiento inmediato (útil para estados críticos)."""
        with self._lock:
            if telefono in self._buffers:
                self._procesar_lote(telefono)
    
    def estado_actual(self) -> Dict[str, dict]:
        """Para debugging: ver buffers activos."""
        with self._lock:
            return {
                tel: {
                    "mensajes": len(lote.mensajes),
                    "tiempo_restante": max(0, self.tiempo_espera - (time.time() - lote.timestamp_inicio)),
                    "en_proceso": lote.en_procesamiento
                }
                for tel, lote in self._buffers.items()
            }