from retrieve_context import retrieve_context as retrieve_vector_context
from retrieve_context_hybrid import retrieve_context as retrieve_hybrid_context
from answer import generate_answer

'''
Runs the end-to-end RAG flow by retrieving relevant context and then generating a final answer
'''
def main() -> None:
    print("Choose retrieval model:")
    print("Press 1 for semantic/vector retrieval")
    print("Press 2 for hybrid retrieval")

    retrieval_choice = input("Enter choice: ").strip()

    if retrieval_choice == "1":
        retrieve_fn = retrieve_vector_context
        retrieval_name = "semantic/vector retrieval"
    elif retrieval_choice == "2":
        retrieve_fn = retrieve_hybrid_context
        retrieval_name = "hybrid retrieval"
    else:
        print("Invalid choice.")
        return

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

    contexts = retrieve_fn(question, top_k=top_k)

    if not contexts:
        print("No relevant context found.")
        return

    answer = generate_answer(question, contexts)

    print(f"\nUsing: {retrieval_name}")
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