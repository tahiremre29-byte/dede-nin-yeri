import json
import logging
from pathlib import Path
from rank_bm25 import BM25Okapi

logger = logging.getLogger("dd1.bm25_service")

class BM25SearchService:
    def __init__(self):
        self.corpus = []
        self.tokenized_corpus = []
        self.bm25 = None
        self.is_ready = False
        self._knowledge_dir = Path(__file__).resolve().parents[1] / "knowledge"
        
    def load_corpus(self):
        """
        Loads the V1 knowledge files (intent_sozluk, woofer_catalog, woofers) into the BM25 corpus.
        Each entry becomes a document in the search space.
        """
        documents = []
        
        # Load intent dictionary
        intent_path = self._knowledge_dir / "intent_sozluk.json"
        if intent_path.exists():
            try:
                with open(intent_path, "r", encoding="utf-8") as f:
                    intents = json.load(f)
                    for item in intents:
                        # Combine utterance, meaning, example reply
                        text = f"{item.get('utterance', '')} {item.get('normalized_meaning', '')} {item.get('example_reply', '')}"
                        documents.append({
                            "source": "intent_sozluk.json",
                            "id": item.get('user_intent', 'unknown'),
                            "content": text.strip(),
                            "raw": item
                        })
            except Exception as e:
                logger.error(f"Error loading intent_sozluk: {e}")

        # Load woofer catalog
        catalog_path = self._knowledge_dir / "woofer_catalog.json"
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    catalog = json.load(f)
                    # catalog could be a dict of brands or list
                    if isinstance(catalog, dict) and "subwoofers" in catalog:
                        catalog = catalog["subwoofers"]
                    
                    for sub in catalog:
                        text = f"{sub.get('brand', '')} {sub.get('model', '')} {sub.get('rms_w', '')}W fs {sub.get('fs_hz', '')}"
                        documents.append({
                            "source": "woofer_catalog.json",
                            "id": f"{sub.get('brand','')} {sub.get('model','')}".strip(),
                            "content": text.strip(),
                            "raw": sub
                        })
            except Exception as e:
                logger.error(f"Error loading woofer_catalog: {e}")
                
        # Load woofers.json (if different structure)
        woofers_path = self._knowledge_dir / "woofers.json"
        if woofers_path.exists():
            try:
                with open(woofers_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for sub in data:
                            text = f"{sub.get('brand', '')} {sub.get('model', '')} {sub.get('size', '')} {sub.get('power', '')}"
                            documents.append({
                                "source": "woofers.json",
                                "id": f"{sub.get('brand','')} {sub.get('model','')}".strip(),
                                "content": text.strip(),
                                "raw": sub
                            })
            except Exception as e:
                logger.error(f"Error loading woofers.json: {e}")

        if not documents:
            logger.warning("No documents loaded into BM25 corpus.")
            return

        self.corpus = documents
        
        # Simple exact tokenizer: lowercase and split by whitespace
        self.tokenized_corpus = [doc["content"].lower().split() for doc in self.corpus]
        
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        self.is_ready = True
        logger.info(f"BM25 Search Service ready. Indexed {len(self.corpus)} documents.")

    def search(self, query: str, top_k: int = 3):
        """
        Executes a BM25 lookup. NEVER mutates application state.
        Returns the top_k matching raw dictionary entries as pure context.
        """
        if not self.is_ready or not self.bm25:
            self.load_corpus()
            if not self.is_ready:
                return []
                
        tokenized_query = query.lower().split()
        
        # Get raw scores to filter out complete misses
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-n indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0.0:  # Only return if there is at least a minimal match
                results.append({
                    "score": round(scores[idx], 3),
                    "source": self.corpus[idx]["source"],
                    "match_id": self.corpus[idx]["id"],
                    "data": self.corpus[idx]["raw"]
                })
                
        return results

# Singleton instance
bm25_db = BM25SearchService()
