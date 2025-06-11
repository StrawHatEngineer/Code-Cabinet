import requests
import json
from utils import read_binary, upload_file, publish_advanced_app, read_image

def upload_solution(env_base_url: str, auth_token: str, target_path: str, solution_path: str) -> dict:
    binary_content = read_binary(solution_path)
    resp = upload_file(
        env_base_url,
        auth_token,
        target_path,
        binary_content,
    )
    print(resp)

def upload_image(env_base_url: str, auth_token: str, target_path: str, image_path: str) -> dict:
    image_content = read_image(image_path)
    resp = upload_file(
        env_base_url,
        auth_token,
        target_path,
        image_content,
    )
    print(resp)
    return resp



def deploy_solution(env_base_url: str, auth_token: str, solution_path: str, async_deploy: bool = False) -> dict:
    url = f"{env_base_url}/api/v2/solutions/deployed/"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + auth_token
    }
    payload = {
        "solution_path": solution_path,
        "async": async_deploy
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    
    return response.json()


if __name__ == "__main__":
    env_base_url = "https://dfx.aihub.instabase.com"
    auth_token = "3mp6BhlgBeIryq3Sr0AlZscim0N7ah"
    async_deploy = False
    solution_path = "/Users/lonewolf/Downloads/Automation/deploy_ibsolution/Doc Translation-1.0.1 (name).ibsolution"
    target_path = "datafabricx/kumar.ramakrishnan_stonehagefleming.com/fs/Instabase Drive/Doc Translation-1.0.1 (name).ibsolution"

    target_image = "datafabricx/kumar.ramakrishnan_stonehagefleming.com/fs/Instabase Drive/icon.png"
    
    # upload_solution(env_base_url, auth_token, target_path, solution_path)
    # upload_image(env_base_url, auth_token, target_image, "/Users/lonewolf/Downloads/Automation/deploy_ibsolution/icon.png")
    
    # payload = {
    #     "ibflowbin_path": target_path,
    #     "icon_path": target_image,
    #     "app_detail": {
    #         "name": "Doc Translation",
    #         "version": "1.0.1",
    #         "description": "(beta) Translate documents to another language",
    #         "visibility": "PUBLIC",
    #         "release_notes": "Upload any document to translate it to another language while preserving its layout and styling. This application works with both machine-readable and non machine-readable documents. Please note, the application is currently in Beta.",
    #         "billing_model": "default",
    #     },
    # }
    # target_org = "datafabricx"
    # target_workspace = "kumar.ramakrishnan_stonehagefleming.com"
    # publish_advanced_app(env_base_url, auth_token, payload, target_org)

    print(deploy_solution(env_base_url, auth_token, target_path, async_deploy))
