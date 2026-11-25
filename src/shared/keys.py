"""Single-table key design. Every shop-owned item lives under SHOP#<shop_id>, so one shop can never read another's data.

    pk                      sk                         what
    SHOP#<shop_id>          META                       the shop (name, city, phone_number_id, created_at)
    PHONE#<phone_number_id> SHOP                       routing: which shop owns this WhatsApp number
    SHOP#<shop_id>          MSG#<iso time>#<wamid>     an inbound WhatsApp message (raw, for the ML lake later)
    DEDUP#<wamid>           DEDUP                      seen-message marker, expires after 7 days (TTL)
"""

DEDUP_TTL_SECONDS = 7 * 24 * 3600


def shop(shop_id: str) -> dict:
    return {"pk": f"SHOP#{shop_id}", "sk": "META"}


def phone(phone_number_id: str) -> dict:
    return {"pk": f"PHONE#{phone_number_id}", "sk": "SHOP"}


def message(shop_id: str, iso_time: str, wamid: str) -> dict:
    return {"pk": f"SHOP#{shop_id}", "sk": f"MSG#{iso_time}#{wamid}"}


def dedup(wamid: str) -> dict:
    return {"pk": f"DEDUP#{wamid}", "sk": "DEDUP"}
