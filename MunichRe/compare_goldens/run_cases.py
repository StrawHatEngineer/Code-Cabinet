import os
import requests
import dotenv
import time
import json
import pandas as pd

dotenv.load_dotenv()    

host = os.getenv("IB_BASE_URL")
token = os.getenv("IB_TOKEN")
workspace = os.getenv("IB_WORKSPACE")
org = os.getenv("IB_ORG")
job_ids = []

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

def upload_file(batch_id, file_path):
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
                }
            }
        }
    )
    return response.json()

def run_cases():
    cases_dir = "./cases"
    deployment_id = "019759b4-ff64-7cec-b41b-55597c5a8c22"

    # Iterate through each case folder
    for case_folder in os.listdir(cases_dir):
        case_path = os.path.join(cases_dir, case_folder)
        
        if os.path.isdir(case_path):
            print(f"\nProcessing case: {case_folder}")
            
            # Create new batch for each case
            batch_id = create_batch()
            
            # Upload all files in the case folder
            for file_name in os.listdir(case_path):
                file_path = os.path.join(case_path, file_name)
                if os.path.isfile(file_path):
                    print(f"Uploading file: {file_name}")
                    file_response = upload_file(batch_id, file_path)
            
            # Run deployment for this case
            run_response = run_deployment(batch_id, deployment_id)
            job_ids.append(run_response["id"])
            print(f"Run response for {case_folder}: {run_response}")

def check_status(job_id, threshold=2000):
    url = f'{host}/api/v2/apps/runs/{job_id}'
    payload = {}
    headers = {
        'IB-Context': org,
        'Authorization': f'Bearer {token}'
    }
    is_running = True
    is_timeout = False
    start_time = time.time()

    # Wait for the job to finish
    while is_running:
        time.sleep(10)
        response = requests.request("GET", url, headers=headers, data=payload)
        status = json.loads(response.text)['status']
        if status not in ['RUNNING', 'PENDING']:
            is_running = False
        if time.time() - start_time > threshold:
            is_running = False
            is_timeout = True
            break
    if is_timeout:
        print(f"Job {job_id} timed out after {threshold} seconds")
    return is_running, is_timeout

def fetch_results(job_id):
    payload = {}
    headers = {
        'IB-Context': org,
        'Authorization': f'Bearer {token}'
    }
    results = None
    file_offset = 0
    while True:
        results_url = f'{host}/api/v2/apps/runs/{job_id}/results'
        params = {
            "include_validation_results": "true",
            "include_source_info": "true",
            "include_confidence_scores": "true",
            "file_offset": file_offset
        }
        query_string = "&".join(f"{key}={value}" for key, value in params.items())
        results_url = f"{results_url}?{query_string}"

        response = requests.request("GET", results_url, headers=headers, data=payload)
        curr_result = json.loads(response.text)
        if results is None:
            results = curr_result
        else:
            results['files'].extend(curr_result.get('files', []))

        if not curr_result.get('has_more', False):
            break
        file_offset += len(curr_result.get('files', []))
    print(f'AIHub results: {results}')
    return results

def create_expected_results(results):    
    rows = []    
    for file in results['files']:
        for document in file['documents']:
            row = {
                'filename': file['original_file_name'],
                'classification': document['class_name']
            }
            for field in document['fields']:
                row[field['field_name']] = field['value']
            rows.append(row)
    return rows

def get_results():
    rows = []
    for job_id in job_ids:
        is_running, is_timeout = check_status(job_id)
        if not is_running and not is_timeout:
            results = fetch_results(job_id)
            rows.extend(create_expected_results(results))
        else:
            print(f"Job {job_id} is timed out")
    df = pd.DataFrame(rows)
    df.to_csv('extracted_results.csv', index=False)

if __name__ == "__main__":    
    run_cases()
    get_results()
    

