from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from retrieve_context import retrieve_context as retrieve_vector_context
from retrieve_context_hybrid import retrieve_context as retrieve_hybrid_context
from answer import generate_answer

app = FastAPI(title="Local RAG API")

DEFAULT_RETRIEVER = os.getenv("DEFAULT_RETRIEVER", "semantic").strip().lower()
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "8"))


class RAGRequest(BaseModel):
    question: str | None = None
    prompt: str | None = None
    input: str | None = None
    user_input: str | None = None
    retriever: str | None = None
    top_k: int | None = None


def normalize_retriever(value: str | None) -> str:
    if not value:
        return DEFAULT_RETRIEVER

    cleaned = value.strip().lower()

    if cleaned in {"semantic", "vector", "semantic/vector", "neural"}:
        return "semantic"

    if cleaned in {"hybrid", "keyword_hybrid"}:
        return "hybrid"

    return DEFAULT_RETRIEVER


def pick_question(req: RAGRequest) -> str | None:
    for candidate in (req.question, req.prompt, req.input, req.user_input):
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def retrieve_contexts(question: str, retriever: str, top_k: int) -> list[dict[str, Any]]:
    if retriever == "semantic":
        return retrieve_vector_context(question, top_k=top_k)
    return retrieve_hybrid_context(question, top_k=top_k)


def build_citations(contexts: list[dict[str, Any]], max_citations: int = 5) -> str:
    seen: set[tuple[str, str, str]] = set()
    lines: list[str] = []

    for ctx in contexts:
        title = ctx.get("title", "").strip()
        section = ctx.get("section", "").strip()
        url = ctx.get("url", "").strip()

        key = (title, section, url)
        if key in seen:
            continue
        seen.add(key)

        label = title
        if section:
            label += f" — {section}"

        if url:
            lines.append(f"- {label}: {url}")
        else:
            lines.append(f"- {label}")

        if len(lines) >= max_citations:
            break

    if not lines:
        return ""

    return "Citations:\n" + "\n".join(lines)


def format_for_assistant(answer: str, contexts: list[dict[str, Any]]) -> str:
    answer = answer.strip()
    citations_block = build_citations(contexts)

    if citations_block:
        return f"{answer}\n\n{citations_block}"

    return answer


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/rag")
def rag(req: RAGRequest) -> dict[str, str]:
    question = pick_question(req)
    if not question:
        return {"response": "No question provided."}

    retriever = normalize_retriever(req.retriever)
    top_k = req.top_k if req.top_k and req.top_k > 0 else DEFAULT_TOP_K

    contexts = retrieve_contexts(question=question, retriever=retriever, top_k=top_k)

    if not contexts:
        return {"response": "No relevant context found."}

    answer = generate_answer(question, contexts)
    final_text = format_for_assistant(answer, contexts)

    return {"response": final_text}