import logging
import os
import json
import requests

from instabase.ocr.client.libs.ibocr import ParsedIBOCRBuilder
from google.protobuf.json_format import MessageToJson

def get_summary(**kwargs):
    summary_dict = {}

    fn_context = kwargs.get('_FN_CONTEXT_KEY')
    clients, _ = fn_context.get_by_col_name('CLIENTS')
    root_out_folder, _ = fn_context.get_by_col_name('ROOT_OUTPUT_FOLDER')

    res_path = os.path.join(root_out_folder, 'batch.ibflowresults')
    output, err = clients.ibfile.read_file(res_path)
    if err:
        return None, err

    results = json.loads(output)
    print(f"VINAY DEBUG: {results}")
    if results['can_resume']:
        # can_resume = True implies flow is stopped at checkpoint.
        # If true, skip writing summary.
        return None, None
    
    summary_dict['records'] = []
    for result_id in results['results']:
        iborc_paths = []
        main_result = results['results'][result_id]
        for record in main_result['records']:
            if record['status'] == 'OK':
                ibocr_path = record['ibocr_full_path']
                if ibocr_path not in iborc_paths:
                    iborc_paths.append(ibocr_path)
                else:
                    continue
                
                ibocr, err = clients.ibfile.read_file(ibocr_path)
                if err:
                    return None, f'Failed to fetch ibocr path={ibocr_path} err={err}'

                builder, err = ParsedIBOCRBuilder.load_from_str(ibocr_path, ibocr)
                if err:
                    return None, f'Failed to parse ibocr path={ibocr_path} err={err}'

                # Iterate over the IBOCR records.
                for ibocr_record in builder.get_ibocr_records():
                    raw_input_filepath = ibocr_record.get_document_path()

                    result = {}
                    # output file path
                    result['output_file_path'] = raw_input_filepath
                    # results
                    result['results'] = []
                    refined_phrases, _ = ibocr_record.get_refined_phrases()
                    for phrase in refined_phrases:
                        field_result = {}
                        key = phrase.get_column_name()
                        value = phrase.get_column_value()
                        field_result['key'] = key
                        field_result['value'] = value
                        if key == '__model_result':
                            continue
                        field_result['field_type'] = phrase.get_output_type()
                        field_result['model_confidence'] = phrase.get_average_model_confidence()
                        result['results'].append(field_result)
                    # record index
                    record_id = ibocr_record.get_record_id()  
                    result['record_index'] = int(''.join(filter(str.isdigit, record_id)))

                    # classification label and file name and document path
                    if ibocr_record.has_class_label():
                        class_label = ibocr_record.get_class_label()
                        result['classification_label'] = class_label
                        file_path = os.path.join(root_out_folder, "s3_apply_classifier/labeled_outputs", class_label)
                        if ibocr_record.has_classify_page_range():
                            result['page_range'] = ibocr_record.get_classify_page_range()
                        else:
                            result['page_range'] = {
                                "start_page": ibocr_record.get_page_numbers()[0] + 1,
                                "end_page": ibocr_record.get_page_numbers()[-1] + 1
                            }

                        if clients.ibfile.is_dir(file_path):
                            list_dir_info, err = clients.ibfile.list_dir(file_path, 0)
                            if err:
                                logging.info('ERROR list_dir at path {}: {}'.format(file_path, err))
                            for node in list_dir_info.nodes:
                                parts = node.name.split('-')
                                if len(parts) >= 3:
                                    try:
                                        start_page = int(parts[-2])
                                        end_page = int(parts[-1].split('.')[0])
                                        if start_page == result['page_range']['start_page'] and end_page == result['page_range']['end_page']:
                                            result['file_name'] = node.name
                                            result['document_path'] = os.path.join(file_path, node.name)
                                            break
                                    except ValueError:
                                        continue

                    # checkpoint results
                    if ibocr_record.has_checkpoint_results():
                        checkpoint_results = ibocr_record.get_checkpoint_results()
                        result['checkpoint_results'] = json.loads(MessageToJson(checkpoint_results))

                    # is manually reviewed, class score, is human corrected, absolute ibocr path
                    result['is_manually_reviewed'] = ibocr_record.is_manually_reviewed()
                    if ibocr_record.has_class_score():
                        result['class_score'] = ibocr_record.get_class_score()
                    result['is_human_corrected'] = ibocr_record.is_human_corrected()
                    result['absolute_ibocr_path'] = ibocr_record.get_absolute_ibocr_path()

                    summary_dict['records'].append(result)
                    
    summary_dict['binary_path'] = results['binary_path']
    summary_dict['job_id'] = results['job_id']
    summary_dict['can_resume'] = False

    return summary_dict, None

def send_results(config, **kwargs):
    fn_context = kwargs.get('_FN_CONTEXT_KEY')
    clients, _ = fn_context.get_by_col_name('CLIENTS')
    root_out_folder, _ = fn_context.get_by_col_name('ROOT_OUTPUT_FOLDER')

    results, err = get_summary(**kwargs)
    if err:
        logging.error(err)
        return

    if results:
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

        results["customer_identifier"] = loan_number
        results["project_identifier"] = "Post Closing Application"

        print(config)

        _, err = clients.ibfile.write_file(
            os.path.join(root_out_folder, 'summary.json'),
            json.dumps(results, indent=4)
        )
        if err:
            return None, f'Failed to write summary file err={err}'

        token = config['keys']['secret']['VCC_API_TOKEN']
        
        headers = {'Authorization': token}
        resp = requests.post(
          'https://vccapi.azure-api.net/aihub/push/v1/response',
          headers=headers,
          json=results
        )
        if resp.ok:
          logging.info('POST request successful')
        else:
          logging.error(f'POST request failed with status code: {resp.status_code} {resp.text}')
        return

def register(name_to_fn):
    name_to_fn.update({
        'send_results': {
            'fn': send_results
        }
    })