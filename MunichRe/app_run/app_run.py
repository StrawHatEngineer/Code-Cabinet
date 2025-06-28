import requests

host = "https://aihub.instabase.com"
token = "i1wdfG1ptR4zkpPo9b2g2kHqBhLoJN"
workspace = "vinay.thapa_instabase.com"
org = "ib-internal"

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
    print(response.json())
    return response.json()["id"]


def upload_file(batch_id, file_path="/Volumes/lonewolf/Code-Cabinet/MunichRe/All in One 3.pdf"):
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

deployment_id = "019715ad-4949-766a-864a-50ca8dff1b61"  
run_response = run_deployment(batch_id, deployment_id)

print(f"Run response: {run_response}")