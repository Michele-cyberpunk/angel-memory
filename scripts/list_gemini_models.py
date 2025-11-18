#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ai/omi-gemini-integration')

import google.generativeai as genai
from config.settings import GeminiConfig

genai.configure(api_key=GeminiConfig.API_KEY)

print("Available Gemini models for content generation:\n")
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"  - {model.name}")
