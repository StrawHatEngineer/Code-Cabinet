import requests
import os
import json

def get_file_api_root(ib_host, api_version="v2", add_files_suffix=True):
    if add_files_suffix:
        return os.path.join(*[ib_host, "api", api_version, "files"])
    return os.path.join(*[ib_host, "api", api_version])


def upload_file(ib_host, api_token, file_path, file_data):
    file_api_root = get_file_api_root(ib_host)
    url = os.path.join(file_api_root, file_path)
    headers = {"Authorization": f"Bearer {api_token}"}

    resp = requests.put(url, headers=headers, data=file_data, verify=False)

    if resp.status_code != 204:
        raise Exception(f"Upload file failed: {resp.content}")

    return resp

def read_binary(file_name):
    with open(file_name, "rb") as f:
        data = f.read()
    return data


def make_api_request(
    url, api_token, method="get", payload=None, context=None, verify=True
):
    """
    Makes an API request with common error handling and logging.  Raises an exception on failure.

    Args:
        url (str): Request URL
        api_token (str): API token
        method (str): HTTP method (get/post)
        payload (dict): Request payload for POST
        context (str): Context header value
        verify (bool): Verify SSL

    Returns:
        dict: Response JSON on success

    Raises:
        requests.exceptions.RequestException: If the API request fails.
    """
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    if context:
        headers["Ib-Context"] = context

    try:
        if method == "get":
            response = requests.get(url, headers=headers, verify=verify)
        elif method == "patch":
            response = requests.patch(
                url, headers=headers, data=json.dumps(payload), verify=verify
            )
        else:
            response = requests.post(
                url, headers=headers, data=json.dumps(payload), verify=verify
            )

        response.raise_for_status()
        print(f"Request was successful. Response content: {response.content}")
        return response.json()
    except requests.exceptions.RequestException as err:
        print(f"API request failed: {err}")
        raise


def publish_advanced_app(target_url, api_token, payload, context):
    """Publish an advanced app"""
    url = f"{target_url}/api/v2/zero-shot-idp/projects/advanced-app"
    return make_api_request(url, api_token, "post", payload, context)


def read_image(image_name):
    with open(image_name, "rb") as f:
        return f.read()