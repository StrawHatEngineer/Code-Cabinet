import requests
import json

# Get the Loan Number.

results = json.load(open("current_result.json"))

def downstream(results):
  loan_number = None
  for record in results["records"]:
    if record["classification_label"] == "Term Note":
      for field in record["results"]:
        if field["key"] == "Loan_Number":
          loan_number = str(field["value"])
          break
    if loan_number:
      break


  for record in results["records"]:
    if "layout" in record:
      del record["layout"]


  # Add two custom fields to the object.
  results["customer_identifier"] = loan_number
  results["project_identifier"] = "Post Closing Application"

  # Post endpoint call template
  # token = keys['secret']['VCC_API_TOKEN']
  # print(token.get_value())

  headers = {'Authorization': token}

  print(results)

  # resp = requests.post(
  #   'https://vccapi.azure-api.net/aihub/push/v1/response',
  #   headers=headers,
  #   json=results
  # )
  # if resp.ok:
  #   print('POST request successful')
  # else:
  #   print(f'POST request failed with status code: {resp.status_code} {resp.text}')
  return None