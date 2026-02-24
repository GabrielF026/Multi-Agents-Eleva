from fastapi import FastAPI
from pydantic import BaseModel

from app.orchestrator.orchestrator import Orchestrator

app = FastAPI(title="Multi Agents Eleva")

orchestrator = Orchestrator()


class MessageRequest(BaseModel):
    message: str


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: MessageRequest):
    result = await orchestrator.handle(request.message)
    return result