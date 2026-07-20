import os
from dotenv import load_dotenv
load_dotenv()  # Esto carga las variables del archivo .env automáticamente
from fastapi import FastAPI, Request, Response, Query
from uvicorn import run
# Importamos la función principal del archivo anterior
from BotUnica import ejecutar_ciclo_bot 

app = FastAPI()

# Token inventado por ti para asegurar la conexión con Meta
TOKEN_VERIFICACION = os.getenv("TOKEN_VERIFICACION", "mi_token_secreto_123")

@app.get("/webhook")
def verificar_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: int = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """Valida el servidor ante Meta for Developers."""
    if hub_mode == "subscribe" and hub_verify_token == TOKEN_VERIFICACION:
        return Response(content=str(hub_challenge), media_type="text/plain")
    return Response(content="Verificación fallida", status_code=403)

@app.post("/webhook")
async def recibir_evento_whatsapp(request: Request):
    """Recibe las notificaciones de mensajes en tiempo real."""
    cuerpo_json = await request.json()
    
    # Pasamos el JSON crudo directamente a nuestro pipeline funcional
    ejecutar_ciclo_bot(cuerpo_json)
    
    # Meta exige un estado 200 rápido para saber que recibimos el mensaje
    return Response(content="EVENT_RECEIVED", status_code=200)

if __name__ == "__main__":
    run("servidor:app", host="0.0.0.0", port=8000, reload=True)