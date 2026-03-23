import numpy as np

from services.licor_api import fetch_devices, fetch_sensor_data
from config import (SAMPLE_INTERVAL, SIG_DIGS,
                    BH_DEPTH, LOOP_OD, AK_EIGHTEEN, OVERBURDEN_DEPTH,
                    DEVICE_SERIAL, SENSOR_MAP, get_cp, get_density, get_formation, get_loop_cs_area
)


def round_sig(value):
    return float(f"{float(value):.{SIG_DIGS}g}")

#gets data array for one sensor [timestamp, data]
def get_records(data, sensor_name, device_serial=DEVICE_SERIAL):
    serial = SENSOR_MAP[sensor_name]
    if device_serial not in data or serial not in data[device_serial]:
        return []

    sensor_data = data[device_serial][serial]
    if 'sensors' not in sensor_data:
        return []
    try:
        return data[device_serial][serial]['sensors'][0]['data'][0]['records']
    except (KeyError, IndexError, TypeError):
        return []


def resolve_device_serial(data, required_sensors):
    required_serials = {SENSOR_MAP[name] for name in required_sensors}

    if DEVICE_SERIAL in data and required_serials.issubset(set(data[DEVICE_SERIAL].keys())):
        return DEVICE_SERIAL

    for device_serial, sensors in data.items():
        if required_serials.issubset(set(sensors.keys())):
            return device_serial

    return None

#converts timestamps to elapsed time in seconds
def get_elapsed_seconds(records):
    if not records:
        return []
    first_timestamp = records[0][0]
    return [(r[0] - first_timestamp)/3600000 for r in records]
            
#calculations
def process(calculation_type, data_method, csv_file_path, ROCK_FORMATION_DISTRIBUTION, START_DATE, END_DATE):
    
    if data_method == 'CSV':
        from csv_parser import parse_licor_csv
        data = parse_licor_csv(csv_file_path)
    elif data_method == 'API':
        devices = fetch_devices()
        data = fetch_sensor_data(devices, START_DATE, END_DATE)
    else:
        return 'invalid calculation method?'
    
    
    '''========== VARIABLES AND UNITS ============================================================================================'''
    
    
    #raw data
    required_sensors = [
        'TempIn1',
        'TempIn2',
        'TempOut1',
        'TempOut2',
        'ScaledVoltage',
        'ScaledCurrent',
        'ScaledSeries',
    ]
    selected_device_serial = resolve_device_serial(data, required_sensors)
    if not selected_device_serial:
        return (
            "Not enough data for the selected date range. Could not find a device containing all required sensors: "
            + ", ".join(required_sensors)
            + "."
        )

    sensor_records = {name: get_records(data, name, selected_device_serial) for name in required_sensors}
    missing_sensors = [name for name, records in sensor_records.items() if not records]
    if missing_sensors:
        return (
            "Not enough data for the selected date range. Missing sensor data for: "
            + ", ".join(missing_sensors)
            + "."
        )

    sensor_lengths = {name: len(records) for name, records in sensor_records.items()}
    if len(set(sensor_lengths.values())) != 1:
        return (
            "Not enough data for the selected date range. Sensor record counts are inconsistent: "
            + ", ".join([f"{name}={count}" for name, count in sensor_lengths.items()])
            + "."
        )

    t1in_raw_data = sensor_records['TempIn1']                  #°C
    t2in_raw_data = sensor_records['TempIn2']                  #°C
    t1out_raw_data = sensor_records['TempOut1']                #°C
    t2out_raw_data = sensor_records['TempOut2']                #°C
    voltage_raw_data = sensor_records['ScaledVoltage']
    current_raw_data = sensor_records['ScaledCurrent']         #A
    flow_meter_raw_data = sensor_records['ScaledSeries']       #LPM
    
    #timestamps
    elapsed_times = get_elapsed_seconds(t1in_raw_data) #hours
    
    #data calculations - lists of (time, value) tuples and their units 
    avg_fluid_temp_records = []   # °C
    dT_dlnt = 0                   # °C (dimensionless slope)
    slope = 0                     # same as dT_dlnt
    circ_time = 0                 # hours
    flow_start_idx = 0            # index    
    
    undist_gpm_flow_records = []        #GPM
    undist_tin1_records = []            #°C
    undist_tin2_records = []            #°C
    avg_undist_grnd_temp_records = []   #°C
    average_undist_grnd_temp = 0       #°C
    
    theo_power_records = []      #kW
    metered_power_records = []   #kW
    average_metered_power = 0    #kW
    average_theo_power = 0       #kW
    metered_k = 0                # W/m·K
    theo_k = 0                   # W/m·K
    
    metered_borehole_resistance_records = []   #hr·ft·F/BTU
    theo_borehole_resistance_records = []      #hr·ft·F/BTU
    average_metered_borehole_resistance = 0    #hr·ft·F/BTU
    average_theo_borehole_resistance = 0       #hr·ft·F/BTU
    
    bh_radius = 0     #meters
    bh_diameter = 0   #inches
    bh_info = []      #list of tuples
    
    weighted_avg_capacity = 0   # BTU/lbm·F
    weighted_avg_density = 0    # lbs/ft³
    weighted_avg_tc = 0         # BTU/hr·ft·F
    
    estimated_diffusivity = 0   # ft^2/day
    
    theo_weighted_avg_calc_diff = 0      # m²/s
    metered_weighted_avg_calc_diff = 0   # m²/s
    gld_weighted_avg_calc_diff = 0       # m²/s
    
    
    '''========== AVERAGE TEMPERATURE ============================================================================================'''
    
    
    #average fluid temperatures
    for i, t in enumerate(elapsed_times):
        tin_avg = (t1in_raw_data[i][1] + t2in_raw_data[i][1])/2
        tout_avg = (t1out_raw_data[i][1] + t2out_raw_data[i][1])/2
        avg = (tin_avg + tout_avg)/2
        avg_fluid_temp_records.append((t, avg))


    '''========= CONDUCTIVITITY =================================================================================================='''


    #conductivity calculation
    times = [t for (t, avg) in avg_fluid_temp_records if t>= 12 and t <= 40]
    temps = [avg for (t, avg) in avg_fluid_temp_records if t>= 12 and t <= 40]
    
    if len(times) < 2:
        return "Not enough data in the selected date range to compute conductivity (requires at least two points between 12 and 40 hours)."

    ln_times = np.log(times)
    slope, intercept = np.polyfit(ln_times, temps, 1)
    dT_dlnt = slope
    #print(f"m (⁰C) (From 12-40hr Data): {dT_dlnt:.{SIG_DIGS}g}")
    
    
    '''========= UNDISTURBED GROUND TEMPERATURE =================================================================================='''
    
    
    #undisturbed ground temperature calculations
    for i, t in enumerate(elapsed_times):
        undist_gpm_flow_records.append((t, flow_meter_raw_data[i][1]/3.7854))
        
    undist_gpm_flow_filtered = [(r[0], r[1]) for r in undist_gpm_flow_records if r[1] > 3.96 and r[0] <= 12]
    if not undist_gpm_flow_filtered:
        return "Not enough flow data in the selected date range to compute undisturbed ground temperature."

    circ_time = get_loop_cs_area(LOOP_OD)*BH_DEPTH*7.48052*2/(np.median([r[1] for r in undist_gpm_flow_filtered]))
    
    flow_start_idx = next(i for i, r in enumerate(flow_meter_raw_data) if r[1] > 15)
    
    for i in range(0, 1 + flow_start_idx + round(circ_time/float (SAMPLE_INTERVAL))):
        undist_tin1_records.append((elapsed_times[i], t1in_raw_data[i][1]))
        undist_tin2_records.append((elapsed_times[i], t2in_raw_data[i][1])) 
        avg_undist_grnd_temp_records.append((undist_tin1_records[i][1]+undist_tin2_records[i][1])/2)

    average_undist_grnd_temp = np.average(avg_undist_grnd_temp_records)
    #print(f"Undisturbed Ground Temperature (⁰C): {average_undist_grnd_temp:.{SIG_DIGS}g}")
    
    
    '''========= POWER ==========================================================================================================='''
    
    
    #metered power calculations
    for i, t in enumerate(elapsed_times):
        pwr = current_raw_data[i][1]*voltage_raw_data[i][1]
        metered_power_records.append((elapsed_times[i], pwr/1000))
        
    average_metered_power = np.average([r for (t, r) in metered_power_records if t >= 12])
    metered_k = 1000*average_metered_power/(4*np.pi*BH_DEPTH*0.3048*slope)/1.7295772056
    #print(f"average metered power: {metered_k:.{SIG_DIGS}g}")
        
    #theoretical power calculations
    for i, t in enumerate(elapsed_times):
        tin_avg = (t1in_raw_data[i][1] + t2in_raw_data[i][1])/2
        tout_avg = (t1out_raw_data[i][1] + t2out_raw_data[i][1])/2
        
        AF = get_density(round(avg_fluid_temp_records[i][1]))
        P = flow_meter_raw_data[i][1]/1000/60
        AG = AF*P
        AH = get_cp(round(avg_fluid_temp_records[i][1]))
        AI = abs(tout_avg-tin_avg)
        
        AK = AG*AH*AI+(AK_EIGHTEEN/1000)
        theo_power_records.append((t, AK))  
    
    average_theo_power = np.average([r for (t, r) in theo_power_records if t >= 12])
    theo_k = 1000*average_theo_power/(4*np.pi*BH_DEPTH*0.3048*slope)/1.7295772056
    
    #print(f"average theoretical power: {theo_k:.{SIG_DIGS}g}")        
        
        
    '''============ BOREHOLE DIMENSIONS =========================================================================================='''
    
    
    #borehole radius and diameter calculations
    if LOOP_OD == 1.5:
        bh_diameter = 4.25
    else:
        bh_diameter = 3.875
        
    bh_radius = 0.0254*((5.5*OVERBURDEN_DEPTH*0.3048/(BH_DEPTH*0.3048)) + bh_diameter*(BH_DEPTH*0.3048-OVERBURDEN_DEPTH*0.3048)/(BH_DEPTH*0.3048))/2


    '''============ DIFFUSIVITY =================================================================================================='''

    
    bh_info = [] #(weighted_capacity, weighted_density, weighted_tc, calculated_diffusivity)
    
    for name, value in ROCK_FORMATION_DISTRIBUTION.items():
        thickness = value['end_depth'] - value['start_depth']
        
        estimated_capacity = get_formation(name)['cp_btu']
        weighted_capacity = estimated_capacity*thickness/BH_DEPTH
        
        estimated_density = get_formation(name)['density_lbft3']
        weighted_density = estimated_density*thickness/BH_DEPTH
        
        estimated_tc = get_formation(name)['tc_btu']
        weighted_tc = estimated_tc*thickness/BH_DEPTH
        
        bh_info.append((weighted_capacity, weighted_density, weighted_tc))


    #weighted averages for borehole information calculations
    #print("\nBorehole Information: ")
    
    weighted_avg_capacity = np.sum([r[0] for r in bh_info])
    #print(f"    weighted average specific capacity (btu/lbm.F): {weighted_avg_capacity:.{SIG_DIGS}g}")
    
    weighted_avg_density = np.sum([r[1] for r in bh_info])
    #print(f"    weighted average density (lbs/ft^3): {weighted_avg_density}")
    
    weighted_avg_tc = np.sum([r[2] for r in bh_info])
    #print(f"    weighted average thermal conductivity (but/ft.hr.F): {weighted_avg_tc:.{SIG_DIGS}g}")
    
    weighted_avg_estimated_diffusivity = 24*weighted_avg_tc/(weighted_avg_density*weighted_avg_capacity)
    #print(f"    weighted average diffusivity (ft²/day): {weighted_avg_estimated_diffusivity:.{SIG_DIGS}g}")

    #based on rock formation disrtibution 
    estimated_diffusivity = weighted_avg_estimated_diffusivity
    
    #diffusivity calculation for METERED, THEO, GLD using metered_k
    metered_weighted_avg_calc_diff = metered_k*24/weighted_avg_density/weighted_avg_capacity*0.0000010753
    theo_weighted_avg_calc_diff = theo_k*24/weighted_avg_density/weighted_avg_capacity*0.0000010753
    gld_weighted_avg_calc_diff = weighted_avg_tc*24/weighted_avg_density/weighted_avg_capacity*0.0000010753
    
    '''
    print("\n")
    print("="*80)
    print("\nSummmary of Calculated Diffusivity Values")
    print(f"    THEO: weighted average theoretically diffusivity (m^2/s) {theo_weighted_avg_calc_diff:.{SIG_DIGS}g}")
    print(f"    METERED: weighted average metered diffusivity (m^2/s) {metered_weighted_avg_calc_diff:.{SIG_DIGS}g}") 
    print(f"    GLD: weighted average bore hole based diffusivity (m^2/s) {gld_weighted_avg_calc_diff:.{SIG_DIGS}g}")
    print("\n")
    print("="*80)
    '''
    
    '''============ BOREHOLE RESISTANCE =========================================================================================='''
    
    
    #metered
    for i, t in enumerate(elapsed_times): 
        if t == 0:
            metered_borehole_resistance_records.append((t, 0))
        else:
            metered_borehole_resistance_records.append(((t, float(((BH_DEPTH*0.3048*(avg_fluid_temp_records[i][1]-average_undist_grnd_temp))/(1000*average_metered_power)) - (np.log((4*metered_weighted_avg_calc_diff*t*3600)/(bh_radius**2))-0.5772)/(4*np.pi*metered_k*1.7295772056))/0.5781759824)))
    
    average_metered_borehole_resistance = np.average([r[1] for r in metered_borehole_resistance_records if r[0] >= 12])


    #theoretical
    for i, t in enumerate(elapsed_times): 
        if t == 0:
            theo_borehole_resistance_records.append((t, 0))
        else:
            theo_borehole_resistance_records.append(((t, float(((BH_DEPTH*0.3048*(avg_fluid_temp_records[i][1]-average_undist_grnd_temp))/(1000*average_theo_power)) - (np.log((4*theo_weighted_avg_calc_diff*t*3600)/(bh_radius**2))-0.5772)/(4*np.pi*theo_k*1.7295772056))/0.5781759824)))

    average_theo_borehole_resistance = np.average([r[1] for r in theo_borehole_resistance_records if r[0] >= 12])
    
    
    #print(f"METERED: average borehole resistance (hr.ft.F/btu) {average_metered_borehole_resistance:.{SIG_DIGS}g}")
    #print(f"THEO: average borehole resistance (hr.ft.F/btu) {average_theo_borehole_resistance:.{SIG_DIGS}g}")
    
    
    '''============  RETURN STATEMENT ============================================================================================'''

    if calculation_type == 'METERED':
        return {
            'undisturbed_ground_temp': round_sig(average_undist_grnd_temp),
            'calculated_diffusivity': round_sig(metered_weighted_avg_calc_diff),
            'estimated_diffusivity': round_sig(estimated_diffusivity),
            'conductivity': round_sig(slope),
            'borehole_resistance': round_sig(average_metered_borehole_resistance),
        }
    elif calculation_type == 'THEORETICAL':
        return {
        'undisturbed_ground_temp': round_sig(average_undist_grnd_temp),
        'calculated_diffusivity': round_sig(theo_weighted_avg_calc_diff),
        'estimated_diffusivity': round_sig(estimated_diffusivity),
        'conductivity': round_sig(slope),
        'borehole_resistance': round_sig(average_theo_borehole_resistance),
        }
    elif calculation_type == 'GLD':
        return {
        'undisturbed_ground_temp': round_sig(average_undist_grnd_temp),
        'calculated_diffusivity': round_sig(gld_weighted_avg_calc_diff),
        'estimated_diffusivity': round_sig(estimated_diffusivity),
        'conductivity': round_sig(slope),
        'borehole_resistance': round_sig(average_metered_borehole_resistance), #same as metered
        }
    else:
        return("invalid calculation type...")