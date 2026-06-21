import os
from langchain_google_genai import ChatGoogleGenerativeAI

def make_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        google_api_key=os.environ["GEMINI_API_KEY"],
    )
