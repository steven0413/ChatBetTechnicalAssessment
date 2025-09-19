from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
from .chatbot import SportsBettingChatbot

app = FastAPI(
    title="Sports Betting Chatbot API",
    description="API para chatbot de deportes y apuestas - Prueba Técnica",
    version="1.0.0"
)

# Configuración desde variables de entorno
API_BASE_URL = os.getenv("API_BASE_URL", "https://v46fnhvrjvtlrsmnismnwhdh5y0lckdl.lambda-url.us-east-1.on.aws")

# Inicializar chatbot
chatbot = SportsBettingChatbot(API_BASE_URL)

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Modelos de datos
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

# Endpoints
@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Procesar mensaje
        session_id = request.session_id or "default"
        response = await chatbot.process_query(request.message, session_id)
        
        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    is_connected = await chatbot.is_connected()
    return {"status": "healthy", "service": "chatbot", "api_connected": is_connected}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
