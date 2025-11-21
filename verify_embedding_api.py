
import google.genai as genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "test_gemini_key":
    print("Skipping test: No valid API key found (using dummy)")
    # We can't really test without a key, but we can check imports
    print("Imports successful. SDK installed.")
    exit(0)

client = genai.Client(api_key=api_key)

model = "models/gemini-embedding-001"
texts = ["Hello world", "Another text", "Third text"]

print(f"Testing batch embedding with model: {model}")
print(f"Input texts: {texts}")

try:
    # Test 1: Standard embed_content with list
    print("\n--- Test 1: client.models.embed_content(contents=list) ---")
    result = client.models.embed_content(
        model=model,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=768
        )
    )

    print(f"Result type: {type(result)}")

    if result.embeddings:
        print(f"Embeddings found: {len(result.embeddings)}")
        first_emb = result.embeddings[0]
        print(f"First embedding values length: {len(first_emb.values)}")
    else:
        print("No embeddings returned.")

except Exception as e:
    print(f"Test 1 failed: {e}")
