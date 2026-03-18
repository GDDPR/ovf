from retrieve_context import retrieve_context
from answer import generate_answer


def main() -> None:
    question = input("Ask a question: ").strip()
    if not question:
        print("No question entered.")
        return

    contexts = retrieve_context(question, top_k=8)

    if not contexts:
        print("No relevant context found.")
        return

    print("\nRetrieved contexts:\n")
    for i, ctx in enumerate(contexts, start=1):
        print(f"Context {i}")
        print(f"Score:   {ctx.get('score', 0)}")
        print(f"Title:   {ctx.get('title', '')}")
        print(f"Section: {ctx.get('section', '')}")
        print(f"URL:     {ctx.get('url', '')}")
        print(f"Text:    {ctx.get('chunk_text', '')[:300]}")
        print("-" * 80)

    answer = generate_answer(question, contexts)

    print("\nGenerated answer:\n")
    print(answer)


if __name__ == "__main__":
    main()