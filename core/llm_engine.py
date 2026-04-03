"""
core/llm_engine.py

"Japon Arabası" Mimarisi LLM Motoru.
Tek görevi: Verilen prompt'u en stabil model üzerinden (Gemini 2.5 Flash) geçirip 
string cevap olarak döndürmek. Hata zincirleri, token hesaplayıcıları veya
karmaşık arayüzleri yoktur. Basit, performanslı ve sağlamdır.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("dd1.llm_engine")

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None


class LLMEngine:
    """Temiz, direkt enjeksiyonlu Gemini İstemcisi."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY ortam değişkeni bulunamadı. Lütfen .env dosyasını kontrol edin.")
            
        if not genai:
            raise ImportError("google-genai kütüphanesi eksik. Lütfen 'pip install google-genai' çalıştırın.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"  # En hızlı ve kararlı model

    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.5) -> str:
        """
        Metin üretimi yapar. Hata durumunda logger'a yazar ve boş string döner.
        Böylece sistemi asla çökertmez.
        """
        try:
            config = types.GenerateContentConfig(
                temperature=temperature,
            )
            if system_prompt:
                config.system_instruction = system_prompt

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            logger.error(f"[LLM_ENGINE] Gemini API hatası: {e}")
            return ""

# Singleton instance için (isteğe bağlı kullanım)
_engine_instance = None

def get_engine() -> LLMEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LLMEngine()
    return _engine_instance
