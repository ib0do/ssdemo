from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_iam as iam,
    Stack,
    NestedStack,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as elbv2_targets
)
from constructs import Construct


class ApplicationStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, vpc: Construct, db: Construct,
                 webservice_ami: str, app_container: str, worker_container: str, **kwargs) -> None:

        super().__init__(scope, construct_id, **kwargs)

        app_cluster = SimpleFargateCluster(self, "cluster", vpc)
        app_service = AppService(self, "app", vpc, db, app_cluster.cluster, app_container)
        worker_service = WorkerService(self, "worker", vpc, db, app_cluster.cluster, worker_container)

        web_service = WebService(self, "web", vpc, app_service.load_balancer, webservice_ami)


class SimpleFargateCluster(Construct):
    def __init__(self, scope: Construct, id: str, vpc: Construct):
        super().__init__(scope, id)

        self.cluster = ecs.Cluster(self, "fargate", vpc=vpc)


class WorkerService(Construct):
    def __init__(self, scope: Construct, id: str, vpc: Construct, db: Construct, cluster: Construct, worker_container: str):
        super().__init__(scope, id)

        worker_def = WorkerTaskDefinition(self, "taskdef", db, worker_container)
        worker_security_group = ec2.SecurityGroup(self, "sg", vpc=vpc)

        self.service = ecs.FargateService(
            self, "service",
            cluster=cluster,
            security_groups=[worker_security_group],
            task_definition=worker_def.task_definition,
            vpc_subnets=ec2.SubnetSelection(
                subnets=vpc.private_subnets
            ),
        )

        auto_scale = self.service.auto_scale_task_count(min_capacity=1, max_capacity=2)

        auto_scale.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=75
        )


class WorkerTaskDefinition(Construct):
    def __init__(self, scope: Construct, id: str, db: Construct, worker_container: str):
        super().__init__(scope, id)

        self.task_definition = ecs.FargateTaskDefinition(self, "worker", memory_limit_mib=3072, cpu=1024)
        self.container = self.task_definition.add_container(
            "worker",
            image=ecs.ContainerImage.from_registry(worker_container),
            environment={
                "ENDPOINT": db.dbcluster.cluster_endpoint.hostname,
                "ENDPOINT_REPLICA": db.dbcluster.cluster_read_endpoint.hostname,
            },
            port_mappings=[
                ecs.PortMapping(container_port=80),
                ecs.PortMapping(container_port=3306)
            ],
            secrets={
                "DB_LOGIN": ecs.Secret.from_secrets_manager(
                    db.dbcluster.secret),
            }
        )

        self.task_definition.execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
        )


class WebService(Construct):
    def __init__(self, scope: Construct, id: str, vpc: Construct, app_load_balancer: Construct, webservice_ami: str):
        super().__init__(scope, id)

        web_load_balancer = WebServiceLoadBalancer(self, "lb", vpc)
        web_security_group = ec2.SecurityGroup(self, "sg", vpc=vpc)

        web_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4("0.0.0.0/0"),
            connection=ec2.Port.tcp(22)
        )

        web_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4("0.0.0.0/0"),
            connection=ec2.Port.tcp(80)
        )

        linux = ec2.MachineImage.generic_linux({
            "eu-central-1": webservice_ami
        })

        self.instances = []

        for subnet in vpc.private_subnets:
            self.instances.append(
                ec2.Instance(
                    self, "i-" + subnet.availability_zone,
                    vpc=vpc,
                    instance_type=ec2.InstanceType('t2.micro'),
                    machine_image=linux,
                    security_group=web_security_group,
                    user_data=ec2.UserData.custom(app_load_balancer.load_balancer_dns_name),
                    vpc_subnets=ec2.SubnetSelection(
                        subnets=[subnet]
                    ),
                )
            )

        for instance in self.instances:
            instance_target = elbv2_targets.InstanceTarget(instance)
            web_load_balancer.target_group.add_target(instance_target)
            instance.role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            )


class WebServiceLoadBalancer(Construct):
    def __init__(self, scope: Construct, id: str, vpc: Construct):
        super().__init__(scope, id)

        self.security_group = ec2.SecurityGroup(self, "sg", vpc=vpc)

        self.security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4("0.0.0.0/0"),
            connection=ec2.Port.tcp(80)
        )

        self.load_balancer = elbv2.ApplicationLoadBalancer(
            self, "lb", vpc=vpc, security_group=self.security_group, internet_facing=True
        )

        self.listener = self.load_balancer.add_listener(
            "listener", port=80, open=True
        )

        self.target_group = self.listener.add_targets(
            "ec2",
            port=80,
            health_check=elbv2.HealthCheck(
                path="/test.php",
                port="80",
                protocol=elbv2.Protocol.HTTP
            ),
        )


class AppService(Construct):
    def __init__(self, scope: Construct, id: str, vpc: Construct, db: Construct, cluster: Construct, app_container: str):
        super().__init__(scope, id)

        app_def = AppTaskDefinition(self, "taskdef", db, app_container)
        app_security_group = ec2.SecurityGroup(self, "sg", vpc=vpc)

        for subnet in vpc.private_subnets:
            app_security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(subnet.ipv4_cidr_block),
                connection=ec2.Port.tcp(80)
            )
            app_security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(subnet.ipv4_cidr_block),
                connection=ec2.Port.tcp(443)
            )
            app_security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(subnet.ipv4_cidr_block),
                connection=ec2.Port.tcp(8080)
            )

        self.service = ecs.FargateService(
            self, "service",
            cluster=cluster,
            desired_count=len(vpc.private_subnets),
            security_groups=[app_security_group],
            task_definition=app_def.task_definition,
            vpc_subnets=ec2.SubnetSelection(
                subnets=vpc.private_subnets
            ),
        )

        self.load_balancer = elbv2.ApplicationLoadBalancer(self, "lb", vpc=vpc, security_group=app_security_group)

        listener = self.load_balancer.add_listener("listener", port=8080, protocol=elbv2.ApplicationProtocol.HTTP)

        self.service.register_load_balancer_targets(
            ecs.EcsTarget(
                container_name="webapp",
                container_port=8080,
                new_target_group_id="web-targetgrp",
                listener=ecs.ListenerConfig.application_listener(
                    listener,
                    health_check=elbv2.HealthCheck(
                        path="/demo/all",
                        port="8080",
                        protocol=elbv2.Protocol.HTTP
                    ),
                    protocol=elbv2.ApplicationProtocol.HTTP
                )
            )
        )


class AppTaskDefinition(Construct):
    def __init__(self, scope: Construct, id: str, db: Construct, app_container: str):
        super().__init__(scope, id)

        self.task_definition = ecs.FargateTaskDefinition(self, "webapp", memory_limit_mib=3072, cpu=1024)
        self.container = self.task_definition.add_container(
            "webapp",
            image=ecs.ContainerImage.from_registry(app_container),
            environment={
                "ENDPOINT": db.dbcluster.cluster_endpoint.hostname,
                "ENDPOINT_REPLICA": db.dbcluster.cluster_read_endpoint.hostname,
            },
            port_mappings=[
                ecs.PortMapping(container_port=80),
                ecs.PortMapping(container_port=8080)
            ],
            secrets={
                "DB_LOGIN": ecs.Secret.from_secrets_manager(
                    db.dbcluster.secret),
            }
        )

        self.task_definition.execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
        )
