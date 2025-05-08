# tfhw3_target120/pipeline/components.py
from kfp.dsl import component

@component(
    base_image="python:3.9", # Specify a base image for reproducibility
    packages_to_install=["google-cloud-logging"], # Example of adding a package
)
def produce_message_component(
    input_text: str,
) -> str:
    """
    A simple KFP component that takes an input string, appends a message,
    logs it, and returns the new string.
    This demonstrates a basic, self-contained pipeline step.
    """
    # For real MLOps, you might load data, preprocess, train, or predict here.
    # For this "Hello World", we just manipulate a string.
    import logging # Import a standard library
    logging.basicConfig(level=logging.INFO)

    processed_message = f"{input_text} - from KFP component (tfhw3)"
    logging.info(f"Component: Received '{input_text}', producing '{processed_message}'")
    return processed_message