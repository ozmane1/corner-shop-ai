"""Part 2 · The foundation: everything the AI will stand on, as code.

WhatsApp -> API Gateway (HTTP API) -> Ingest Lambda -> SQS FIFO (+ DLQ) -> Dispatcher Lambda -> DynamoDB
Secrets in Secrets Manager. Least-privilege IAM (CDK grants). No AI yet: Part 3 plugs the agent into the dispatcher.
"""
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as ddb
from constructs import Construct


class FoundationStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, stage: str, **kw) -> None:
        super().__init__(scope, cid, **kw)
        prod = stage == "prod"

        table = ddb.TableV2(
            self, "Shop",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing=ddb.Billing.on_demand(),
            point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(point_in_time_recovery_enabled=True),
            time_to_live_attribute="ttl",
            deletion_protection=prod,
            removal_policy=RemovalPolicy.RETAIN if prod else RemovalPolicy.DESTROY,
        )

        CfnOutput(self, "TableName", value=table.table_name)
