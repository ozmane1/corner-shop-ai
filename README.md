# Corner Shop AI

A production AI assistant for a real corner shop in Casablanca, built in public by **Oz builds AI**.
The owner just asks on WhatsApp (French or English): stock, sales, customer credit, daily reports.
Agents built with **Strands** on **Bedrock AgentCore**, tools through **MCP**, a demand **forecasting model** on
**SageMaker AI**, and **MLOps** to keep it alive. 12 parts, 3 seasons, one real shop, real data. Every part is a video
and a git tag (`part-N`). Nothing is shown as built before it is built.

![Architecture](docs/architecture.png)

## Status: Part 2 · The foundation ✅

Before any AI: the boring part that keeps it alive.

```
WhatsApp ──► API Gateway (HTTP) ──► Ingest Lambda ──► SQS FIFO ──► Dispatcher Lambda ──► DynamoDB
                                      │  verify Meta signature        │ per-shop order      │ store under SHOP#<id>
                                      │  drop duplicates (Meta retries)│ 3 tries ──► DLQ ──► alarm
                                      │  find the shop, answer 200 fast
                                      └─ secrets: Secrets Manager
```

- **Infrastructure as code:** AWS CDK (Python), `dev` and `prod` stacks, region `eu-central-1` (Frankfurt: every
  AgentCore feature the later parts need). Nothing clicked in the console.
- **Multi-tenant from day one:** single table, every shop's data under `SHOP#<shop_id>`. Each Lambda's IAM policy is
  limited to the key prefixes it needs (`dynamodb:LeadingKeys`): ingest reads `PHONE#` and writes `DEDUP#`, the
  dispatcher only writes `SHOP#`. No scans, no deletes.
- **Never lose, never double:** dedupe by WhatsApp message id (conditional write + TTL) and SQS FIFO deduplication;
  idempotent writes; partial batch failures keep per-shop order; dead-letter queue + CloudWatch alarm.
- **Tested:** 19 tests (webhook signature, Meta handshake, retries, unknown numbers, ordering, idempotency) and
  infrastructure assertions (FIFO + DLQ, backups, scoped IAM, partial batch failures).

| Key (pk / sk) | What |
|---|---|
| `SHOP#<id>` / `META` | the shop |
| `PHONE#<phone_number_id>` / `SHOP` | which shop owns a WhatsApp number |
| `SHOP#<id>` / `MSG#<time>#<wamid>` | every inbound message (the raw data the forecasting model learns from later) |
| `DEDUP#<wamid>` / `DEDUP` | seen-message marker, expires after 7 days |

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
pytest -q                                   # unit + infrastructure tests, no AWS needed
npx aws-cdk synth                           # CloudFormation template
npx aws-cdk deploy -c stage=dev --profile <your-profile>
```

After deploying: put your Meta app secret in the `WhatsAppSecret` (`app_secret`; `verify_token` is generated), register
the shop with `scripts/register_shop.py`, point the Meta webhook to the `WebhookUrl` output, or test without Meta using
`scripts/send_test_webhook.py`.

## The 12 parts

| Season | Part | |
|---|---|---|
| 1 · The assistant | 1 The plan · **2 The foundation** · 3 The first agent · 4 Tools via MCP · 5 The credit notebook · 6 Live in the shop | |
| 2 · Make it reliable | 7 Stop it from lying · 8 Observability and cost per request | |
| 3 · Make it predict | 9 From chats to a dataset · 10 Forecasting · 11 The MLOps loop · 12 Drift and lessons | |

Next: **Part 3 · The first agent** (it starts talking back).

## License

MIT
