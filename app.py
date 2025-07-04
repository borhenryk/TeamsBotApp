import os
import logging
import requests
from botbuilder.core import BotFrameworkAdapter, TurnContext, BotFrameworkAdapterSettings
from botbuilder.schema import Activity, ActivityTypes
from aiohttp import web
import aiohttp
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# -------------------- Load Secrets from Azure Key Vault --------------------
# Set the vault name as an environment variable or replace directly here
KEY_VAULT_NAME = os.getenv("KEY_VAULT_NAME", "kvhenryk")
KV_URI = f"https://{KEY_VAULT_NAME}.vault.azure.net"

# Use Azure Managed Identity / Environment credentials
credential = DefaultAzureCredential()
client = SecretClient(vault_url=KV_URI, credential=credential)

# Fetch secrets by name
APP_ID = client.get_secret("Bot-App-Id-new").value
APP_PASSWORD = client.get_secret("Bot-App-Password-new").value
DATABRICKS_TOKEN = client.get_secret("Databricks-Token").value

# -------------------- Bot Framework Setup --------------------
settings = BotFrameworkAdapterSettings(app_id=APP_ID, app_password=APP_PASSWORD)
adapter = BotFrameworkAdapter(settings)

# -------------------- API Endpoint --------------------
async def messages(req: web.Request) -> web.Response:
    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")
    
    async def turn_handler(turn_context: TurnContext):
        if activity.type == ActivityTypes.message:
            try:
                response = await query_llama3_model(turn_context.activity.text)
            except Exception as e:
                logging.error(f"Error in query_llama3_model: {e}")
                response = "Error querying the model."
            await turn_context.send_activity(Activity(type=ActivityTypes.message, text=response))
    
    await adapter.process_activity(activity, auth_header, turn_handler)
    return web.Response(status=200)

app = web.Application()
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    host = os.getenv("HOST", "localhost")
    port = int(os.environ.get("PORT", 3978))
    web.run_app(app, host=host, port=port)

async def query_llama3_model(user_input):
    url = "https://dbc-e629cdfb-2b4a.cloud.databricks.com/serving-endpoints/agents_main-rag_chatbot-basic_rag_demo/invocations"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
            "messages": [
                {
                    "role": "user",
                    "content": user_input
                }
            ]
        }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return "Error calling the model"
    
# Required for aiohttp.web startup
def init_func():
    return app