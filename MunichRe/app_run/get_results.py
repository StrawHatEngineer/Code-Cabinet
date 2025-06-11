import requests
import json

host = "https://aihub.instabase.com"
token = "F1pNww9SDzF1DeO47CjUZXzzIV5fTx"

run_id = "a1a4fc4b-4a92-4344-bd72-26d8b6413f16"
workspace = "vinay.thapa_instabase.com"
org = "ib-internal"


def get_results(run_id):
    response = requests.get(
        f"{host}/api/v2/apps/runs/{run_id}/results?include_source_info=true",
        headers={
            "Authorization": f"Bearer {token}",
            "Ib-Context": org
        }
    )
    return response.json()


if __name__ == "__main__":
    results = get_results(run_id)
    
    output_file = f"results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)
