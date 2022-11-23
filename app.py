#!/usr/bin/env python3
import os
import aws_cdk as cdk

from ssdemo.ssdemo_stack import SsdemoStack

app = cdk.App()

SsdemoStack(
    app, "DemoStack",
    webservice_ami="<front-end service AMI id>",
    app_container="<application service container URI>",
    worker_container="<worker service container URI>",
    availability_zones=["eu-central-1a", "eu-central-1b"]
)

app.synth()
