import requests
import json

def publish_advanced_app(target_url, api_token, payload, context=None, verify=True):
    url = f"{target_url}/api/v2/zero-shot-idp/projects/advanced-app"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    if context:
        headers["Ib-Context"] = context

    try:
        response = requests.post(
            url, 
            headers=headers,
            data=json.dumps(payload),
            verify=verify
        )
        response.raise_for_status()
        print(f"Request was successful. Response content: {response.content}")
        return response.json()
    except requests.exceptions.RequestException as err:
        print(f"API request failed: {err}")
        raise

if __name__ == "__main__":
    target_url = "https://aihub.instabase.com"
    api_token = "F1pNww9SDzF1DeO47CjUZXzzIV5fTx"
    org = "velocitymortgage"
    workspace = "vinay.thapa.velocity_instabase.com"
    payload = {
        "ibflowbin_path": "velocitymortgage/Velocity-IB/fs/Instabase Drive/Doc Translation/doc-translation-flow.ibflowbin",
        "icon_path": "velocitymortgage/Velocity-IB/fs/Instabase Drive/Doc Translation/icon.png",
        "app_detail": {
            "name": "vinay test",
            "version": "0.0.1",
            "description": "",
            "visibility": "PRIVATE",
            "release_notes": "INITIAL RELEASE",
            "billing_model": "default",
        },
    }
    publish_advanced_app(target_url, api_token, payload, org)