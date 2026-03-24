import os
from dotenv import load_dotenv
from datetime import datetime
import numpy as np
from zoneinfo import ZoneInfo
toronto = ZoneInfo('America/Toronto')

load_dotenv()

LICOR_TOKEN = os.getenv("LICOR_TOKEN")

DEVICE_SERIAL = '21329018'

CALCULATION_TYPE = 'METERED'
START_TIME = int(datetime(2026, 2, 26, 8, 24, 0, tzinfo=toronto).timestamp() * 1000)
END_TIME = int(datetime(2026, 2, 28, 7, 22, 0, tzinfo=toronto).timestamp() * 1000)

SENSOR_MAP = {
    'TempIn1':'20466913-1',
    'TempIn2':'20466914-1',
    'TempOut1':'20466915-1',
    'TempOut2':'20590610-1',
    'ScaledVoltage':'20536129-1',
    'ScaledCurrent':'20536129-2',
    'ScaledSeries':'21433559-1',
}

ROCK_FORMATIONS = {
    "Shale": {
        "density_lbft3": 169,      # from CSV: 169 lbs/ft³ (2.7 g/cm³ × 62.4)
        "tc_btu": 1.45,            # from Roberts Field reference
        "cp_btu": 0.21             # from Roberts Field reference
    },
    "Limestone": {
        "density_lbft3": 162,      # from CSV: 162 lbs/ft³ (2.6 g/cm³ × 62.4)
        "tc_btu": 1.74,            # from Table 2.2 (Kappelmeyer 1974)
        "cp_btu": 0.20             # from Table 2.7 (851 J/kg·C → 0.203 BTU/lb·F)
    },
    "Dolomite": {
        "density_lbft3": 177,      # from CSV: 177 lbs/ft³ (2.83 g/cm³ × 62.4)
        "tc_btu": 2.88,            # from Table 2.2
        "cp_btu": 0.19             # from Table 2.7 (802 J/kg·C → 0.191 BTU/lb·F)
    },
    "Sandstone": {
        "density_lbft3": 165,      # from CSV: ~165 lbs/ft³ (2.64 g/cm³ × 62.4)
        "tc_btu": 3.29,            # from Table 2.2 (Quartz Sandstone, Parallel)
        "cp_btu": 0.17             # from engineeringtoolbox reference (710 J/kg·C → 0.17)
    },
    "Quartzite_Schist": {
        "density_lbft3": 169,      # from Table 2.7: 2.71 g/cm³ × 62.4 = 169
        "tc_btu": 2.42,            # 4.19 W/mK × 0.577789 = 2.42 BTU/hr·ft·F
        "cp_btu": 0.20             # 858 J/kg·C × 0.000238846 = 0.205 BTU/lb·F
    },
    "Clay": {
        "density_lbft3": 130,      # from CSV: 2.08 g/cm³ × 62.4 = 130
        "tc_btu": 0.82,            # from Table 2.7 (Chalk as proxy for clay)
        "cp_btu": 0.51             # from Table 2.7 (2127 J/kg·C → 0.508 BTU/lb·F)
    },
    "Sand": {
        "density_lbft3": 120,      # from Roberts Field reference
        "tc_btu": 1.10,            # from Roberts Field reference
        "cp_btu": 0.20             # from Roberts Field reference
    },
    "Gravel": {
        "density_lbft3": 125,      # from Roberts Field reference
        "tc_btu": 1.15,            # from Roberts Field reference
        "cp_btu": 0.20             # from Roberts Field reference
    },
    "Marl": {
        "density_lbft3": 123,      # from CSV: 1.97 g/cm³ × 62.4 = 123
        "tc_btu": 0.80,            # from Table 2.7 (1.38 W/mK × 0.577789)
        "cp_btu": 0.41             # from Table 2.7 (1734 J/kg·C → 0.414 BTU/lb·F)
    },
    "Siltstone": {
        "density_lbft3": 160,      # from CSV: 2.566 g/cm³ × 62.4 = 160
        "tc_btu": 1.28,            # 2.22 W/mK × 0.577789 = 1.28
        "cp_btu": 0.19             # 795 J/kg·C × 0.000238846 = 0.19
    },
    "Mudstone": {
        "density_lbft3": 160,      # from CSV: 2.555 g/cm³ × 62.4 = 159.5
        "tc_btu": 1.30,            # 2.25 W/mK × 0.577789 = 1.30
        "cp_btu": 0.20             # 838 J/kg·C × 0.000238846 = 0.20
    },
    "Argillite": {
        "density_lbft3": 160,      # from CSV: 2.555 g/cm³ × 62.4 = 159.5
        "tc_btu": 1.30,            # same as mudstone basically
        "cp_btu": 0.20
    },
    "Halite": {
        "density_lbft3": 135,      # from CSV: 2.16 g/cm³ × 62.4 = 135
        "tc_btu": 3.53,            # from Table 2.2 (6.11 W/mK × 0.577789)
        "cp_btu": 0.21             # 880 J/kg·C × 0.000238846 = 0.21
    }
}

#constants
LOOP_CS_AREA = 0.010058354
LOOP_OD = 1.25 #in
BH_DEPTH = 650 #ft
OVERBURDEN_DEPTH = 10 #ft
SAMPLE_INTERVAL = 2 #min
FLOW_START_TRIGGER_POINT = 15
AK_EIGHTEEN = 250

SIG_DIGS = 8

#heat capacity of water lookup (Cp value)
CP_TABLE = [
    (0.01, 4.2199),
    (1, 4.217457558),
    (2, 4.215015115),
    (3, 4.212572673),
    (4, 4.21013023),
    (5, 4.207687788),
    (6, 4.205245345),
    (7, 4.202802903),
    (8, 4.20036046),
    (9, 4.197918018),
    (10, 4.1955),
    (11, 4.19439),
    (12, 4.19328),
    (13, 4.19217),
    (14, 4.19106),
    (15, 4.18995),
    (16, 4.18884),
    (17, 4.18773),
    (18, 4.18662),
    (19, 4.18551),
    (20, 4.1844),
    (21, 4.18384),
    (22, 4.18328),
    (23, 4.18272),
    (24, 4.18216),
    (25, 4.1816),
    (26, 4.1813),
    (27, 4.181),
    (28, 4.1807),
    (29, 4.1804),
    (30, 4.1801),
    (31, 4.18005),
    (32, 4.18),
    (33, 4.17995),
    (34, 4.1799),
    (35, 4.17985),
    (36, 4.1798),
    (37, 4.17975),
    (38, 4.1797),
    (39, 4.17965),
    (40, 4.1796),
    (41, 4.17979),
    (42, 4.17998),
    (43, 4.18017),
    (44, 4.18036),
    (45, 4.18055),
    (46, 4.18074),
    (47, 4.18093),
    (48, 4.18112),
    (49, 4.18131),
    (50, 4.1815),
]

def get_cp(temp_c):
    temps = [row[0] for row in CP_TABLE]
    cps = [row[1] for row in CP_TABLE]
    return float(np.interp(temp_c, temps, cps))

#density of water lookup
DENSITY_TABLE = [
    (0.01, 999.85),
    (1, 999.9),
    (2, 999.9233333),
    (3, 999.9466667),
    (4, 999.97),
    (5, 999.925),
    (6, 999.88),
    (7, 999.835),
    (8, 999.79),
    (9, 999.745),
    (10, 999.7),
    (11, 999.58),
    (12, 999.46),
    (13, 999.34),
    (14, 999.22),
    (15, 999.1),
    (16, 998.922),
    (17, 998.744),
    (18, 998.566),
    (19, 998.388),
    (20, 998.21),
    (21, 997.978),
    (22, 997.746),
    (23, 997.514),
    (24, 997.282),
    (25, 997.05),
    (26, 996.77),
    (27, 996.49),
    (28, 996.21),
    (29, 995.93),
    (30, 995.65),
    (31, 995.326),
    (32, 995.002),
    (33, 994.678),
    (34, 994.354),
    (35, 994.03),
    (36, 993.668),
    (37, 993.306),
    (38, 992.944),
    (39, 992.582),
    (40, 992.22),
    (41, 991.818),
    (42, 991.416),
    (43, 991.014),
    (44, 990.612),
    (45, 990.21),
    (46, 989.776),
    (47, 989.342),
    (48, 988.908),
    (49, 988.474),
    (50, 988.04),
]

def get_density(temp_c):
    temps = [row[0] for row in DENSITY_TABLE]
    densities = [row[1] for row in DENSITY_TABLE]
    return float(np.interp(temp_c, temps, densities))

# Rock Formation Thermal Properties Database
# Units:density_lbft3 = lbs/ft³, tc_btu = BTU/hr·ft·F, cp_btu = BTU/lbm·F

def get_formation(name):
    """Get thermal properties for a rock formation by name."""
    if name not in ROCK_FORMATIONS:
        raise ValueError(f"Formation '{name}' not found. Available: {list(ROCK_FORMATIONS.keys())}")
    return ROCK_FORMATIONS[name]


SDR11_PIPE_TABLE = {
    0.75: 0.003996,
    1.0:  0.006303,
    1.25: 0.010058354,
    1.5:  0.013211,
    2.0:  0.020587,
    3.0:  0.044688,
    4.0:  0.073854,
    6.0:  0.160150,
    8.0:  0.271574,
}

def get_loop_cs_area(nominal_size):
    if nominal_size not in SDR11_PIPE_TABLE:
        raise ValueError(f"Nominal size {nominal_size} not found.")
    return SDR11_PIPE_TABLE[nominal_size]