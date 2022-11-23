from aws_cdk import (
    Stack,
    NestedStack,
)
from constructs import Construct
from ssdemo.network_stack import NetworkStack


class SsdemoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, webservice_ami: str, app_container: str,
                 worker_container: str, availability_zones: list, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        NetworkStack(self, "networkstack", webservice_ami, app_container, worker_container, availability_zones)
