#!/usr/bin/env python3
"""Send one message to the deployed agent on AgentCore Runtime and print what it understood.

    AWS_PROFILE=... AWS_DEFAULT_REGION=eu-central-1 python scripts/ask_agent.py "vendu 2 lait" [--stack CornerShop-dev]
"""
import argparse
import json
import time
import uuid

import boto3

p = argparse.ArgumentParser()
p.add_argument("text")
p.add_argument("--stack", default="CornerShop-dev")
a = p.parse_args()
outputs = boto3.client("cloudformation").describe_stacks(StackName=a.stack)["Stacks"][0]["Outputs"]
arn = next(o["OutputValue"] for o in outputs if o["OutputKey"] == "AgentRuntimeArn")
t0 = time.time()
r = boto3.client("bedrock-agentcore").invoke_agent_runtime(
    agentRuntimeArn=arn, runtimeSessionId=f"cli-{uuid.uuid4()}", payload=json.dumps({"text": a.text}).encode())
print(json.dumps(json.loads(r["response"].read()), ensure_ascii=False, indent=1))
print(f"({time.time() - t0:.1f} s)")
