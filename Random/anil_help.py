from typing import Any
from instabase.provenance.registration import register_fn
import os
import logging
import time
import json
from datetime import datetime
import urllib.parse
import traceback
import pandas as pd

from .model import constants
from .services.app_run import APPRun
from .services.compare_results import compare_field_metrics_and_store_results
from .solution_accuracy_utils.aihub_solution_accuracy_calculator import (
    AIHubSolutionAccuracyCalculator,
)
from .solution_accuracy_utils.solution_accuracy_calculator import (
    SolutionAccuracyCalculator,
)
from .solution_accuracy_utils.aggregate_golden_and_extracted import DataAggregator
from .model.config import BaseConfig
from .services.email_service import *
from .services.aihub_utils import *


def __validate_blank(key, val):
    if not val:
        raise Exception(f"{key} is not present in the config")


def __attach_slash(val):
    if val and val[-1] != "/":
        val += "/"
    return val


def __read_file(clients, path):
    if not clients.ibfile.exists(path):
        return {}
    try:
        data = json.loads(clients.ibfile.read_file(path)[0])
        logging.info(f"data: {data}")
        return data
    except:
        return {}


def __get_date_time_stamp():
    now = datetime.now()
    timestamp = now.strftime("%Y/%m/%d")
    return timestamp


def __trigger_email(app_name, ALERT_EMAIL_ID, summary_dict, summary_path, base_url):
    # Creating email body and sending summary for all apps
    test_status = "Failed"
    summary = "an issue occurred while executing Regression Test Runner flow"
    if "TestStatus" in summary_dict:
        test_status = summary_dict["TestStatus"]
        summary_link = urllib.parse.quote(base_url + "/" + summary_path, safe="/:?=&")
        summary = f"test summary can be found <a href={summary_link}>here</a>"

    email_body = "Summary of the app run: \n\n"
    email_body += "<ul>"
    email_body += f"<li><b>{app_name} Test Status</b>: {test_status}, {summary}</li>"
    email_body += "</ul>"

    app_config = BaseConfig()
    email_config = EmailConfigDict(
        email_provider=app_config.EMAIL_PROVIDER,
        from_addr=app_config.NO_REPLY_EMAIL_ADDRESS,
        ses_config=SESConfigDict(
            use_aws_access_creds=app_config.USE_AWS_ACCESS_CREDS,
            region_name=app_config.SES_REGION_NAME,
            ses_access_key_id=app_config.SES_ACCESS_KEY_ID,
            ses_secret_access_key=app_config.SES_SECRET_ACCESS_KEY,
        ),
    )
    email_client, email_err = EmailClientBuilder.new_client(email_config)
    if email_err:
        raise Exception(email_err)
    date_val = __get_date_time_stamp()
    email_client.send_email(
        to_addr=ALERT_EMAIL_ID,
        subject=f"AIHub Apps Regression Test Runner ({date_val}): {app_name} - {test_status}",
        msg_body=email_body,
    )
    logging.info("Triggered summary email")


@register_fn(provenance=False)
def run_test(config, clients, job_id, *args: Any, **kwargs: Any) -> None:
    # Get the app name, its config file and token to trigger the apis
    app_id = config.get("APP_ID", "")
    app_name = config.get("APP_NAME", "")
    app_owner = config.get("APP_OWNER", "")
    config_file = config.get("APP_CONFIG_FILE", "")
    token = config.get("TOKEN", "")
    API_BASE_URL = config.get("ENV", "")

    # getting app name and app owner from aihub
    if app_id:
        app_name, app_owner = get_app_details(API_BASE_URL, app_id, token)

    # check for blank values
    __validate_blank("APP_NAME", app_name)
    __validate_blank("APP_CONFIG_FILE", config_file)
    __validate_blank("APP_OWNER", app_owner)
    __validate_blank("TOKEN", token)

    if not clients.ibfile.exists(config_file):
        raise Exception(f"{config['APP_CONFIG_FILE']} is not a valid path")

    config_file = json.loads(clients.ibfile.read_file(config_file)[0])

    is_advanced = config_file.get("IS_ADVANCED", False)
    if is_advanced:
        input_folder_path = config_file["INPUT_FOLDER_PATH"]
        out_path = config_file["OUT_FILES_PATH"]
        test_summary_path = config["TESTS_SUMMARY_PATH"]
        golden_file_path = config_file["GOLDEN_FILE_PATH"]
        golden_metrics_path = config_file["GOLDEN_METRICS_PATH"]

        accuracy_drop_allowed = config_file.get("ACCURACY_DROP_ALLOWED", 3)
        accuracy_drop_fields_count_allowed = config_file.get(
            "ACCURACY_DROP_FIELDS_ALLOWED_COUNT", 0
        )

        # Reading the % of drop allowed on the fields level
        fields_accuracy_drop_allowed = config_file.get(
            "FIELDS_ACCURACY_DROP_ALLOWED", {}
        )

        # Reading the list of critical fields
        critical_fields_list = config_file.get("CRITICAL_FIELDS", [])

        try:
            accuracy_drop_allowed = int(accuracy_drop_allowed)
            if accuracy_drop_allowed < 0:
                raise Exception("ACCURACY_DROP_ALLOWED should be a whole number")
        except:
            raise Exception("ACCURACY_DROP_ALLOWED should be a whole number")

        # validate if drop allowed per field is whole number
        for key, value in fields_accuracy_drop_allowed.items():
            try:
                value = int(value)
                if value < 0:
                    raise
            except:
                raise Exception(
                    f"FIELDS_ACCURACY_DROP_ALLOWED value for {key} should be a whole number"
                )

        try:
            accuracy_drop_fields_count_allowed = int(accuracy_drop_fields_count_allowed)
            if accuracy_drop_fields_count_allowed < 0:
                raise Exception(
                    "ACCURACY_DROP_FIELDS_ALLOWED_COUNT should be a whole number"
                )
        except:
            raise Exception(
                "ACCURACY_DROP_FIELDS_ALLOWED_COUNT should be a whole number"
            )

        ALERT_EMAIL_ID = config_file.get("ALERT_EMAIL_ID", "varun.nandan@instabase.com")

        __validate_blank("INPUT_FOLDER_PATH", input_folder_path)
        __validate_blank("OUT_FILES_PATH", out_path)
        __validate_blank("TESTS_SUMMARY_PATH", test_summary_path)
        __validate_blank("GOLDEN_FILE_PATH", golden_file_path)

        input_paths = []
        if clients.ibfile.is_dir(input_folder_path):
            output, err = clients.ibfile.list_dir(input_folder_path, "")
            nodes = output.nodes
            for node in nodes:
                if clients.ibfile.is_dir(node.full_path):
                    input_paths.append(node.full_path)

        if not input_paths:
            raise Exception("No test case folders found inside the input directory")

        job_ids = []
        summary_paths = []

        # Step 1: Run all cases to get job IDs
        for ib_input_path in input_paths:
            try:
                case = os.path.basename(ib_input_path)
                case_summary = {
                    "AppName": app_name,
                    "TestCase": case,
                    "RegressionTestRunnerJobID": job_id,
                }
                case_out_path = (
                    os.path.join(out_path, __get_date_time_stamp(), app_name, case)
                    + "/"
                )
                case_summary_path = os.path.join(case_out_path, "summary.json")

                if clients.ibfile.exists(case_summary_path):
                    logging.info(
                        f"App summary already found for case {case}. Skipping App trigger..."
                    )
                    try:
                        case_summary = json.loads(
                            clients.ibfile.read_file(case_summary_path)[0]
                        )
                    except:
                        pass

                app_job_id = case_summary.get("Application_Run_Job_ID")
                case_summary["Test_Runner_Job_ID"] = job_id

                logging.info(
                    f"app_name - {app_name} | token - {token} | ib_input_path - {ib_input_path} | case_out_path - {case_out_path} | clients - {clients} | case_summary - {case_summary} | API_BASE_URL - {API_BASE_URL}"
                )
                org_name = ib_input_path.split("/")[0]
                app_run = APPRun(
                    app_name,
                    token,
                    ib_input_path,
                    case_out_path,
                    clients,
                    case_summary,
                    API_BASE_URL,
                    app_owner,
                    org_name,
                )

                if not app_job_id:
                    try:
                        app_job_id = app_run.run_app()
                        logging.info(
                            f"Application triggered successfully for case {case}. Saving current checkpoint to avoid duplicate processing."
                        )
                        clients.ibfile.write_file(
                            case_summary_path, json.dumps(case_summary, indent=4)
                        )
                        logging.info(
                            f"Summary written successfully at: {case_summary_path}"
                        )
                    except Exception as ex:
                        logging.info(
                            f"Unable to trigger application for case {case}. Error: {traceback.format_exc()}"
                        )
                        raise Exception(
                            f"Unable to trigger application for case {case}. Error: {str(ex)}"
                        )

                job_ids.append(app_job_id)
                summary_paths.append(case_summary_path)

            except Exception as ex:
                logging.error(f"Error in test case {case} {ex}")
                logging.error(traceback.format_exc())
                case_summary["Note"] = str(ex)
                case_summary["SummaryPath"] = case_summary_path
                clients.ibfile.write_file(
                    case_summary_path, json.dumps(case_summary, indent=4)
                )

        # Step 2: Continue each job using the stored job IDs
        combined_csv_df = None
        combined_checkpoint_csv_df = None

        for app_job_id, case_summary_path in zip(job_ids, summary_paths):
            try:
                app_run = APPRun(
                    app_name,
                    token,
                    ib_input_path,
                    case_out_path,
                    clients,
                    case_summary,
                    API_BASE_URL,
                    app_owner,
                )
                _ = app_run.continue_run(app_job_id)
                output_folder, _ = app_run.check_job_status(app_job_id)

                case_summary = json.loads(
                    clients.ibfile.read_file(case_summary_path)[0]
                )
                case_summary["Output_Folder"] = output_folder
                clients.ibfile.write_file(
                    case_summary_path, json.dumps(case_summary, indent=4)
                )

                # Read existing CSV data
                csv_data_path = os.path.join(output_folder, "extraction_summary.csv")
                val_data_path = os.path.join(output_folder, "validation_summary.csv")
                logging.info(f"csv_data path: {csv_data_path}")

                if clients.ibfile.exists(csv_data_path):
                    csv_df = pd.read_csv(clients.ibfile.open(csv_data_path))
                    csv_df["Case ID"] = case_summary_path.split("/")[-2]
                    combined_csv_df = (
                        pd.concat([combined_csv_df, csv_df], ignore_index=True)
                        if combined_csv_df is not None
                        else csv_df
                    )

                if clients.ibfile.exists(val_data_path):
                    val_df = pd.read_csv(clients.ibfile.open(val_data_path))
                else:
                    logging.info(
                        "validation_summary.csv not found, creating dummy data."
                    )
                    if clients.ibfile.exists(csv_data_path):
                        csv_df = pd.read_csv(clients.ibfile.open(csv_data_path))
                        val_df = pd.DataFrame({col: [True] for col in csv_df.columns})
                    else:
                        logging.error("extraction_summary.json not found")

                val_df["Case ID"] = case_summary_path.split("/")[-2]
                combined_checkpoint_csv_df = (
                    pd.concat([combined_checkpoint_csv_df, val_df], ignore_index=True)
                    if combined_checkpoint_csv_df is not None
                    else val_df
                )

            except Exception as ex:
                logging.error(f"Error in continuing test case {case} {ex}")
                logging.error(traceback.format_exc())
                case_summary["Note"] = str(ex)
                case_summary["SummaryPath"] = case_summary_path
                clients.ibfile.write_file(
                    case_summary_path, json.dumps(case_summary, indent=4)
                )

        # Step 3: Write merged CSV data
        out_path = os.path.join(out_path, __get_date_time_stamp(), app_name)
        out_path = config.get("app_out_path", out_path)
        merged_csv_data_path = os.path.join(out_path, "merged_csv_data.csv")
        merged_val_data_path = os.path.join(out_path, "merged_val_data.csv")
        if combined_csv_df is not None:
            clients.ibfile.write_file(
                merged_csv_data_path, combined_csv_df.to_csv(index=False)
            )

        if combined_checkpoint_csv_df is not None:
            clients.ibfile.write_file(
                merged_val_data_path, combined_checkpoint_csv_df.to_csv(index=False)
            )

        summary_dict = {
            "App_Name": app_name,
            "RegressionRunJobID": job_id,
            "App_UUID": app_id,
        }

        # Step 4: Calculate the accuracy metrics
        metrics_path = f"{out_path}/{app_name}_metrics.json"
        try:
            aggregator = DataAggregator(
                merged_csv_data_path,
                merged_val_data_path,
                golden_file_path,
                clients,
                out_path,
                summary_dict,
                API_BASE_URL,
            )
            raw_data_aggregated_output = aggregator.get_raw_data_aggregated_output()
            comparison_logic = aggregator.generate_comparison_logic(
                merged_csv_data_path
            )

            accuracy_metrics = SolutionAccuracyCalculator.compute_accuracy_metrics(
                comparison_logic,
                raw_data_aggregated_output,
                comparison_logic.get("exempt_misclassified_records", {}),
            )
            logging.info(f"accuracy_metrics: {accuracy_metrics}")

            with clients.ibfile.open(metrics_path, "w") as f:
                f.write(
                    json.dumps(
                        accuracy_metrics,
                        default=lambda o: getattr(o, "__dict__", str(o)),
                    )
                )
                summary_dict["Current_Run_Metrics_URL"] = urllib.parse.quote(
                    API_BASE_URL + "/" + metrics_path, safe="/:?=&"
                )

        except Exception as ex:
            logging.error(
                f"Error in calculating the accuracy metrics: {traceback.format_exc()}"
            )
            summary_dict["Note"] = str(ex)

        # Step 5: Compare with old metrics
        if golden_metrics_path:
            compare_field_metrics_and_store_results(
                metrics_path,
                golden_metrics_path,
                app_name,
                out_path,
                clients,
                accuracy_drop_allowed,
                fields_accuracy_drop_allowed,
                accuracy_drop_fields_count_allowed,
                critical_fields_list,
                summary_dict,
                API_BASE_URL,
            )

        # Trigger summary email
        out_path = os.path.join(out_path, "summary.json")
        clients.ibfile.write_file(out_path, json.dumps(summary_dict, indent=4))
        summary_dict["Summary_Path"] = out_path
        data = __read_file(clients, test_summary_path)
        data[app_name] = summary_dict
        clients.ibfile.write_file(test_summary_path, json.dumps(data, indent=4))

    else:
        # Get all config values
        out_path = config_file.get("OUT_FILES_PATH", "").strip()
        test_summary_path = config["TESTS_SUMMARY_PATH"]
        golden_id = config_file.get("GOLDEN_ID")
        accuracy_run_id = config_file.get("ACCURACY_RUN_ID")
        alert_email_id = config_file.get("ALERT_EMAIL_ID", "varun.nandan@instabase.com")
        accuracy_drop_allowed = config_file.get("ACCURACY_DROP_ALLOWED", 3)
        fields_accuracy_drop_allowed = config_file.get(
            "FIELDS_ACCURACY_DROP_ALLOWED", {}
        )
        accuracy_drop_fields_count_allowed = config_file.get(
            "ACCURACY_DROP_FIELDS_ALLOWED_COUNT", 0
        )
        critical_fields_list = config_file.get("CRITICAL_FIELDS", [])

        # Validate required config values
        __validate_blank("OUT_FILES_PATH", out_path)
        __validate_blank("TESTS_SUMMARY_PATH", test_summary_path)
        __validate_blank("GOLDEN_ID", golden_id)
        __validate_blank("ACCURACY_RUN_ID", accuracy_run_id)

        # Validate numeric config values
        try:
            accuracy_drop_allowed = int(accuracy_drop_allowed)
            if accuracy_drop_allowed < 0:
                raise Exception("ACCURACY_DROP_ALLOWED should be a whole number")
        except:
            raise Exception("ACCURACY_DROP_ALLOWED should be a whole number")

        for key, value in fields_accuracy_drop_allowed.items():
            try:
                value = int(value)
                if value < 0:
                    raise
            except:
                raise Exception(
                    f"FIELDS_ACCURACY_DROP_ALLOWED value for {key} should be a whole number"
                )

        try:
            accuracy_drop_fields_count_allowed = int(accuracy_drop_fields_count_allowed)
            if accuracy_drop_fields_count_allowed < 0:
                raise Exception(
                    "ACCURACY_DROP_FIELDS_ALLOWED_COUNT should be a whole number"
                )
        except:
            raise Exception(
                "ACCURACY_DROP_FIELDS_ALLOWED_COUNT should be a whole number"
            )

        # Getting the output path appended with date and app name e.g: {out_path}/2023/11/10/Passport/
        out_path = (
            __attach_slash(out_path) + __get_date_time_stamp() + "/" + app_name + "/"
        )
        out_path = config.get("app_out_path", out_path)
        out_path = __attach_slash(out_path)

        summary_path = config.get("app_summary_path", out_path + "summary.json")
        summary_dict = {"App_Name": app_name}

        try:
            golden_set = fetch_ground_truth_set(API_BASE_URL, golden_id, token)
            ib_input_path = os.path.join(
                "/".join(golden_set["file_paths"][0].split("/")[:-3]), "input"
            )
            
            # get the files folder and save the files in it
            summary_path = os.path.dirname(summary_path)
            path_to_save = os.path.join(summary_path, "files")
            list_dir_info, err = clients.ibfile.list_dir(ib_input_path, 0)
            for node in list_dir_info.nodes:
                path_to_read = os.path.join(ib_input_path, node.name)
                clients.ibfile.write_file(os.path.join(path_to_save, node.name), clients.ibfile.read_file(path_to_read)[0])
            


            deployed_solution_id = golden_set["ground_truth_set"][
                "deployed_solution_id"
            ]
            org_name = ib_input_path.split("/")[0]

            # get all the app ids for the project
            app_name, app_owner = get_app_details(
                API_BASE_URL, deployed_solution_id, token
            )
            app_ids = get_all_app_ids(
                API_BASE_URL, token, app_owner, app_name, org_name
            )
            print(f"app_ids: {app_ids}")

            # getting details of the accuracy run
            accuracy_details = get_accuracy_details(
                API_BASE_URL, app_ids, accuracy_run_id, token, org_name
            )
            accuracy_run_dir = json.loads(accuracy_details["metadata"])[
                "flow_metadata"
            ]["flow_input"]["output_args"]["output_root_dirpath"].rstrip("/output")
            golden_metrics_path = f"{accuracy_run_dir}/accuracy/metrics.json"

            # get the data.xlsx and metrics.json from the accuracy run dir
            print(accuracy_run_dir)
            data_path = os.path.join(accuracy_run_dir, "data.xlsx")
            metrics_path = os.path.join(accuracy_run_dir, "metrics.json")
            metadata_path = os.path.join(accuracy_run_dir, "metadata.json")
            page_splits_path = os.path.join(accuracy_run_dir, "page_splits.xlsx")
            schema_path = os.path.join(accuracy_run_dir, "schema.json")
            clients.ibfile.write_file(os.path.join(summary_path, "data.xlsx"), clients.ibfile.read_file(data_path)[0])
            clients.ibfile.write_file(os.path.join(summary_path, "metrics.json"), clients.ibfile.read_file(metrics_path)[0])
            clients.ibfile.write_file(os.path.join(summary_path, "metadata.json"), clients.ibfile.read_file(metadata_path)[0])
            clients.ibfile.write_file(os.path.join(summary_path, "page_splits.xlsx"), clients.ibfile.read_file(page_splits_path)[0])
            clients.ibfile.write_file(os.path.join(summary_path, "schema.json"), clients.ibfile.read_file(schema_path)[0])

            return

        except Exception as ex:
            logging.error(f"Error: {ex}")
            summary_dict["Note"] = str(ex)
            summary_dict["Summary_Path"] = summary_path
            clients.ibfile.write_file(summary_path, json.dumps(summary_dict, indent=4))
            data = __read_file(clients, test_summary_path)
            data[app_name] = summary_dict
            clients.ibfile.write_file(test_summary_path, json.dumps(data, indent=4))
            return

        __validate_blank("INPUT_FILES_PATH", ib_input_path)
        base_input_path = os.path.dirname(ib_input_path)
        if not out_path:
            out_path = os.path.join(base_input_path, "output")

        try:
            if clients.ibfile.exists(summary_path):
                logging.info(f"App summary already found. Skipping App trigger...")
                try:
                    summary_dict = json.loads(clients.ibfile.read_file(summary_path)[0])
                except:
                    pass

            app_job_id = summary_dict.get("Application_Run_Job_ID")

            summary_dict["Test_Runner_Job_ID"] = job_id
            ib_input_path = __attach_slash(ib_input_path)

            # Running the app through api and getting the ibflow results
            logging.info(
                f"app_name - {app_name} | token - {token} | ib_input_path - {ib_input_path} | out_path - {out_path} | clients - {clients} | summary_dict - {summary_dict} | API_BASE_URL - {API_BASE_URL}"
            )
            app_run = APPRun(
                app_name,
                token,
                ib_input_path,
                out_path,
                clients,
                summary_dict,
                API_BASE_URL,
                app_owner,
            )

            if not app_job_id:
                try:
                    app_job_id = app_run.run_app()
                    logging.info(
                        f"Application triggered successfully. Saving current checkpoint to avoid duplicate processing."
                    )
                    clients.ibfile.write_file(
                        summary_path, json.dumps(summary_dict, indent=4)
                    )
                    logging.info(f"Summary written successfully at: {summary_path}")
                except Exception as ex:
                    logging.info(
                        f"Unable to trigger application. Error: {traceback.format_exc()}"
                    )
                    raise Exception(f"Unable to trigger application. Error: {str(ex)}")

            ibresults_dict = app_run.download_results(app_job_id)

            # Calculating the solution accuracy by comparing the ibflow result with the golden values
            solCalculator = AIHubSolutionAccuracyCalculator(
                accuracy_source_dir=accuracy_run_dir,
                ibresults_dict=ibresults_dict,
                access_token=token,
                out_path=out_path,
                app_name=app_name,
                clients=clients,
                summary_dict=summary_dict,
                api_base_url=API_BASE_URL,
            )
            metrics_path, err = solCalculator.compute_and_record_solution_accuracy()

            # Comparing the current run metric with the previous run accuracy
            compare_field_metrics_and_store_results(
                metrics_path,
                golden_metrics_path,
                app_name,
                out_path,
                clients,
                accuracy_drop_allowed,
                fields_accuracy_drop_allowed,
                accuracy_drop_fields_count_allowed,
                critical_fields_list,
                summary_dict,
                API_BASE_URL,
                note=err,
            )

            # save the test summary
            summary_dict["Benchmarked_Metrics_URL"] = urllib.parse.quote(
                os.path.join(API_BASE_URL, golden_metrics_path), safe="/:?=&"
            )
            summary_dict["Summary_Path"] = summary_path
            clients.ibfile.write_file(summary_path, json.dumps(summary_dict, indent=4))
        except Exception as ex:
            logging.error("Error in - run_test")
            logging.error(traceback.format_exc())
            summary_dict["Note"] = str(ex)
            summary_dict["Summary_Path"] = summary_path
            clients.ibfile.write_file(summary_path, json.dumps(summary_dict, indent=4))

        data = __read_file(clients, test_summary_path)
        data[app_name] = summary_dict
        clients.ibfile.write_file(test_summary_path, json.dumps(data, indent=4))
