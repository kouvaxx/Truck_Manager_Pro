import google.generativeai as genai
import os

genai.configure(api_key="AIzaSyCSa-rrg4G3s4H3a9XV8EdRbjaULF9YUnc")

print("Listing models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
