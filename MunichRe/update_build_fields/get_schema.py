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

# Get the schema
response = requests.get(url, headers=headers)
print(response.json())

with open("schema.json", "w") as f:
    json.dump(response.json(), f)


