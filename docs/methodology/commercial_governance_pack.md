# Signal Review service boundaries and data handling

Updated September 23, 2026. This current reference replaces the earlier v7 commercial-status wording. Historical releases and their decision records remain unchanged.

## Service and scope

The free Apache-2.0 software and optional paid Signal Review research services are described separately in [pricing](../pricing.md). Request a scope call through the [Signal Review page](../signal_review.html). Scope, fees, data handling, delivery arrangements and invoicing are agreed in writing before work begins.

Signal Review reports research classifications, including adverse and inconclusive findings. It does not provide investment recommendations, execute trades or promise financial returns. A fee does not buy a favourable finding or a standing above EXPLORATORY (CLIENT).

## Data flow

- Local pre-check: `yuclaw intake-check` reads the file on the user's machine and does not transmit it.
- Initial contact: a general scope request through GitHub. Do not post proprietary signals, datasets or confidential information in public issues.
- Website: no upload endpoint or payment checkout. These boundaries remain enforced by the no-form gate.
- Analysis and delivery: local processing, with data handling agreed for the engagement before files are provided. Client material must not enter the public repository. Delivered bundles follow the derived-data export rule and exclude raw vendor rows.
- Receipt program: private receipt, challenge and decision stores are separate from client engagement records. Public export requires its designated review and publication policy; it is not activated by a service inquiry.

## Retention and evidence

Public artifacts and historical releases are retained as published; corrections supersede rather than erase records. The receipt software's private stores are append-only and have no deletion path. Engagement-specific retention and delivery arrangements must therefore be specified accurately; this page does not promise an unimplemented deletion or backup function.

The [Evidence Scoreboard](../evidence_scoreboard.html) reports recorded evidence, with real zero, pending and unavailable states. Service availability is not a signed engagement, an independent audit or a demonstrated human benefit. Current evidence counts are read from that scoreboard rather than repeated here.

See [API terms](../API_TERMS.md) for the API's research-use, acceptable-use, attribution and privacy provisions. This service description makes no regulatory endorsement, grant-eligibility or independent security-certification claim.
