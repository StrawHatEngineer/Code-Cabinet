import requests
import json
import os
import dotenv
dotenv.load_dotenv()

def get_schema(token: str, base_url: str, project_id: str, org: str) -> dict:
    """Fetch the schema from the API"""
    url = f"{base_url}/api/v2/aihub/build/projects/{project_id}/schema"
    headers = {
        "Authorization": f"Bearer {token}",
        "Ib-Context": org
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching schema: {e}")
        return {}

def post_schema(token: str, base_url: str, project_id: str, org: str, schema: dict) -> bool:
    """Update the schema via API"""
    url = f"{base_url}/api/v2/aihub/build/projects/{project_id}/schema"
    headers = {
        "Authorization": f"Bearer {token}",
        "Ib-Context": org
    }
    try:
        response = requests.post(url, headers=headers, json=schema)
        response.raise_for_status()
        print("Schema updated successfully")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error updating schema: {e}")
        return False

def copy_fields(source_class: str, target_class: str):
    """Copy fields from source to target class"""
    token = os.getenv("IB_TOKEN")
    base_url = os.getenv("IB_BASE_URL")
    project_id = os.getenv("IB_PROJECT_ID")
    org = os.getenv("IB_ORG")

    if not all([token, base_url, project_id]):
        raise ValueError("Missing environment variables: IB_TOKEN, IB_BASE_URL, IB_PROJECT_ID")

    schema = get_schema(token, base_url, project_id, org)
    if not schema:
        return

    # checking if source and target class exist
    source_class_id = None
    source_class_data = None
    target_class_id = None
    for item, data in schema.items():
        if item not in ["last_edited_at", "last_edited_class_at"]:
            if data.get("name") == source_class:
                source_class_id = item
                source_class_data = data
            if data.get("name") == target_class:
                target_class_id = item

    if not source_class_id or not target_class_id:
        print(f"Source or target class not found")
        return
    
    # modyfing the schema
    for item, data in schema.items():
        if item == target_class_id:
            data['new_fields'] = []
            for _, field_data in source_class_data['fields'].items():
                data['new_fields'].append(field_data)

    schema.pop("last_edited_at", None)
    schema.pop("last_edited_class_at", None)
    
    final_payload = {
        "classes": schema,
        "classes_are_edited": False,
        "new_classes": []
    }
    print(json.dumps(final_payload, indent=4))
    post_schema(token, base_url, project_id, org, final_payload)


if __name__ == "__main__":
    copy_fields("Driver License", "xlsx")
