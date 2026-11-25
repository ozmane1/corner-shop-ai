#!/usr/bin/env python3
"""CDK app: one foundation stack per stage.  cdk deploy -c stage=dev  (default dev; prod gets deletion protection)."""
import os

import aws_cdk as cdk

from infra.foundation_stack import FoundationStack

app = cdk.App()
stage = app.node.try_get_context("stage") or "dev"
FoundationStack(
    app, f"CornerShop-{stage}", stage=stage,
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=os.environ.get("CDK_DEFAULT_REGION")),
)
cdk.Tags.of(app).add("project", "corner-shop-ai")
cdk.Tags.of(app).add("stage", stage)
app.synth()
