import google.generativeai as genai

# Pune cheia ta reală aici
genai.configure(api_key="AIzaSyBhtUZtqw2SB15VwTo2jnh3SNjtqmMN_tQ")

print("🔍 Caut modelele disponibile pentru această cheie API...")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ Model găsit: {m.name}")
except Exception as e:
    print("❌ Eroare la citirea modelelor:", str(e))