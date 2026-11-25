import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from infra.guardrails_stack import GuardrailsStack


def test_monthly_budget_alerts_at_50_80_100_and_forecast():
    t = Template.from_stack(GuardrailsStack(cdk.App(), "G", email="alerts@example.com", monthly_usd=20))
    budget = list(t.find_resources("AWS::Budgets::Budget").values())[0]["Properties"]
    assert budget["Budget"]["BudgetLimit"] == {"Amount": 20, "Unit": "USD"}
    got = sorted((n["Notification"]["NotificationType"], n["Notification"]["Threshold"])
                 for n in budget["NotificationsWithSubscribers"])
    assert got == [("ACTUAL", 50), ("ACTUAL", 80), ("ACTUAL", 100), ("FORECASTED", 100)]
    t.has_resource_properties("AWS::Budgets::Budget", {"NotificationsWithSubscribers": Match.array_with([
        Match.object_like({"Subscribers": [{"SubscriptionType": "EMAIL", "Address": "alerts@example.com"}]})])})
