from langchain_nvidia_ai_endpoints import ChatNVIDIA
import os

llm = ChatNVIDIA(
    model="nvdev/meta/llama-3.1-8b-instruct", 
    nvidia_api_key=os.getenv("NVIDIA_API_KEY"), 
    base_url = "https://integrate.api.nvidia.com/v1")
response = llm.invoke("tell me about the office tv show")
print(response.content)