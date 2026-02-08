import asyncio

import numpy as np

from app.agents.azure_openai import LLMService
from app.agents.backlog.prompts import get_decompose_system_prompt


async def main():
    llm = LLMService()

    system_prompt = get_decompose_system_prompt(project_key="KAN")

    prompt_mars = "Space Exploration Mission to Mars"
    prompt_trades = (
        "Skilled Trades Micro-Business (Plumbing, Electrical, HVAC fixes) Mobile/on-demand service for home repairs"
    )

    # Simulate how LangChain might stringify messages for caching
    # Usually it's just the content concatenation or separate embeddings
    # If it embeds the whole thing:
    text_mars = f"System: {system_prompt}\nUser: {prompt_mars}"
    text_trades = f"System: {system_prompt}\nUser: {prompt_trades}"

    print(f"System Prompt Length: {len(system_prompt)}")
    print(f"Mars Prompt Length: {len(prompt_mars)}")
    print(f"Trades Prompt Length: {len(prompt_trades)}")

    vec_mars = await llm.get_embeddings(text_mars)
    vec_trades = await llm.get_embeddings(text_trades)

    # Cosine similarity
    dot = np.dot(vec_mars, vec_trades)
    norm_m = np.linalg.norm(vec_mars)
    norm_t = np.linalg.norm(vec_trades)
    similarity = dot / (norm_m * norm_t)

    print(f"\nCosine Similarity: {similarity:.4f}")
    print(f"Distance (1 - Sim): {1 - similarity:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
