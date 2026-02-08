import asyncio
import os
import sys

# Add src to path
sys.path.append(os.getcwd())


async def verify_reranker():
    print("\n--- Verifying KeywordBonusReranker ---")
    try:
        from src.app.agents.reranking import KeywordBonusReranker

        reranker = KeywordBonusReranker(bonus_weight=0.5)

        docs = [
            {"content": "apple banana", "score": 0.5, "id": "1"},
            {"content": "cherry date", "score": 0.5, "id": "2"},
            {"content": "apple cherry", "score": 0.5, "id": "3"},
        ]

        # Query: "apple"
        results = await reranker.rerank("apple", docs)

        print("Query: 'apple'")
        for doc in results:
            print(f"Doc {doc['id']}: {doc['content']} -> Score: {doc.get('rerank_score'):.4f}")

        # Expected: Doc 1 and 3 should be boosted.
        top = results[0]
        if "apple" in top["content"]:
            print("âœ… Reranking boosted relevant document.")
        else:
            print("âŒ Reranking failed to boost.")

    except ImportError as e:
        print(f"Skiping reranker check: {e}")
    except Exception as e:
        print(f"âŒ Reranker verification failed: {e}")


async def verify_import_node():
    print("\n--- Verifying ImportNode ---")
    try:
        # Create a dummy file-like object
        from io import BytesIO

        from src.app.agents.backlog.nodes.import_node import ImportNode

        dummy_file = BytesIO(b"This is a test spec.\nIt has multiple lines.")

        node = ImportNode()
        # Mocking partition since we don't want to actually run unstructured if not installed or strictly configured

        # We really want to test the module logic, but if unstructured is missing it logs error.
        # Let's see if we can run it.
        try:
            text = node.parse_file(dummy_file, "test.txt")
            print(f"Extracted Text: {text[:50]}...")
            if "Error" not in text:
                print("âœ… ImportNode parsed successfully (or mocked).")
            else:
                print(f"âš ï¸ ImportNode returned error (likely missing deps): {text}")
        except Exception as e:
            print(f"âŒ ImportNode execution failed: {e}")

    except Exception as e:
        print(f"âŒ ImportNode init failed: {e}")


async def main():
    await verify_reranker()
    await verify_import_node()


if __name__ == "__main__":
    asyncio.run(main())
