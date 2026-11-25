"""Part 2 · The foundation: everything the AI will stand on, as code.

WhatsApp -> API Gateway (HTTP API) -> Ingest Lambda -> SQS FIFO (+ DLQ) -> Dispatcher Lambda -> DynamoDB
Secrets in Secrets Manager. Least-privilege IAM (CDK grants). No AI yet: Part 3 plugs the agent into the dispatcher.
"""
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_sqs as sqs
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

        dlq = sqs.Queue(self, "InboxDLQ", fifo=True, retention_period=Duration.days(14),
                        encryption=sqs.QueueEncryption.SQS_MANAGED, enforce_ssl=True)
        inbox = sqs.Queue(
            self, "Inbox", fifo=True, content_based_deduplication=False,
            visibility_timeout=Duration.seconds(180),          # 6x the dispatcher timeout
            encryption=sqs.QueueEncryption.SQS_MANAGED, enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3),
        )

        cw.Alarm(self, "DLQNotEmpty", metric=dlq.metric_approximate_number_of_messages_visible(period=Duration.minutes(5)),
                 threshold=1, evaluation_periods=1, alarm_description="A message failed 3 times: look at the DLQ")

        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "DLQUrl", value=dlq.queue_url)
