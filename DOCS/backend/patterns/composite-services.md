---
id: backend-pattern-composite-services
title: Composite Services
category: backend
tags: [pattern, composite, fan-out]
related: [backend-patterns-overview]
---

# Pattern 6: Composite Services

**When to Use**: Same operation needs to go to multiple destinations.

```
┌─────────────────────────────────────────────────────────────────┐
│                   COMPOSITE SERVICE                              │
│                                                                  │
│  log(event) {                                                    │
│    for (service in registeredServices) {                        │
│      service.log(event)  // Fan out to all                      │
│    }                                                             │
│  }                                                               │
│                                                                  │
│  Registered:                                                     │
│    ┌─────────────────┐                                          │
│    │ MixpanelService │                                          │
│    ├─────────────────┤                                          │
│    │ OpenMeterService│                                          │
│    └─────────────────┘                                          │
│                                                                  │
│  Use Cases:                                                      │
│    - Analytics to multiple providers                            │
│    - Notifications to multiple channels                         │
│    - Audit logging to multiple destinations                     │
└─────────────────────────────────────────────────────────────────┘
```


