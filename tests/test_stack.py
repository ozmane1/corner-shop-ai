"""The infrastructure itself is tested: the safety properties the video talks about must stay true."""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infra.foundation_stack import FoundationStack


@pytest.fixture(scope="module", params=["dev", "prod"])
def tpl(request):
    app = cdk.App()
    return request.param, Template.from_stack(FoundationStack(app, "T", stage=request.param))


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
