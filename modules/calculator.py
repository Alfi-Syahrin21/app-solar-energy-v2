import pandas as pd
import numpy as np

def check_time_window(current_time, start_time, end_time):
    """
    Cek apakah waktu sekarang berada dalam rentang start-end.
    Menghandle kasus lintas hari (misal 23:00 s/d 07:00).
    """
    if start_time < end_time:
        return start_time <= current_time < end_time
    else: # Lintas tengah malam
        return current_time >= start_time or current_time < end_time

def run_simulation(df, params):
    """
    Menghitung simulasi aliran energi (Solar, Baterai, Grid)
    berdasarkan strategi VPP dan Baseline Time-Schedule.
    """
    
    # --- 1. PRE-CALCULATION (SOLAR) ---
    # Hitung Solar Output (Fisika)
    # Rumus: Capacity * (Irr/1000) * (1 + Coeff*(Temp - 25)) * PR
    # Kita batasi min 0 agar tidak negatif
    temp_factor = 1 + (params['temp_coeff'] * (df['temperature'] - 25))
    df['solar_output_kw'] = params['solar_capacity_kw'] * (df['irradiance'] / 1000) * temp_factor * params['pr']
    df['solar_output_kw'] = df['solar_output_kw'].clip(lower=0)
    
    # --- 2. PERSIAPAN LOOP BATERAI ---
    # Ambil parameter baterai
    bat_cap = params['battery_capacity_kwh']
    soc_min_kwh = bat_cap * params['soc_min_pct']
    soc_max_kwh = bat_cap * params['soc_max_pct']
    # Effisiensi One-Way (Akar dari Round-Trip)
    # Asumsi: Eff Charge = Eff Discharge = sqrt(RoundTrip)
    eff_one_way = params['battery_efficiency'] ** 0.5 
    
    max_charge_kw = params['max_charge_kw']
    max_discharge_kw = params['max_discharge_kw']
    
    # Parameter VPP & Schedule
    vpp_threshold = params['dispatch_price_threshold']
    
    # List penampung hasil loop
    bat_power_list = [] # (+) Discharge, (-) Charge
    soc_list = []
    grid_list = []
    
    # SoC Awal
    current_soc = bat_cap * params['battery_initial_soc']
    
    # Time delta (dalam jam), asumsi data 5 menit
    dt = 5 / 60 

    # --- 3. CORE LOOP (SIMULASI PER BARIS) ---
    # Kita convert dataframe ke list of dict biar iterasi lebih cepat dari itertuples
    records = df.to_dict('records')
    
    for row in records:
        
        # Ambil variable saat ini
        load = row['load_profile']
        solar = row['solar_output_kw']
        price = row['price_import']
        cur_time = row['timestamp'].time()
        
        # Hitung Net Load Asli (Load - Solar)
        # Positif = Butuh daya (Defisit), Negatif = Surplus Solar
        net_load_pure = load - solar
        
        # Inisialisasi Keputusan Baterai (kW AC Side)
        # Target Power: (+) mau discharge, (-) mau charge
        target_bat_power = 0 
        
        # --- A. LOGIC DECISION TREE ---
        
        # 1. CEK VPP DISPATCH (Prioritas Tertinggi)
        if price > vpp_threshold:
            # Mode: FORCE DISCHARGE (Jual sekuat tenaga)
            target_bat_power = max_discharge_kw
            
        else:
            # Masuk ke BASELINE STRATEGY (Cek Jam)
            
            # Cek Time Windows
            is_offpeak = check_time_window(cur_time, params['t_offpeak_start'], params['t_offpeak_end'])
            is_peak = check_time_window(cur_time, params['t_peak_start'], params['t_peak_end'])
            # Jika bukan offpeak dan bukan peak, maka shoulder
            
            if is_offpeak:
                # Mode: FORCE CHARGE (Isi baterai dari Grid/Solar buat nanti)
                # Kita set target charge maksimum
                target_bat_power = -max_charge_kw 
                
            elif is_peak:
                # Mode: PEAK SHAVING / SELF-CONSUMPTION
                # Hanya discharge jika Load > Solar (Defisit)
                # Kita coba discharge sebesar kekurangan beban
                if net_load_pure > 0:
                    target_bat_power = net_load_pure # Coba tutupi beban
                else:
                    target_bat_power = 0 # Kalau solar sudah cukup, baterai diam (atau bisa charge dikit, tp di peak biasanya diam)
            
            else: # SHOULDER
                # Mode: STORE EXCESS SOLAR
                # Hanya charge jika Solar > Load (Surplus)
                if net_load_pure < 0:
                    # Surplus solar masuk baterai
                    # net_load_pure nilainya negatif, jadi target_bat_power otomatis negatif (charge)
                    target_bat_power = net_load_pure 
                else:
                    # Jika mendung di siang hari, apakah mau discharge?
                    # Opsional: Bisa support load, atau diam hemat energi.
                    # Kita set support load saja
                    target_bat_power = net_load_pure

        # --- B. BATTERY CONSTRAINTS (BATAS FISIK) ---
        
        # 1. Batasi dengan Rating Inverter (kW)
        # Clip antara Max Charge (-) dan Max Discharge (+)
        target_bat_power = max(-max_charge_kw, min(max_discharge_kw, target_bat_power))
        
        # 2. Batasi dengan Kapasitas Energi (kWh) -> Mencegah Overcharge/Deep Discharge
        
        # Hitung energi yang akan dipindahkan dalam dt ini (kwh raw)
        # Ingat effisiensi:
        # Kalau Charge (-): Masuk ke SoC = Power * Eff * dt
        # Kalau Discharge (+): Keluar dari SoC = Power / Eff * dt
        
        if target_bat_power < 0: # CHARGING
            # Energi yang BISA masuk sampai penuh
            max_energy_in = soc_max_kwh - current_soc
            # Konversi max_energy_in ke Power AC yang dibutuhkan (dibagi Eff karena losses)
            # SoC_delta = P_ac * Eff * dt  => P_ac_max = SoC_delta / (Eff * dt)
            max_p_charge_by_soc = - (max_energy_in / (eff_one_way * dt))
            
            # Koreksi target (ambil yang paling mendekati 0 / paling tidak negatif)
            real_bat_power = max(target_bat_power, max_p_charge_by_soc)
            
            # Update SoC
            energy_change = real_bat_power * eff_one_way * dt # Bernilai negatif (tambah SoC?)
            # Wait, logic saya terbalik. 
            # Jika P negatif (Charge), SoC harus NAIK.
            # Jadi SoC New = SoC Old - (P * Eff * dt) -> Minus ketemu minus jadi plus.
            current_soc = current_soc - energy_change
            
        else: # DISCHARGING (atau 0)
            # Energi yang BISA keluar sampai kosong
            max_energy_out = current_soc - soc_min_kwh
            # Konversi ke Power AC
            # SoC_delta = P_ac / Eff * dt => P_ac_max = SoC_delta * Eff / dt
            max_p_discharge_by_soc = (max_energy_out * eff_one_way) / dt
            
            # Koreksi target (ambil yang paling kecil positif)
            real_bat_power = min(target_bat_power, max_p_discharge_by_soc)
            
            # Update SoC
            energy_change = (real_bat_power / eff_one_way) * dt # Bernilai positif
            current_soc = current_soc - energy_change
            
        # Safety rounding SoC
        current_soc = max(0, min(bat_cap, current_soc))
        
        # --- C. FINAL GRID CALCULATION ---
        # Rumus: Grid = Load - Solar - Battery_AC
        # Jika Bat Discharge (+): Grid = Load - Solar - (+) = Berkurang (Bagus)
        # Jika Bat Charge (-): Grid = Load - Solar - (-) = Bertambah (Impor naik)
        grid_kwh = (load - solar - real_bat_power) * dt
        
        # Simpan hasil
        bat_power_list.append(real_bat_power)
        soc_list.append(current_soc)
        grid_list.append(grid_kwh)
        
    # --- 4. WRAPPING OUTPUT ---
    df['battery_power_kw'] = bat_power_list
    df['battery_soc_kwh'] = soc_list
    df['battery_soc_pct'] = (df['battery_soc_kwh'] / bat_cap) * 100
    df['grid_net_kwh'] = grid_list # Ini Net (Bisa positif impor, negatif ekspor)
    
    # Pisahkan Impor dan Ekspor untuk visualisasi
    df['grid_import_kwh'] = df['grid_net_kwh'].apply(lambda x: x if x > 0 else 0)
    df['grid_export_kwh'] = df['grid_net_kwh'].apply(lambda x: -x if x < 0 else 0)
    
    return df