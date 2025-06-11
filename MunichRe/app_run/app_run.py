import requests

host = "https://aihub.instabase.com"
token = "tW5mdeAJxJh00HJoab3lV5eL79rAfs"
workspace = "VCC-API"
org = "velocitymortgage"

def create_batch():
    response = requests.post(
        f"{host}/api/v2/batches",
        headers={
            "Authorization": f"Bearer {token}",
            "Ib-Context": org
        },
        json={
            "name": "batch_1",
            "workspace": workspace
        },
    )
    return response.json()["id"]


def upload_file(batch_id, file_path="../sample/Arcelay.pdf"):
    with open(file_path, 'rb') as f:
        response = requests.put(
            f"{host}/api/v2/batches/{batch_id}/files/{file_path.split('/')[-1]}",
            headers={
                "Authorization": f"Bearer {token}",
                "Ib-Context": org
            },
            data=f.read()
        )
    return response

def run_deployment(batch_id, deployment_id):
    response = requests.post(
        f"{host}/api/v2/apps/deployments/{deployment_id}/runs",
        headers={
            "Authorization": f"Bearer {token}",
            "Ib-Context": org
        },
        json={
            "batch_id": batch_id,
            "input_dir": None,
            "manual_upstream_integration": False,
            "from_timestamp": None,
            "to_timestamp": None,
            "version": None,
            "output_dir": None,
            "settings": {
                "keys": {
                    "custom": {},
                    "secret": {}
                },
                "runtime_config": {
                    "generate_post_process_pdf": True
                }
            }
        }
    )
    return response.json()

batch_id = create_batch()
file_response = upload_file(batch_id)

deployment_id = "01973178-d575-7b3b-b9fc-8afa9d0d6550"  
run_response = run_deployment(batch_id, deployment_id)

print(f"Run response: {run_response}")