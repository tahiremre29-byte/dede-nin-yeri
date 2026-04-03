from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Any
from services.bm25_service import bm25_db

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base (BM25)"])

class SearchQuery(BaseModel):
    query: str
    top_k: int = 3
    session_id: str | None = None

@router.post("/search")
async def exact_search(request: SearchQuery) -> List[Any]:
    """
    BM25/Exact Search kullanarak bilgi havuzunu (woofer_catalog, intent_sozluk vb.) tarar.
    Kesinlikle tasarım kararlarına etki etmez, sadece context zenginleştirmesi için verileri döner.
    """
    results = bm25_db.search(query=request.query, top_k=request.top_k)
    
    from services.history_service import history_db
    history_db.log_knowledge_lookup(session_id=request.session_id, query=request.query, matched_sources=results)
    
    return results
