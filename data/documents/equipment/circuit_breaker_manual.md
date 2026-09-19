---
document: "Circuit Breaker Manual"
category: "Equipment"
equipment: "Circuit Breaker"
version: "5.0"
effective_date: "2023-11-01"
status: "active"
access_level: "Maintenance"
notice: "DEMO/FICTIONAL DOCUMENT FOR GRIDKNOWLEDGE RAG TESTING ONLY"
---

# Circuit Breaker Technical and Maintenance Manual

--- Page 1 ---
## Section 1: Equipment Classification and Ratings
This manual covers 33kV and 11kV medium-voltage switchgear circuit breakers, including SF6 gas-insulated puffer circuit breakers and vacuum circuit breakers (VCB).

Standard Technical Ratings:
- Rated Voltage: 36 kV
- Rated Continuous Current: 1250 A / 2000 A / 3150 A
- Rated Short-Circuit Breaking Current: 25 kA / 31.5 kA (3 sec)
- Operating Duty Cycle: O - 0.3s - CO - 3min - CO
- Stored Energy Operating Mechanism: Motor-charged spring mechanism with manual charging facility

--- Page 14 ---
## Section 2: SF6 Gas Pressure Monitoring and Density Limits
SF6 gas provides arc quenching and phase-to-ground dielectric insulation. Density is monitored via temperature-compensated pressure gauges.

Pressure Thresholds at 20°C Reference:
1. Normal Operating Filling Pressure: 0.60 MPa (6.0 bar absolute)
2. Low Pressure Alarm Stage 1: 0.52 MPa (5.2 bar). Trigger SCADA alarm and schedule leak detection within 24 hours.
3. Low Pressure Lockout Stage 2: 0.50 MPa (5.0 bar). Automatic electrical and mechanical trip/close interlock activates. Breaker must not be operated until refilled and certified.
4. Gas Purity: Minimum 97.0% SF6 volume. Maximum moisture content: 150 ppm (v/v) for in-service gas.

--- Page 22 ---
## Section 3: Vacuum Circuit Breaker (VCB) Inspection Procedure
For 11kV and 33kV Vacuum Circuit Breakers:
1. Contact Erosion Measurement:
   - Check contact erosion gauge located on the vacuum interrupter moving stem.
   - If the red line on the contact wear indicator is fully concealed when breaker is closed, the vacuum bottle has reached its end of electrical life (maximum allowable erosion is 3.0 mm) and must be replaced.
2. Vacuum Integrity Test (Hipot Test):
   - Apply 28 kV AC (rms) across open contacts for 1 minute for 11kV breakers; 70 kV AC for 33kV breakers. No flashover or puncture shall occur.
3. Operating Mechanism Timing:
   - Breaker Closing Time: <= 65 ms
   - Breaker Opening Time: <= 45 ms
   - Contact Bounce during closing: <= 2.0 ms
4. Lubrication:
   - Apply synthetic grease (Aeroshell 22 or Isoflex LDS 18) to trip latch rollers, motor gears, and spring linkages. Never use WD-40 or penetrating petroleum oils on trip latches.
