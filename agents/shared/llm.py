import os


def make_llm():
    """LLM for the Band agents (text reasoning).

    Provider is chosen by LLM_PROVIDER:
      - "gemini" (default): Google Gemini 2.5 Flash (GEMINI_API_KEY).
      - "nebius": Nebius AI Studio — GPU-hosted open models via an
        OpenAI-compatible API (NEBIUS_API_KEY). Set NEBIUS_MODEL to pick the
        model (default Llama 3.1 70B). Runs inference on Nebius GPUs and removes
        the Gemini dependency/rate limits.

    Switch the whole agent fleet to Nebius with:  LLM_PROVIDER=nebius
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()

    if provider == "nebius":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url=os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/"),
            api_key=os.environ["NEBIUS_API_KEY"],
            model=os.environ.get("NEBIUS_MODEL", "meta-llama/Llama-3.3-70B-Instruct"),
            temperature=0.1,
        )

    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        google_api_key=os.environ["GEMINI_API_KEY"],
    )
