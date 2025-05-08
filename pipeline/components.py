# ./pipeline/components.py
from kfp.dsl import component

@component(
    base_image="python:3.12", # Specify a base image for reproducibility
)
def produce_message_component(
    input_text: str,
) -> str:
    """
    A simple KFP component that takes an input string, appends a message,
    logs it, and returns the new string.
    """
    # For real MLOps, you might load data, preprocess, train, or predict here.
    # For this "Hello World", we just manipulate a string.
    processed_message = f"{input_text} - from KFP component"
    
    return processed_message