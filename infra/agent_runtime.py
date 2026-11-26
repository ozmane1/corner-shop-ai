"""Part 3 · The agent on Amazon Bedrock AgentCore Runtime (serverless, one isolated microVM per session).

Direct code deploy: build/agent (from scripts/build_agent.py) is zipped to S3 by CDK and started as main.py on Python 3.13.
The runtime role may call only the Claude Haiku EU inference profile (and the models behind it), write its logs and traces.
"""
import os

from aws_cdk import Aws, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_assets as s3_assets
from constructs import Construct

MODEL_ID = "eu.anthropic.claude-haiku-5-5"
BASE_MODEL = "anthropic.claude-haiku-5-5*"


class AgentRuntime(Construct):
    def __init__(self, scope: Construct, cid: str, *, stage: str, code_dir: str) -> None:
        super().__init__(scope, cid)
        if not os.path.isfile(os.path.join(code_dir, "main.py")):
            raise FileNotFoundError(f"{code_dir}/main.py missing: run `python scripts/build_agent.py` first")
        code = s3_assets.Asset(self, "Code", path=code_dir)          # a folder: CDK zips and uploads it

        role = iam.Role(self, "Role", assumed_by=iam.ServicePrincipal(
            "bedrock-agentcore.amazonaws.com",
            conditions={"StringEquals": {"aws:SourceAccount": Aws.ACCOUNT_ID}}))
        region = Stack.of(self).region
        role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[f"arn:aws:bedrock:{region}:{Aws.ACCOUNT_ID}:inference-profile/{MODEL_ID}",
                       f"arn:aws:bedrock:*::foundation-model/{BASE_MODEL}"]))     # the EU profile routes across EU regions
        role.add_to_policy(iam.PolicyStatement(
            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"],
            resources=[f"arn:aws:logs:{region}:{Aws.ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*"]))
        role.add_to_policy(iam.PolicyStatement(
            actions=["logs:DescribeLogGroups", "xray:PutTraceSegments", "xray:PutTelemetryRecords",
                     "cloudwatch:PutMetricData"], resources=["*"]))  # these APIs have no resource-level scoping
        code.grant_read(role)

        self.runtime = agentcore.CfnRuntime(
            self, "Runtime",
            agent_runtime_name=f"corner_shop_{stage}",
            description="Corner Shop AI: understands the owner's WhatsApp messages",
            role_arn=role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                code_configuration=agentcore.CfnRuntime.CodeConfigurationProperty(
                    code=agentcore.CfnRuntime.CodeProperty(s3=agentcore.CfnRuntime.S3LocationProperty(
                        bucket=code.s3_bucket_name, prefix=code.s3_object_key)),
                    entry_point=["main.py"], runtime="PYTHON_3_13")),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            protocol_configuration="HTTP",
            environment_variables={"MODEL_ID": MODEL_ID, "AWS_DEFAULT_REGION": region},
        )
        self.runtime.node.add_dependency(role)
        self.arn = self.runtime.attr_agent_runtime_arn
