import asyncio
import httpx
from src.app.core.config import settings

async def check_auth():
    print(f"Testing Endpoint: {settings.AZURE_OPENAI_ENDPOINT}")
    print(f"Chat Deployment: {settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME}")
    
    chat_url = f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/{settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    
    headers = {
        "api-key": settings.AZURE_OPENAI_API_KEY.get_secret_value(),
        "Content-Type": "application/json"
    }
    
    chat_body = {
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Test Chat
            response = await client.post(chat_url, headers=headers, json=chat_body, timeout=10.0)
            print(f"Chat Status: {response.status_code}")
            if response.status_code == 200:
                print("SUCCESS: Azure OpenAI Chat Authentication Successful!")
            else:
                print(f"FAILURE: Chat returned {response.status_code}")

            # 2. Test Embeddings
            embed_deployment = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME
            print(f"Embeddings Deployment: {embed_deployment}")
            embed_url = f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/{embed_deployment}/embeddings?api-version={settings.AZURE_OPENAI_API_VERSION}"
            embed_body = {"input": "Hello world"}
            
            response_embed = await client.post(embed_url, headers=headers, json=embed_body, timeout=10.0)
            print(f"Embeddings Status: {response_embed.status_code}")
            if response_embed.status_code == 200:
                print("SUCCESS: Azure OpenAI Embeddings Authentication Successful!")
            else:
                print(f"FAILURE: Embeddings returned {response_embed.status_code}")
                
        except Exception as e:
            print(f"ERROR: Request Failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_auth())
