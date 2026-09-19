---
document: "Substation Operations Guide"
category: "Grid Operations"
equipment: "Substation System"
version: "4.1"
effective_date: "2024-02-01"
status: "active"
access_level: "Operations"
notice: "DEMO/FICTIONAL DOCUMENT FOR GRIDKNOWLEDGE RAG TESTING ONLY"
---

# Substation Operations Guide

--- Page 1 ---
## Section 1: Substation Layout and Primary Schemes
This guide specifies standard operational procedures for 132/33kV and 33/11kV transmission and distribution substations. Operations personnel must understand busbar arrangements (single bus, double bus with bus coupler, and breaker-and-a-half schemes) to execute load transfers safely.

--- Page 24 ---
## Section 2: 33kV Busbar Switching and Load Transfer
Busbar switching procedures mandate strict adherence to sequential interlocking rules:
1. Load Break Principle: Disconnector / isolator switches are NOT designed to interrupt load current or break short-circuits. Never open or close an isolator under load unless a parallel bypass path of negligible impedance is established.
2. Busbar Transfer Sequence (Double Busbar Scheme):
   - Step 1: Ensure the Bus Coupler Circuit Breaker is CLOSED and both Bus Coupler Isolators are CLOSED, tying Bus 1 and Bus 2 together at equal potential.
   - Step 2: Disable bus coupler overcurrent protection tripping temporarily (or engage bus transfer trip mode) to prevent uncoordinated tripping during switching surges.
   - Step 3: Close the destination bus selector isolator on the bay being transferred.
   - Step 4: Verify both bus isolators are simultaneously closed (on-load parallel condition).
   - Step 5: Open the original bus selector isolator.
   - Step 6: Verify feeder current remains balanced on the destination busbar.
   - Step 7: Re-enable bus coupler protection scheme.

--- Page 38 ---
## Section 3: SCADA Alarm Response and Transformer Overload Control
When SCADA telemetry issues an automated thermal or overcurrent alarm:
1. Step 1: Check active load MW/MVAR and oil/winding temperatures immediately.
2. Step 2: If transformer load exceeds 110% of rated MVA continuous for more than 15 minutes, start auxiliary forced cooling banks (Fans and Pumps).
3. Step 3: If temperature approaches trip thresholds (OTI 85°C, WTI 95°C), coordinate with Regional Load Dispatch Centre (RLDC) to initiate emergency feeder load shedding.
