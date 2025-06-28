import requests
import json

host = "https://munichre-gsi.aihub.instabase.com"
token = "cTKpFDOWfiMOieGJrYLNVSAXpAOv"

run_id = "eddb0bef-19d0-44c3-b79f-122949540e74"
workspace = ""
org = "munichre"


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
