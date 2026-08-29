---
name: aegis-roi
description: "Cost vs benefit attestation"
objective: "Every decision has a signed ROI report"
triggers: ["aegis posture", "ROI Attest"]
inputs: ["decision_id, tenant_id"]
outputs: ["ROIReport with net_usd"]
verify: "record_decision then report, check HMAC"
---

# aegis-roi

Optional skill. Attests cost and benefit for each decision and exposes it in posture.
