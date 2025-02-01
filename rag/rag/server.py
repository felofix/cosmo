from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rag.db import make_db, rerank, load_pickled_db
from rag.query import query_with_context, translate_query
import asyncio

app = FastAPI()


class QueryRequest(BaseModel):
    query: str
    k: int = 10
    rerank: bool = False


class TranslateRequest(BaseModel):
    question: str
    documents: list[str]


db = None


@app.on_event("startup")
async def startup_event():
    global db
    db = load_pickled_db()

@app.post("/query")
async def query_endpoint(request: QueryRequest):
    print("Got query", request)
    if db is None:
        return {"success": False}
    if request.rerank:
        sources = db.query(request.query, k=5*request.k)
        sources = rerank(request.query, sources, request.k)
    else:
        sources = db.query(request.query, k=request.k)    

    return query_with_context(request.query, sources)

@app.post("/translate")
async def translate_endpoint(request: TranslateRequest):
    async def translate_document(doc):
        return await asyncio.to_thread(translate_query, request.question, doc)

    translations = await asyncio.gather(*(translate_document(doc) for doc in request.documents))
    return {"translations": translations}
