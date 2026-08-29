---
name: aegis-watch
description: "Live flow and notifications"
objective: "Every event on the bus is visible in the TUI and alerts on drift or BLOCK"
triggers: ["aegis watch", "aegis tui"]
inputs: ["event bus subscription"]
outputs: ["flow log + notification"]
verify: "subscribe to bus, tail events, emit alert on drift"
---

# aegis-watch

Required skill. Streams the EventBus to the TUI Flow tab and the notification pane. Alerts when Ship Gate BLOCKs or SwapWatch drifts.
