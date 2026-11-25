"""Part 2 · The foundation: everything the AI will stand on, as code.

WhatsApp -> API Gateway (HTTP API) -> Ingest Lambda -> SQS FIFO (+ DLQ) -> Dispatcher Lambda -> DynamoDB
Secrets in Secrets Manager. Least-privilege IAM (CDK grants). No AI yet: Part 3 plugs the agent into the dispatcher.
"""
from aws_cdk import Stack
from constructs import Construct


class FoundationStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, stage: str, **kw) -> None:
        super().__init__(scope, cid, **kw)
        # Part 2 builds this stack step by step: table, queue, webhook, dispatcher, least privilege.

