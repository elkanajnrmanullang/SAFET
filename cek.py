import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY")
)

print("🔍 Sedang mengambil daftar model dari Groq...")

try:
    models = client.models.list()
    print("\n✅ BERHASIL! Berikut daftar ID model yang tersedia:")
    print("-" * 40)
    for model in models.data:
        print(f"- {model.id}")
    print("-" * 40)
    print("👉 Pilih salah satu ID di atas untuk ditaruh di file .env")
except Exception as e:
    print(f"❌ Gagal: {e}")