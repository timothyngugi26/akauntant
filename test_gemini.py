import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

key = os.environ.get("GEMINI_API_KEY", "").strip()

if not key:
    print("❌ No GEMINI_API_KEY found in .env")
else:
    # Print partial key to verify it loaded correctly without exposing it
    print(f"Loaded key starting with: {key[:8]}... (length: {len(key)})")

    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents="Say 'API works!'",
        )
        print("✅ Success:", response.text.strip())
    except Exception as e:
        print("❌ Error:", e)