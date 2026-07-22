import logging
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("bot_unica")

TOKEN_WHATSAPP = os.getenv("TOKEN_WHATSAPP", "")
ID_TELEFONO_WHATSAPP = os.getenv("ID_TELEFONO_WHATSAPP", "")
ID_GRUPO_REPARTIDORES = os.getenv("ID_GRUPO_REPARTIDORES", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
HUB_VERIFY_TOKEN = os.getenv("HUB_VERIFY_TOKEN", "")

IA_PROVEEDORES = os.getenv("IA_PROVEEDORES", "gemini").lower().split(",")
CLAVE_API_GEMINI = os.getenv("CLAVE_API_GEMINI", "")
CLAVE_API_OPENAI = os.getenv("CLAVE_API_OPENAI", "")
CLAVE_API_ANTHROPIC = os.getenv("CLAVE_API_ANTHROPIC", "")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v25.0")
TIPO_DESTINATARIO_REPARTIDORES = os.getenv("TIPO_DESTINATARIO_REPARTIDORES", "individual")

_VARS_REQUERIDAS = {
    "TOKEN_WHATSAPP": TOKEN_WHATSAPP,
    "ID_TELEFONO_WHATSAPP": ID_TELEFONO_WHATSAPP,
    "ID_GRUPO_REPARTIDORES": ID_GRUPO_REPARTIDORES,
    "META_APP_SECRET": META_APP_SECRET,
}
_faltantes = [nombre for nombre, valor in _VARS_REQUERIDAS.items() if not valor]
if _faltantes:
    logger.warning(f"Faltan variables obligatorias: {', '.join(_faltantes)}")

TIMEOUT_WHATSAPP = (5, 10)
TIMEOUT_IA = (5, 20)

session = requests.Session()
retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

# ── Configuración del Buffer de Mensajes ──
BUFFER_TIEMPO_ACUMULACION_MS = int(os.getenv("BUFFER_TIEMPO_MS", "2500"))  # 2.5 segundos
BUFFER_MAX_MENSAJES = int(os.getenv("BUFFER_MAX_MSG", "10"))  # Límite de seguridad