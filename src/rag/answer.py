import os
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "gemma3:12b")

"""
Builds a prompt from retrieved contexts and sends it to Ollama to generate the final answer
"""
def build_prompt(question: str, contexts: list[dict]) -> str:
    context_blocks = []

    for i, ctx in enumerate(contexts, start=1):
        block = (
            f"[Context {i}]\n"
            f"Title: {ctx.get('title', '')}\n"
            f"Section: {ctx.get('section', '')}\n"
            f"URL: {ctx.get('url', '')}\n"
            f"Text: {ctx.get('chunk_text', '')}\n"
        )
        context_blocks.append(block)

    joined_context = "\n\n".join(context_blocks)

    prompt = (
        "You are answering questions using only the provided policy context.\n"
        "If the answer is not clearly supported by the context, say that the answer is not found in the retrieved sections.\n"
        "Be concise and cite the section titles you used.\n\n"
        f"{joined_context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )
    return prompt


def generate_answer(question: str, contexts: list[dict]) -> str:
    prompt = build_prompt(question, contexts)

    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_CHAT_MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=300,
    )
    response.raise_for_status()

    data = response.json()
    answer = data.get("response", "").strip()

    if not answer:
        raise RuntimeError("Ollama returned an empty response.")

    return answer