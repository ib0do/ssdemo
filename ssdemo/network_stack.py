from aws_cdk import (
    aws_ec2 as ec2,
    Stack,
    NestedStack,
    aws_rds as rds
)
from constructs import Construct
from ssdemo.application_stack import ApplicationStack
from ssdemo.database_stack import DatabaseStack


class NetworkStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, webservice_ami: str, app_container: str,
                 worker_container: str, availability_zones: list, **kwargs) -> None:

        super().__init__(scope, construct_id, **kwargs)

        demo_vpc = SimpleVpc(self, "vpc", availability_zones)
        demo_db = DatabaseStack(self, "database", demo_vpc.vpc)

        ApplicationStack(self, "app", demo_vpc.vpc, demo_db, webservice_ami, app_container, worker_container)


class SimpleVpc(Construct):
    def __init__(self, scope: Construct, id: str, availability_zones, *, cidr="10.0.0.0/16"):
        super().__init__(scope, id)

        subnets = [
            ec2.SubnetConfiguration(
                cidr_mask=20,
                name='public',
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            ec2.SubnetConfiguration(
                cidr_mask=20,
                name='private',
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            ec2.SubnetConfiguration(
                cidr_mask=20,
                name='isolated',
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            )
        ]

        self.vpc = ec2.Vpc(
            self, "simple",
            availability_zones=availability_zones,
            ip_addresses=ec2.IpAddresses.cidr(cidr),
            subnet_configuration=subnets
        )