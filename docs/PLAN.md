# ClaimFlow main plan

Build a synthetic insurance support demonstration that follows the [original assignment](ASSIGNMENT.md): strict identity and authorization gates with bounded natural-language interpretation, grounded claim discussion and explicit follow-up consent.

## Maintained contract

1. **Verify identity.** Require at least three distinct approved fields matching one policyholder; policy numbers do not count. Preserve early questions without reading claims. Representatives require independent identity and a scoped grant; public chat cannot supply that proof.
2. **Resolve intent.** Reuse early hints, ask about ambiguous records and restrict every read to the authorized policyholder. Identity/role changes invalidate incompatible access and consent.
3. **Process the case.** Interpret caller questions through a typed model proposal; render facts from the supplied fixtures and mapped document guidance. Preserve monetary meanings, expired deadlines and unresolved questions separately for each claim.
4. **Post-process.** Offer a grounded summary of the discussed claims and follow-ups. Send simulation and Skip are explicit actions bound to the current recipient, preview and expiry. Chat assent never sends anything.
5. **Recover safely.** Offer empathy, alternate identity fields and voluntary human-assistance pause without bypassing gates. Preserve committed conversations across failures/restarts and reject conflicting concurrent mutations.
6. **Demonstrate and verify.** Keep Playground, Inspector and scripted Evaluation Lab consistent. Use isolated backend/policy/browser tests, a production frontend build and Docker checks where feasible. Label live-model evidence separately.

## Scope

One FastAPI service, React/Vite, encrypted SQLite and native fixed-host model adapters. Keep the original six JSON fixtures unchanged under [fixtures](fixtures). No real email, transfer, uploads, payments, appeals or claim changes. No production identity assurance is claimed.

Focused review fixes and current test evidence live in [VALIDATION.md](VALIDATION.md); architecture and setup live in [ARCHITECTURE.md](ARCHITECTURE.md) and [USAGE.md](USAGE.md). Historical intermediate plans stay local and ignored. Deployments and merging to main require a separate owner action.
