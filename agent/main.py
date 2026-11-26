"""AgentCore Runtime entry point: POST /invocations {"text": "..."} -> the Understood result as JSON."""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from shop_agent import understand

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload, context=None):
    text = (payload or {}).get("text", "")
    if not text.strip():
        return {"intent": "other", "items": [], "language": "en", "reply": ""}
    return understand(text).model_dump()


if __name__ == "__main__":
    app.run()
