from aws_cdk import (
    aws_ec2 as ec2,
    Stack,
    NestedStack,
    aws_rds as rds
)
from constructs import Construct


class DatabaseStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, vpc: Construct, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        custom_engine_version = rds.AuroraMysqlEngineVersion.of("5.7.mysql_aurora.2.10.2")

        security_group = ec2.SecurityGroup(self, "sg", vpc=vpc)

        for subnet in vpc.private_subnets:
            security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(subnet.ipv4_cidr_block),
                connection=ec2.Port.tcp(3306)
            )

        self.dbcluster = rds.DatabaseCluster(
            self, "database",
            engine=rds.DatabaseClusterEngine.aurora_mysql(
                version=custom_engine_version
            ),
            credentials=rds.Credentials.from_generated_secret("admin"),
            instance_props=rds.InstanceProps(
                instance_type=ec2.InstanceType.of(
                    ec2.InstanceClass.BURSTABLE2, ec2.InstanceSize.SMALL
                ),
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                ),
                security_groups=[
                    security_group
                ],
                vpc=vpc
            )
        )

