---
document: "Grid Operations Standard"
category: "Standards"
equipment: "Interconnected Transmission Grid"
version: "GOS-101"
effective_date: "2023-07-01"
status: "active"
access_level: "Viewer"
notice: "DEMO/FICTIONAL DOCUMENT FOR GRIDKNOWLEDGE RAG TESTING ONLY"
---

# Enterprise Grid Operations Compliance Standard (GOS-101)

--- Page 1 ---
## Section 1: System Frequency and Voltage Tolerances
The transmission and distribution grid must be operated within rigid statutory quality boundaries:
1. System Frequency Limits:
   - Nominal Frequency: 50.00 Hz (or 60.00 Hz as regionally configured).
   - Standard Operating Band: 49.85 Hz to 50.15 Hz.
   - Emergency Low Frequency Limit: 49.20 Hz (initiates automatic under-frequency load shedding Stage 1).
   - Emergency High Frequency Limit: 50.50 Hz (initiates automatic generation tripping/curtailment).
2. Voltage Tolerances at Grid Delivery Points:
   - 132kV System: ± 10% (118.8 kV to 145.2 kV)
   - 33kV System: ± 6% (31.02 kV to 34.98 kV)
   - 11kV System: ± 6% (10.34 kV to 11.66 kV)

--- Page 18 ---
## Section 2: N-1 Reliability Criterion and Contingency Response
The transmission grid must be configured such that the unexpected tripping of any single transmission element (line, transformer, or generator) will not cause:
- Cascading line overloads exceeding 120% emergency thermal rating.
- Voltage collapse below 0.90 per-unit at any transmission substation.
- System instability or loss of customer load outside the tripped feeder zone.
All planned switching or maintenance requests that breach N-1 security must be rejected by the Dispatcher.
