# Corner Shop AI

A production AI assistant for a real corner shop in Casablanca, built in public by **Oz builds AI**.
The owner just asks on WhatsApp (French or English): stock, sales, customer credit, daily reports.
Agents built with **Strands** on **Bedrock AgentCore**, tools through **MCP**, a demand **forecasting model** on
**SageMaker AI**, and **MLOps** to keep it alive. 12 parts, 3 seasons, one real shop, real data. Every part is a video
and a git tag (`part-N`). Nothing is shown as built before it is built.

## Status: Part 2 · The foundation (in progress)

Built step by step, one issue and one pull request per step.

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
pytest -q                                   # unit + infrastructure tests, no AWS needed
npx aws-cdk synth                           # CloudFormation template
npx aws-cdk deploy -c stage=dev --profile <your-profile>
```

## License

MIT
