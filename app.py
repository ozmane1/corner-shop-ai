#!/usr/bin/env python3
"""CDK app.

    cdk deploy -c stage=dev                         foundation stack per stage (prod gets deletion protection)
    cdk deploy CornerShop-guardrails -c alertEmail=you@example.com [-c budgetUsd=20]   account-level budget alerts
"""
import os

import aws_cdk as cdk

from infra.foundation_stack import FoundationStack
from infra.guardrails_stack import GuardrailsStack

app = cdk.App()
env = cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=os.environ.get("CDK_DEFAULT_REGION"))
stage = app.node.try_get_context("stage") or "dev"
FoundationStack(app, f"CornerShop-{stage}", stage=stage, env=env)
email = app.node.try_get_context("alertEmail")
if email:                                   # only when deploying the guardrails (keeps the email out of the repo)
    GuardrailsStack(app, "CornerShop-guardrails", email=email,
                    monthly_usd=float(app.node.try_get_context("budgetUsd") or 20), env=env)
cdk.Tags.of(app).add("project", "corner-shop-ai")
cdk.Tags.of(app).add("stage", stage)
app.synth()
