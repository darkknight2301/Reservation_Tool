"""Shared helper for building the ``HX-Trigger`` response header used by every admin/web router."""
import json


def hx_trigger(message: str, message_type: str = "info", close_dialog: bool = False) -> str:
    """
    Build an ``HX-Trigger`` header value that fires app.js's ``showToast``
    handler, and -- only when ``close_dialog`` is True -- its
    ``closeDialog`` handler too.

    Callers must only pass ``close_dialog=True`` on a genuine success path
    for an action that originated from a modal dialog, so that a
    validation/business-rule error leaves the dialog open for the user to
    correct and resubmit instead of silently discarding their input.
    """
    payload = {"showToast": {"message": message, "type": message_type}}
    if close_dialog:
        payload["closeDialog"] = {}
    return json.dumps(payload)
