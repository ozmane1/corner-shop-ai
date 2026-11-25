"""Account-level guardrails, deployed once (not per stage): a monthly AWS Budget with email alerts.

    cdk deploy CornerShop-guardrails -c alertEmail=you@example.com [-c budgetUsd=20]

The email is a deploy-time parameter so it is never committed to this public repo.
"""
from aws_cdk import Stack
from aws_cdk import aws_budgets as budgets
from constructs import Construct


class GuardrailsStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, email: str, monthly_usd: float = 20, **kw) -> None:
        super().__init__(scope, cid, **kw)
        alerts = [("ACTUAL", 50), ("ACTUAL", 80), ("ACTUAL", 100), ("FORECASTED", 100)]
        budgets.CfnBudget(
            self, "MonthlyBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name="corner-shop-ai-monthly", budget_type="COST", time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(amount=monthly_usd, unit="USD")),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        notification_type=kind, comparison_operator="GREATER_THAN", threshold=pct,
                        threshold_type="PERCENTAGE"),
                    subscribers=[budgets.CfnBudget.SubscriberProperty(subscription_type="EMAIL", address=email)])
                for kind, pct in alerts],
        )
