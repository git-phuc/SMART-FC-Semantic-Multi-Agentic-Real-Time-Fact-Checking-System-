from huggingface_hub import InferenceClient

# Trying Mistral 7B (often natively hosted and free)
MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"
# Try keys one by one
KEYS = [
    "YOUR_HF_API_KEY_1",
    "YOUR_HF_API_KEY_2",
    "YOUR_HF_API_KEY_3"
]

for i, key in enumerate(KEYS):
    print(f"Testing Key {i} with {MODEL_ID}...")
    try:
        client = InferenceClient(model=MODEL_ID, token=key)
        # Using a simple prompt to check connectivity
        response = client.text_generation("Hello, can you help me?", max_new_tokens=20)
        print(f"Key {i} SUCCESS: {response.strip()}")
    except Exception as e:
        print(f"Key {i} FAILED: {e}")
    print("-" * 30)
