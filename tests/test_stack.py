"""The infrastructure itself is tested: the safety properties the video talks about must stay true."""
import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infra.foundation_stack import FoundationStack


@pytest.fixture(scope="module", params=["dev", "prod"])
def tpl(request, tmp_path_factory):
    code = tmp_path_factory.mktemp("agent")            # a tiny stand-in for build/agent
    (code / "main.py").write_text("print('agent')\n")
    app = cdk.App()
    return request.param, Template.from_stack(FoundationStack(app, "T", stage=request.param, agent_code=str(code)))


def test_queue_is_fifo_with_dead_letter_queue(tpl):
    _, t = tpl
    t.resource_count_is("AWS::SQS::Queue", 2)
    t.has_resource_properties("AWS::SQS::Queue", {"FifoQueue": True, "RedrivePolicy": {"maxReceiveCount": 3, "deadLetterTargetArn": Match.any_value()}})


def test_table_has_backups_and_ttl(tpl):
    stage, t = tpl
    t.has_resource_properties("AWS::DynamoDB::GlobalTable", {
        "TimeToLiveSpecification": {"AttributeName": "ttl", "Enabled": True},
        "Replicas": [Match.object_like({"PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
                                        "DeletionProtectionEnabled": stage == "prod"})]})


def test_lambdas_only_touch_their_own_key_prefixes(tpl):
    _, t = tpl
    policies = t.find_resources("AWS::IAM::Policy")
    ddb_statements = [s for p in policies.values() for s in p["Properties"]["PolicyDocument"]["Statement"]
                      if any(str(a).startswith("dynamodb:") for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]]))]
    assert ddb_statements, "expected DynamoDB statements"
    for s in ddb_statements:
        assert "dynamodb:LeadingKeys" in str(s.get("Condition")), f"unscoped table access: {s['Action']}"
        assert "dynamodb:Scan" not in str(s["Action"]) and "dynamodb:DeleteItem" not in str(s["Action"])


def test_dispatcher_reports_partial_batch_failures(tpl):
    _, t = tpl
    t.has_resource_properties("AWS::Lambda::EventSourceMapping", {"FunctionResponseTypes": ["ReportBatchItemFailures"]})


def test_webhook_route_exists(tpl):
    _, t = tpl
    t.has_resource_properties("AWS::ApiGatewayV2::Route", {"RouteKey": "POST /webhook"})
    t.has_resource_properties("AWS::ApiGatewayV2::Route", {"RouteKey": "GET /webhook"})


def test_agent_runs_on_agentcore_with_only_the_haiku_eu_profile(tpl):
    stage, t = tpl
    t.has_resource_properties("AWS::BedrockAgentCore::Runtime", {
        "AgentRuntimeName": f"corner_shop_{stage}",
        "AgentRuntimeArtifact": {"CodeConfiguration": {"EntryPoint": ["main.py"], "Runtime": "PYTHON_3_13"}}})
    statements = [s for p in t.find_resources("AWS::IAM::Policy").values()
                  for s in p["Properties"]["PolicyDocument"]["Statement"]
                  if "bedrock:InvokeModel" in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])]
    assert len(statements) == 1                                       # only the agent may call a model
    text = str(statements[0]["Resource"])
    assert "inference-profile/eu.anthropic.claude-haiku-5-5" in text and "foundation-model/anthropic.claude-haiku-5-5" in text


def test_dispatcher_may_call_only_its_agent(tpl):
    _, t = tpl
    statements = [s for p in t.find_resources("AWS::IAM::Policy").values()
                  for s in p["Properties"]["PolicyDocument"]["Statement"]
                  if "bedrock-agentcore:InvokeAgentRuntime" in str(s["Action"])]
    assert len(statements) == 1 and "*" not in json.dumps(statements[0]["Resource"]).replace("/*", "")
