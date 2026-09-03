"""
Thin wrapper around the Paystack REST API.

Only one server-side call is needed for the inline-popup flow:
  verify_transaction() -> confirms a reference actually succeeded

NEVER trust the browser-side callback() alone -- always re-verify
server-side before activating a subscription, since a client can fake
or replay that callback.
"""

import requests
from django.conf import settings


class PaystackError(Exception):
    pass


def verify_transaction(reference: str) -> dict:
    """
    Queries Paystack for the true status of a transaction.
    Returns the 'data' dict on success (contains status, amount in kobo,
    reference, customer, etc). Raises PaystackError otherwise.
    """
    resp = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        timeout=15,
    )
    data = resp.json()

    if not resp.ok or not data.get("status"):
        raise PaystackError(f"Paystack verification failed: {data}")

    return data["data"]