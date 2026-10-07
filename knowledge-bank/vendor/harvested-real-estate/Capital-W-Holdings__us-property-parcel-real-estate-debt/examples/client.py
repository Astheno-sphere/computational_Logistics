#!/usr/bin/env python3
"""Minimal DFX MCP client. No dependencies beyond the standard library, no key.

    python3 client.py                       # discovery, then a worked question
    python3 client.py "100 Binney St" MA    # resolve one address
"""
import json
import sys
import urllib.request

DFX = "https://exchange-production-9123.up.railway.app/mcp"


def call(tool, arguments):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}}).encode()
    req = urllib.request.Request(
        DFX, data=body,
        headers={"Content-Type": "application/json",
                 # Naming yourself is optional and it is good manners. It does not
                 # authenticate you and DFX treats it as a claim, never as identity.
                 "X-Agent-Name": "dfx-example-client"})
    with urllib.request.urlopen(req, timeout=60) as r:
        env = json.loads(r.read())
    out = json.loads(env["result"]["content"][0]["text"])

    # EVERY DFX ANSWER CARRIES A `state`, INCLUDING THE REFUSALS, AND READING IT IS
    # THE WHOLE CONTRACT. A refusal is a well-formed envelope, not an exception and
    # not an empty list: RATE_LIMITED, NOT_COVERED, NO_MATCH and PAYMENT_REQUIRED all
    # arrive as HTTP 200 with a reason, a retry hint and `charged: false`.
    #
    # The budget is 20 requests per 60 seconds PER IDENTITY, where the identity is the
    # X-Agent-Name you send. Run this script four times in a minute and the twenty-first
    # call is refused, correctly, with `retry.after_seconds`.
    if not out.get("ok"):
        print(f"  [{out.get('state')}] {out.get('error')}")
        if out.get("retry"):
            print(f"  retry: {out['retry']}")
    return out


def main(argv):
    if argv:
        address, state = argv[0], (argv[1] if len(argv) > 1 else None)
        print(json.dumps(call("resolve_address",
                              {"address": address, "state": state}), indent=1))
        return 0

    # 1. Ask what it can do before assuming. It answers no clearly when the answer is no.
    plan = call("what_can_dfx_answer",
                {"objective": "which commercial mortgages in Ohio mature within a year"})
    print("CAN HELP:", plan.get("can_help"), "-> call", plan.get("use_capability"),
          "with", json.dumps(plan.get("arguments")))

    # 2. Free: the maturity events.
    events = call("search_property_events",
                  {"event_type": "LOAN_MATURITY_SCHEDULED", "state": "OH",
                   "within_days": 365})
    print("free events returned:", events.get("count"))
    if events.get("count"):
        print("  first:", events["results"][0]["headline"][:100])

    # 3. The paid tool, WITHOUT authorize. This is a quote. Nothing is charged.
    quote = call("debt_maturity_schedule", {"state": "OH"})
    print("state:", quote.get("state"))
    print("price:", (quote.get("price") or {}).get("amount_usd"), "USD")
    filt = (quote.get("delivers") or {}).get("for_your_filter") or {}
    print("rows this dollar buys:", filt.get("rows_you_will_receive"))
    print("charged:", quote.get("charged"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
