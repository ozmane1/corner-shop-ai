"""Part 2 · The foundation: everything the AI will stand on, as code.

WhatsApp -> API Gateway (HTTP API) -> Ingest Lambda -> SQS FIFO (+ DLQ) -> Dispatcher Lambda -> DynamoDB
Secrets in Secrets Manager. Least-privilege IAM. Part 3: the dispatcher asks the agent on AgentCore Runtime and replies.
"""
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from infra.agent_runtime import AgentRuntime

SRC = "src"


class FoundationStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, stage: str, agent_code: str = "build/agent", **kw) -> None:
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
            visibility_timeout=Duration.seconds(360),          # 6x the dispatcher timeout
            encryption=sqs.QueueEncryption.SQS_MANAGED, enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3),
        )

        whatsapp = secrets.Secret(
            self, "WhatsAppSecret",
            description="WhatsApp Cloud API: app_secret, verify_token (and later access_token)",
            generate_secret_string=secrets.SecretStringGenerator(
                secret_string_template='{"app_secret": "set-me"}', generate_string_key="verify_token",
                exclude_punctuation=True, password_length=40),
        )

        common = dict(
            runtime=lambda_.Runtime.PYTHON_3_13, architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset(SRC, exclude=["**/__pycache__", "*.egg-info"]),
            memory_size=256, tracing=lambda_.Tracing.ACTIVE,
        )

        def log_group(name):
            return logs.LogGroup(self, f"{name}Logs", retention=logs.RetentionDays.ONE_MONTH,
                                 removal_policy=RemovalPolicy.RETAIN if prod else RemovalPolicy.DESTROY)
        ingest = lambda_.Function(
            self, "Ingest", handler="ingest.handler.handler", timeout=Duration.seconds(10), log_group=log_group("Ingest"),
            environment={"TABLE_NAME": table.table_name, "QUEUE_URL": inbox.queue_url, "SECRET_ID": whatsapp.secret_arn},
            **common,
        )
        agent = AgentRuntime(self, "Agent", stage=stage, code_dir=agent_code)   # Part 3: the first agent

        dispatcher = lambda_.Function(
            self, "Dispatcher", handler="dispatcher.handler.handler", timeout=Duration.seconds(60), log_group=log_group("Dispatcher"),
            environment={"TABLE_NAME": table.table_name, "AGENT_RUNTIME_ARN": agent.arn, "SECRET_ID": whatsapp.secret_arn},
            **common,
        )
        # ~5 s per message with the agent: small batches keep a batch well inside the 60 s timeout
        dispatcher.add_event_source(sources.SqsEventSource(inbox, batch_size=5, report_batch_item_failures=True))

        # least privilege: ingest reads routing + writes dedup markers, sends to the queue, reads the secret
        def rows(actions, prefixes):
            return iam.PolicyStatement(actions=actions, resources=[table.table_arn], conditions={
                "ForAllValues:StringLike": {"dynamodb:LeadingKeys": [p + "*" for p in prefixes]}})
        ingest.add_to_role_policy(rows(["dynamodb:GetItem"], ["PHONE#"]))      # routing lookup only
        ingest.add_to_role_policy(rows(["dynamodb:PutItem"], ["DEDUP#"]))      # dedup markers only
        inbox.grant_send_messages(ingest)
        whatsapp.grant_read(ingest)
        dispatcher.add_to_role_policy(rows(["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"], ["SHOP#"]))  # shop rows only
        dispatcher.add_to_role_policy(iam.PolicyStatement(                     # may call this one agent, nothing else
            actions=["bedrock-agentcore:InvokeAgentRuntime"], resources=[agent.arn, f"{agent.arn}/*"]))
        whatsapp.grant_read(dispatcher)                                         # the WhatsApp token to reply

        api = apigw.HttpApi(self, "Webhook", description=f"corner-shop-ai {stage} WhatsApp webhook")
        hook = integrations.HttpLambdaIntegration("IngestIntegration", ingest)
        api.add_routes(path="/webhook", methods=[apigw.HttpMethod.GET, apigw.HttpMethod.POST], integration=hook)

        cw.Alarm(self, "DLQNotEmpty", metric=dlq.metric_approximate_number_of_messages_visible(period=Duration.minutes(5)),
                 threshold=1, evaluation_periods=1, alarm_description="A message failed 3 times: look at the DLQ")

        CfnOutput(self, "WebhookUrl", value=f"{api.api_endpoint}/webhook")
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "SecretArn", value=whatsapp.secret_arn)
        CfnOutput(self, "DLQUrl", value=dlq.queue_url)
        CfnOutput(self, "AgentRuntimeArn", value=agent.arn)
