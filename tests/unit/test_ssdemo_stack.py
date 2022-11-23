import aws_cdk as core
import aws_cdk.assertions as assertions

from ssdemo.ssdemo_stack import SsdemoStack

# example tests. To run these tests, uncomment this file along with the example
# resource in ssdemo/ssdemo_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = SsdemoStack(app, "ssdemo")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
