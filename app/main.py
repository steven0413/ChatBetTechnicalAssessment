from fastapi import FastAPI, HTTPException
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

# Modelos de datos
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

# Endpoints
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

@app.get("/")
async def root():
    return {
        "message": "Sports Betting Chatbot API - Prueba Técnica",
        "version": "1.0.0",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)