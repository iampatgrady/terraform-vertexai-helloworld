# ./pipeline/hello_pipeline.py
from kfp import dsl
from .components import produce_message_component

@dsl.pipeline(
    name="minimal-hello-world-pipeline",
    description="A minimal Vertex AI pipeline that produces a Hello World message, orchestrated by Terraform."
)
def minimal_hello_pipeline(
    # Terraform will pass a value for this.
    message_to_produce: str 
):
    """
    Defines the Hello World KFP pipeline structure.
    It consists of a single component that processes an input message.
    """
    # Call the component, passing the pipeline parameter to its input.
    producer_task = produce_message_component(
        input_text=message_to_produce
    )
    # In more complex pipelines, you would chain multiple components here.