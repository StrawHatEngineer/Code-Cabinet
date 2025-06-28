import requests
import json
import os
import dotenv

dotenv.load_dotenv()
token = os.getenv("IB_TOKEN")
base_url = os.getenv("IB_BASE_URL")
project_id = os.getenv("IB_PROJECT_ID")

url = f"{base_url}/api/v2/aihub/build/projects/{project_id}/schema"

headers = {
    "Authorization": f"Bearer {token}",
    "Ib-Context": "munichre"
}

# Post the schema
with open("./schema.json", "r") as f:
    schema = json.load(f)

response = requests.post(url, headers=headers, json=schema)
print(response.json())
