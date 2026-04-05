import os
from core.config import cfg
from google import genai
from pathlib import Path

client = genai.Client(api_key=cfg.gemini_api_key)

system_prompt = Path("agents/prompts/ses_ustasi.txt").read_text(encoding="utf-8")
system_prompt += "\n\nBU BİLGİLER ZATEN ELİMİZDE, KESİNLİKLE TEKRAR SORMA:\n- Araç tipi: doblo\n- Çap: 12\"\n- Marka: JBL\n- Model: gt12"

system_prompt += "\n\nTEKNİK UYARI: Cihazın fabrika verisi: Fs: 30.0Hz. (Yani çok alt frekans isteniyorsa cihaz limiti 30.0Hz etrafındadır, bu durumu kullanıcıya belli ederek gerçeği söyle).\nKullanıcıya bu bilgiyi sezdirerek (Örn: 'Reis senin cihazın frekansı şu, yani anca buraya kadar ineriz' şeklinde) gerçekçi bir yaklaşım sergile."

system_prompt += "\n\nSİSTEM MESAJI: Tasarımı tamamlamak için şu bilgi eksik: 'Son olarak bagajda ayırdığın yerin en, boy, derinliği var mı yoksa limitsiz salla gitsin mi?'. Bu eksiği kullanıcıya doğal, usta ağzıyla ve doğrudan sor. Yukarıdaki teknik uyarıyı (varsa) soruyla harmanla. 'Dinliyorum' vb. robotik girişler yapma. Tek soru sor."

res = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="elimde jbl gt12 bas var arabam doblo alt frekans severim uygun kutuyu tasarlarmısın",
    config=genai.types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7
    )
)
print("RESPONSE:", res.text)
