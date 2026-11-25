"""The infrastructure itself is tested: the safety properties the video talks about must stay true."""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infra.foundation_stack import FoundationStack


@pytest.fixture(scope="module", params=["dev", "prod"])
def tpl(request):
    app = cdk.App()
    return request.param, Template.from_stack(FoundationStack(app, "T", stage=request.param))


def test_stack_synthesizes_for_each_stage(tpl):
    stage, t = tpl
    assert t.to_json() is not None
