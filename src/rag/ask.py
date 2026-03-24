from retrieve_context import retrieve_context
from answer import generate_answer

'''
Runs the end-to-end RAG flow by retrieving relevant context and then generating a final answer
'''
def main() -> None:
    question = input("Ask a question: ").strip()
    if not question:
        print("No question entered.")
        return

    top_k_input = input("Enter top_k: ").strip()
    if not top_k_input:
        print("No top_k entered.")
        return

    try:
        top_k = int(top_k_input)
    except ValueError:
        print("top_k must be an integer.")
        return

    if top_k <= 0:
        print("top_k must be greater than 0.")
        return

    contexts = retrieve_context(question, top_k=top_k)

    if not contexts:
        print("No relevant context found.")
        return

    answer = generate_answer(question, contexts)

    print("\nGenerated answer:\n")
    print(answer)

    print("\nRetrieved contexts:\n")
    for i, ctx in enumerate(contexts, start=1):
        print(f"Context {i}")
        print(f"Score:   {ctx.get('score', 0)}")
        print(f"Title:   {ctx.get('title', '')}")
        print(f"Section: {ctx.get('section', '')}")
        print(f"URL:     {ctx.get('url', '')}")
        print(f"Text:    {ctx.get('chunk_text', '')[:300]}")
        print("-" * 80)


if __name__ == "__main__":
    main()