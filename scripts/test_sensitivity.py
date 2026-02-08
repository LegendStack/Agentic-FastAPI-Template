import asyncio

import numpy as np

from app.agents.azure_openai import LLMService
from app.agents.backlog.prompts import get_decompose_system_prompt


async def main():
    llm = LLMService()
    system_prompt = get_decompose_system_prompt(project_key="KAN")

    # Base
    u1 = "Space Exploration Mission to Mars"
    # Minor variation
    u2 = "Mars Space Exploration Mission"
    # Typo
    u3 = "Space Exploraton Mission to Mars"
    # Different topic
    u4 = "Skilled Trades Micro-Business"

    texts = [
        f"System: {system_prompt}\nUser: {u1}",
        f"System: {system_prompt}\nUser: {u2}",
        f"System: {system_prompt}\nUser: {u3}",
        f"System: {system_prompt}\nUser: {u4}",
    ]

    vecs = []
    for t in texts:
        vecs.append(await llm.get_embeddings(t))

    def sim(v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    print(f"Base: {u1}")
    print(f"V1 (Variation): {u2} | Sim: {sim(vecs[0], vecs[1]):.6f} | Dist: {1 - sim(vecs[0], vecs[1]):.6f}")
    print(f"V2 (Typo):      {u3} | Sim: {sim(vecs[0], vecs[2]):.6f} | Dist: {1 - sim(vecs[0], vecs[2]):.6f}")
    print(f"V3 (Different): {u4} | Sim: {sim(vecs[0], vecs[3]):.6f} | Dist: {1 - sim(vecs[0], vecs[3]):.6f}")


if __name__ == "__main__":
    asyncio.run(main())
