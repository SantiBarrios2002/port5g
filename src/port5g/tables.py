"""Spec lookup tables that are constants of 3GPP releases (not scenario assumptions).

Each table carries its source. Values marked SECONDARY must be re-checked against the current release
(brief §10.3) — the check is a team task, recorded in docs/assumptions.md.
"""
from __future__ import annotations

# TS 38.214 Table 5.2.2.1-2 (4-bit CQI table 1, 64QAM): (modulation order Qm, code rate x1024, efficiency)
# SECONDARY — verify against current TS 38.214.
CQI_TABLE_1 = {
    1: (2, 78, 0.1523), 2: (2, 120, 0.2344), 3: (2, 193, 0.3770), 4: (2, 308, 0.6016),
    5: (2, 449, 0.8770), 6: (2, 602, 1.1758), 7: (4, 378, 1.4766), 8: (4, 490, 1.9141),
    9: (4, 616, 2.4063), 10: (6, 466, 2.7305), 11: (6, 567, 3.3223), 12: (6, 666, 3.9023),
    13: (6, 772, 4.5234), 14: (6, 873, 5.1152), 15: (6, 948, 5.5547),
}
CQI_TABLE_1_SOURCE = "3GPP TS 38.214 Table 5.2.2.1-2 (target BLER 0.1)"

# TS 38.211 Table 4.2-1: numerology -> subcarrier spacing
SCS_KHZ = {0: 15, 1: 30, 2: 60, 3: 120, 4: 240}
SYMBOLS_PER_SLOT = 14  # normal CP, TS 38.211 Table 4.3.2-1
SUBCARRIERS_PER_PRB = 12  # TS 38.211 §4.4.4.1

# TS 38.306 §4.1.2 constants
R_MAX = 948 / 1024
OH_FR1_DL = 0.14
OH_FR1_UL = 0.08
OH_FR2_DL = 0.18
OH_FR2_UL = 0.10

# Thermal noise density at T0 = 290 K: 10*log10(k*T0*1Hz) = -173.98 dBm/Hz ≈ -174 (physics; brief §4.2)
NOISE_DENSITY_DBM_HZ = -174.0

# TS 38.213 §11.1 slot format letters
SLOT_DL, SLOT_UL, SLOT_SPECIAL = "D", "U", "S"
