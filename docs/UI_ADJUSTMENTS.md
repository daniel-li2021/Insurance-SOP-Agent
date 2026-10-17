# Evaluation Lab header follow-up — October 17, 2026

Moved “Scripted tests / No model calls” from the Lab subtitle into a compact badge in the global header, visible only while Evaluation Lab is selected. Narrow layouts wrap the header to keep the badge and controls readable. Scenario replay, evidence tabs and policy behavior are unchanged. The existing Lab browser test now checks header placement and tablet visibility as well as desktop/mobile overflow.

The production TypeScript/Vite build passes. No additional browser/backend checks were run after the owner requested no further inspection. The earlier validation below remains historical. Apply a manual Render deploy to publish this source change.

# Interface adjustments — October 17, 2026

- Removed the persistent 12-new-sessions/hour creation cap. New Session still replaces the old session, clears identity/conversation/consent, and follows the existing optional encrypted-key retention preference. Turn, identity-attempt, model-settings, summary-action, evaluation, concurrency and token limits remain in place.
- The Inspector’s “Evidence used for this response” table now shows readable source names in one full-width column. Original reference values remain in the response data and expandable full decision history.
- Moved the Lab’s scripted/no-model-call note into small subtitle text. Reduced scenario-header padding and title gaps; on wide screens, run/result controls use the space beside the scenario description. Narrow screens stack these controls. The replay, assertion and trace views retain their behavior.

## Validation

- 73 focused backend/API/settings/recovery checks pass, including 15 consecutive fresh sessions within one fixed hour and normal 24-hour expiry.
- Production TypeScript/Vite build passes.
- Three focused local offline Chromium journeys pass: grounded denial/evidence/summary/send/refresh, Lab replay/assertions/reset, and failed-reset recovery preserving conversation. The Lab was checked at 1440×900 and 390×844 with replay content in view and no horizontal overflow; both screenshots were visually inspected and remain under ignored `data/ui-adjustments/`. The installed Playwright browser revision was absent, so checks used existing cached Chromium via a temporary configuration, outside the filesystem sandbox required by macOS process startup. No browser dependency was installed.

The full test suites, Docker rebuild, paid model calls and deployment were not run. Restart an already-running backend to load the removed session cap. Earlier validation reports describe their historical trees, including the former hourly session cap.
