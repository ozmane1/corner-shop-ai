"""Part 3 · The first agent: reads one WhatsApp message from the shop owner and understands it.

"sold 3 bread", "vendu 2 lait et 1 sucre", "Karim owes 40 dh" -> a typed result (intent, items, customer, amount)
plus a short reply in the owner's language. Strands Agents + Claude Haiku 5.5 on Amazon Bedrock (EU inference profile).
Nothing here writes to the database: the dispatcher stores what was understood; real tools arrive in Part 4 (MCP).
"""
import os
from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent
from strands.models import BedrockModel

MODEL_ID = os.environ.get("MODEL_ID", "eu.anthropic.claude-haiku-5-5")

SYSTEM = """You are the assistant of a small corner shop in Casablanca. The owner texts you on WhatsApp,
in French or English, often short, mixed, with typos or abbreviations ("vendu 2 lait", "sold 3 bread", "dh" = dirhams).

Understand ONE message and fill the result:
- intent: sale (he sold something), restock (goods came in), credit (a customer took goods or money on credit,
  or paid back part of it), question (he asks something), other (greetings, thanks, anything else).
- items: every product with its quantity (and unit if given). Use the product name the way he wrote it, singular.
- customer and amount_mad: for credit only. A payment back is a negative amount.
- language: "fr" or "en", the language of his message.
- reply: one or two short lines in HIS language (in French, use "vous"), like a helpful shop assistant. Repeat back what you understood
  so he can spot a mistake. Never invent numbers. If a quantity or product is missing or unclear, ask for it.
  You cannot see stock or sales history yet: for questions, say you will be able to answer soon.
"""


class Item(BaseModel):
    product: str = Field(description="product name, singular, as the owner wrote it")
    quantity: float = Field(description="how many")
    unit: str | None = Field(default=None, description="kg, L, pack... only if the owner said it")


class Understood(BaseModel):
    intent: Literal["sale", "restock", "credit", "question", "other"]
    items: list[Item] = Field(default_factory=list)
    customer: str | None = None
    amount_mad: float | None = Field(default=None, description="credit amount in dirhams, negative when paid back")
    language: Literal["fr", "en"]
    reply: str = Field(description="short reply to the owner, in his language")


def make_agent(model=None) -> Agent:
    model = model or BedrockModel(model_id=MODEL_ID, max_tokens=400)
    return Agent(model=model, system_prompt=SYSTEM, callback_handler=None)


def understand(text: str, agent: Agent | None = None) -> Understood:
    """One message in, one typed result out. A fresh agent per message: no memory yet (that is Part 5)."""
    agent = agent or make_agent()
    return agent(text.strip()[:1000], structured_output_model=Understood).structured_output
