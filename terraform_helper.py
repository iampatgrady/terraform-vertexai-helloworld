#!/usr/bin/env python3
# target120/terraform_helper.py (Corrected)

import argparse
import json
import os
import sys
import tempfile
import traceback
import logging # For better script logging

# Ensure the pipeline package can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pipeline.hello_pipeline import minimal_hello_pipeline
from kfp import compiler
from google.cloud import aiplatform
from google.cloud.aiplatform.compat.types import pipeline_state as ps_module # Renamed to avoid confusion

# Configure basic logging for this helper script
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='Helper: %(levelname)s: %(message)s')

def run_vertex_ai_pipeline(
    project_id: str,
    region: str,
    pipeline_root_gcs: str,
    job_id_suffix: str,
    message_from_tf: str,
    output_json_file_path: str
):
    """
    Compiles, submits, and monitors a KFP pipeline on Vertex AI,
    then writes its output to a JSON file for Terraform.
    """
    compiled_pipeline_path = None
    result_data = {"error": "Python script encountered an unexpected error before pipeline execution."}

    try:
        logging.info(f"Initializing Vertex AI SDK for project '{project_id}' in region '{region}'.")
        aiplatform.init(project=project_id, location=region)

        with tempfile.NamedTemporaryFile(mode='w', suffix=".yaml", delete=False) as tmpfile:
            compiled_pipeline_path = tmpfile.name
        logging.info(f"Compiling KFP pipeline to '{compiled_pipeline_path}'.")
        compiler.Compiler().compile(
            pipeline_func=minimal_hello_pipeline,
            package_path=compiled_pipeline_path
        )

        pipeline_job_id = f"kfp-{job_id_suffix.lower().replace('_', '-')}"[:120]

        logging.info(f"Submitting Vertex AI Pipeline Job '{pipeline_job_id}'.")
        job = aiplatform.PipelineJob(
            display_name=f"KFP Run - {job_id_suffix.lower()}"[:120],
            template_path=compiled_pipeline_path,
            pipeline_root=pipeline_root_gcs,
            job_id=pipeline_job_id,
            parameter_values={"message_to_produce": message_from_tf},
            enable_caching=False
        )

        logging.info(f"Waiting for pipeline job '{pipeline_job_id}' to complete (synchronous call)...")
        job.run(sync=True, create_request_timeout=120.0)

        if job.state == ps_module.PipelineState.PIPELINE_STATE_SUCCEEDED:
            logging.info(f"Pipeline job '{pipeline_job_id}' SUCCEEDED. Extracting output.")
            output_message_str = None
            for task in job.task_details:
                if task.task_name == "produce-message-component":
                    if task.execution and task.execution.metadata:
                        output_key_from_proto = "output:Output"
                        if output_key_from_proto in task.execution.metadata:
                            output_message_str = str(task.execution.metadata[output_key_from_proto])
                            logging.info(f"Found output from 'produce-message-component': '{output_message_str}'")
                            break
            
            if output_message_str is not None:
                result_data = {"message": output_message_str}
            else:
                err_msg = f"Pipeline '{pipeline_job_id}' SUCCEEDED, but 'produce-message-component' task output was not found in execution.metadata."
                logging.error(err_msg)
                result_data = {"error": err_msg}
        else:
            # job.state is an enum instance, so job.state.name gives its string name
            job_state_name = job.state.name if job.state else 'UNKNOWN_PIPELINE_STATE'
            error_summary = f"Pipeline job '{pipeline_job_id}' did not succeed. Final State: {job_state_name}."
            try:
                if hasattr(job, '_gca_resource') and job._gca_resource and job._gca_resource.error:
                    g_error = job._gca_resource.error
                    if g_error and (g_error.message or g_error.code != 0):
                         error_summary += f" GCP Error Details: {g_error.message} (Code: {g_error.code})"
            except Exception as e_detail:
                logging.warning(f"Could not retrieve detailed GCP error for job '{pipeline_job_id}': {e_detail}")
            logging.error(error_summary)
            result_data = {"error": error_summary}

    except Exception as e:
        full_trace = traceback.format_exc()
        critical_error_message = f"A critical error occurred in the Python script: {str(e)}\nFull Traceback:\n{full_trace}"
        logging.critical(critical_error_message)
        result_data = {"error": f"Python script internal exception: {str(e)} (check Terraform runner logs for full trace)"}
    finally:
        if compiled_pipeline_path and os.path.exists(compiled_pipeline_path):
            try:
                os.remove(compiled_pipeline_path)
                logging.info(f"Cleaned up temporary compiled pipeline file: '{compiled_pipeline_path}'.")
            except OSError as e_remove:
                logging.warning(f"Could not remove temporary file '{compiled_pipeline_path}': {e_remove}")
        
        logging.info(f"Writing result to output file: '{output_json_file_path}'. Content: {result_data}")
        try:
            with open(output_json_file_path, 'w') as f:
                json.dump(result_data, f, indent=2)
        except IOError as e_io:
            logging.critical(f"FATAL: Could not write to output file '{output_json_file_path}': {str(e_io)}")
            print(json.dumps({"error": f"FATAL_WRITE_ERROR: {str(e_io)}"}), file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Terraform helper script to compile and run a minimal Vertex AI KFP pipeline."
    )
    parser.add_argument("--project_id", required=True, help="Google Cloud Project ID.")
    parser.add_argument("--region", required=True, help="Google Cloud Region for Vertex AI.")
    parser.add_argument("--pipeline_root_gcs", required=True, help="GCS path for Vertex AI pipeline root.")
    parser.add_argument("--job_id_suffix", required=True, help="Suffix for the Vertex AI job ID.")
    parser.add_argument("--message_from_tf", required=True, help="Message string to pass to the KFP.")
    parser.add_argument("--output_file", required=True, help="Path to write the JSON output.")
    
    args = parser.parse_args()

    logging.info("Terraform helper script started.")
    run_vertex_ai_pipeline(
        project_id=args.project_id,
        region=args.region,
        pipeline_root_gcs=args.pipeline_root_gcs,
        job_id_suffix=args.job_id_suffix,
        message_from_tf=args.message_from_tf,
        output_json_file_path=args.output_file
    )
    logging.info("Terraform helper script finished.")