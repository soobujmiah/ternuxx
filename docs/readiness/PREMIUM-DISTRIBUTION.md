# Free core, paid services, and premium delivery design

**Status:** architecture proposal only; no package is approved for sale, no provider selected, and no payment or entitlement service exists. **Reviewed:** 2026-10-24.

## Product boundary today

Ternuxx is the owner-approved product and repository name; the public GitHub slug is `soobujmiah/ternuxx`. `./tx` is the source-checkout command and `tx` is the installed command; `ternuxx` remains a compatibility entrypoint. Ternuxx uses Native Termux as host/control plane with optional Debian PRoot workloads. The repository is public but unlicensed, has no release artifacts, and has no approved premium module. Public visibility is not a grant to redistribute code. The historical first-commit PolyForm Noncommercial/addendum statement remains a legal review issue. The owner must decide the source license after counsel reviews the exact history and provenance.

| Surface | Current state | Distribution/commercial treatment |
|---|---|---|
| Core CLI and lifecycle manager | Present in public source; product paths not qualified; no release | Keep no payment/feature-lock logic in existing core. A public checkout is not automatically an authorized redistributable installer. Resolve license and qualify releases first. |
| Optional Debian PRoot workload provider | Reauthorized and restored under P11; one-device live guest/client acceptance passed, while clean-device setup replay and broader qualification remain open | Treat Native and guest capabilities separately. Current workflow and limits are in P11 evidence and the capability matrix. |
| Termux, Termux:X11, Mesa/Turnip, XFCE, Wine/Hangover, llama-cpp, pinned Snapdragon HTP runtime and other Native runtime packages | Upstream components fetched from their own package/source channels; not bundled in a release | Record exact version, source, license and redistribution terms before bundling or mirroring. User-installed or privately downloaded upstream artifacts are distinct from redistributed binaries. |
| Premium software/modules | None implemented or approved | No payment gate, private repo, download URL or entitlement is operational. Each future component needs its own legal/provenance and security decision. |
| Installation/setup/support/customization/training | Service hypotheses only; no approved offer | Fulfill as a scoped service order and completion record, not a generic software download entitlement. No availability, price, SLA or warranty is promised. |

## Package catalog and entitlement records

If implementation is later approved, use one version-controlled catalog as the source for product pages and purchase options. Suggested fields:

```yaml
schema_version: 1
products:
  - id: core
    kind: software
    status: unavailable # proposed | available | retired
    entitlement: none
    artifact_source: github_release
  - id: assisted-setup
    kind: service
    status: unavailable
    fulfillment: scoped_service_order
```

The production catalog must add reviewed description, BDT price and tax treatment, buyer-facing terms version, implementation status, target environment, artifact/version or service deliverables, exclusions, compatibility evidence, support/updates period, refund/cancellation rule, license/provenance record, owner and approval date. `status: available` is forbidden until the exact artifact or service operation exists and passes its release gate. Do not publish this illustrative YAML as a real offer or invent purchase URLs.

Use separate product kinds and fulfillment states:

- **Software artifact:** product/version → paid order → verified entitlement → authorized download of that exact artifact/version.
- **License/entitlement:** product, order, account or customer reference, scope, start/end/revocation status, terms version. A license record states contractual permission; it does not stop copying.
- **Installation/configuration bundle:** only if it is generated and tested per supported profile. Never generate a customer bundle by placing credentials, SSH keys or personal data into source code.
- **Private source access:** a repository invitation is an access mechanism, not a license or copy-prevention mechanism. Use only for a separately reviewed proprietary module; audit membership and remove access on refund/expiry when terms allow.
- **Service order:** scope, prerequisites, consent, scheduled/delivery state, evidence/customer data minimization, completion and refund/dispute status; no software download entitlement unless separately purchased.

No premium feature currently meets these gates. Do not identify a current public feature as premium until legal review establishes that the feature may be separately distributed and a migration decision protects already published grants and users.

## Payment to fulfillment state machine

The design assumes a future public product site, an application backend, a transactional database, a payment provider selected after Bangladesh-first legal/accounting review, and private artifact storage. A static-only site cannot safely verify payments or authorize private artifacts. Do not put provider keys in browser code, repository settings exposed to untrusted PR builds, logs, or generated website assets.

1. **Discover:** site shows only catalog entries with approved `available` status, verified deliverable, current terms and complete price/tax display.
2. **Create checkout:** authenticated or minimal guest checkout creates a random internal order ID and server-side line item snapshot (SKU, version, amount/currency, terms version, fulfillment type). The browser never chooses the trusted price or SKU semantics.
3. **Redirect:** backend creates provider checkout using its secret credential and a provider idempotency key. Return URL carries only an opaque order reference; it is not proof of payment.
4. **Verify:** accept either a provider webhook whose signature is verified over the raw body using the provider's documented library, or an authenticated server-to-server status query. Check provider account/merchant, transaction ID, amount, currency, order association, product, and a final paid/captured state. Do not accept browser parameters or screenshots as payment evidence.
5. **Persist idempotently:** atomically record provider event/transaction ID and transition `pending → paid` once. Enforce uniqueness constraints; tolerate retries and out-of-order events by fetching the provider's current transaction state where necessary. Verify signatures, freshness/replay protections when supported, payload size/schema, rate limits, TLS, and constant-time MAC comparison as provider requires.
6. **Fulfill:** an asynchronous worker processes only verified paid orders. It issues the purchased artifact access or creates a service work item matching the purchased product. Re-check order and entitlement on every private download. Keep order and fulfillment states distinct.
7. **Notify:** send a minimal receipt/order reference and access instructions through an owner-approved channel. Never include a password or long-lived token in ordinary email. A redirect success page can say “payment is being confirmed”; it cannot grant access.
8. **Refund/reversal/chargeback:** provider event or verified staff action creates an auditable state transition. Apply the published terms; revoke future access where contractually allowed, preserve a record of what was delivered, and handle service work already performed under reviewed rules. Do not automatically erase a customer account or source copy.
9. **Reconcile:** scheduled/manual reconciliation compares provider transactions, internal orders, refunds and fulfillment. Alert on paid-but-unfulfilled and fulfilled-but-reversed cases. Keep a narrow, audited manual-review path.

Recommended states:

`created → checkout_pending → payment_pending → paid → fulfillment_pending → fulfilled`

Side states: `failed`, `expired`, `cancelled`, `refund_pending`, `partially_refunded`, `refunded`, `disputed`, `reversed`, `revoked`, `manual_review`. State transitions must be validated server-side and recorded with actor, time, reason and source event ID. Only `paid` may trigger fulfillment, and only while not refunded, disputed, reversed or revoked under the approved policy.

OWASP webhook guidance supports signature verification, replay/duplicate handling, idempotency, rate limiting and avoiding full payload/secrets in logs. Provider-specific rules must take precedence; do not invent one generic signature format. See [OWASP Webhook Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html).

## Customer-specific download security

Preferred flow: customer signs into or proves control of an order-bound account/session; backend checks entitlement for the exact SKU/version; private object storage returns a narrowly scoped signed URL with short expiry (initial design target: 1–5 minutes, subject to provider constraints). Alternatively issue a random 256-bit one-time opaque token, store only a hash, bind it to order/artifact, expire it quickly, and atomically consume it. Do not encode email, username, order sequence or entitlement data into the URL.

Controls:

- Keep premium objects private; public GitHub release assets are not premium. Store artifacts outside the public repository/releases.
- Check entitlement at link issuance and, where supported, at download. Use HTTPS, unguessable token material, short expiry, least-privilege object credentials, and no directory listing.
- Redact tokens and query strings from access/application logs and referrer headers; set `Referrer-Policy: no-referrer` on download pages. Rate-limit issuance and downloads; cap artifact size and monitor unusual access.
- Make revocation effective for new authorizations. Already downloaded source/binaries cannot be remotely recalled or made non-copyable; signatures/checksums identify artifacts but do not enforce a license.
- Do not impose arbitrary device/download counts by default. If a limit is justified, disclose it, provide a recovery/support process and avoid invasive device fingerprinting.
- Use checksum and signed release provenance where feasible. Keep signing keys offline or in an approved managed secret store; separate release signing from web-serving credentials.
- Treat browser download endpoints as untrusted inputs; validate artifact IDs against catalog records, not user-supplied storage paths.

## Separation of technical and contractual enforcement

| Method | Useful for | Limitation |
|---|---|---|
| Private artifact storage + expiring signed URL | Restricts initial download to paid orders | Once downloaded, software can be copied; provider URL leakage is possible until expiry |
| Server-side entitlement check | Hosted features, update feeds, or per-download authorization | Requires service availability, personal/order data and operational security; not suitable as mandatory check for offline core |
| Local license verification | Optional offline functionality/updates if designed carefully | Local checks can be patched; signing secret must never ship in the client; public-key signatures prove issuer, not prevent redistribution |
| Contractual license/terms | Defines permission, support, redistribution and remedies | Enforcement requires valid terms, notice/assent, jurisdiction and practical dispute process; counsel needed |
| Separate private source repository | Controls initial source access and collaboration | Invitations can be copied; does not replace a license or prevent onward disclosure |

Do not implement DRM, always-online activation, telemetry, recurring billing or feature locks by default. Keep the free core useful and independent; an offline customer must retain the capabilities granted by its approved license.

## Privacy, refunds, support, and owner decisions

Minimum records should be order ID, provider transaction reference, purchased item/version, amount/currency, status, terms version, necessary billing/receipt details, event IDs and fulfillment status. Retention periods, access roles, deletion exceptions, backups, processor/location, breach handling and lawful basis require Bangladesh privacy/legal review before launch. Do not collect device identifiers, Android serials, SSH keys, full logs or NID unless a qualified professional determines a specific legal need and the owner approves it.

Before offering anything for sale, approve: legal entity/individual seller; provider availability and contract for Bangladesh; BDT price and tax/invoice handling; privacy notice; terms and refund/cancellation/dispute rules; service scope and response expectations; customer support channel and retention; artifact license/provenance; provider and object storage location; access recovery; incident/refund manual procedure. Existing laws researched in [LEGAL-IP.md](LEGAL-IP.md) require individualized legal/accounting review; this design does not resolve applicability.

## Implementation gate

No payment provider, order database, backend, premium artifact store, account system or checkout has been selected or built. Implementation is blocked until the owner approves a specific offering, license/provenance, seller/payment route, data policy, service/refund terms, and production scope. A later static website prototype can show no prices or checkout, and must mark all unapproved offerings unavailable.
