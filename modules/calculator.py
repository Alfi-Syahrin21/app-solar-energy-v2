import pandas as pd

def run_simulation(df, params):
    """
    Fungsi inti untuk menghitung simulasi energi.
    df: DataFrame yang sudah ada kolom irradiance, suhu, beban, harga.
    params: Dictionary berisi parameter (kapasitas solar, batre, dll).
    """
    
    solar_cap = params['solar_capacity_kw']
    temp_coeff = params['temp_coeff']
    bat_cap = params['battery_capacity_kwh']
    bat_eff = params['battery_efficiency']
    bat_soc = params['battery_initial_soc']
    
    solar_output = []
    battery_soc_list = []
    grid_import_list = []
    grid_cost_list = []
    
    current_bat_kwh = bat_cap * bat_soc
    
    for index, row in df.iterrows():
        irr = row['irradiance']
        temp = row['suhu']
        
        temp_factor = 1 + (temp_coeff * (temp - 25))
        
        solar_kw = solar_cap * (irr / 1000) * temp_factor
        solar_kw = max(0, solar_kw)
        solar_output.append(solar_kw)
        
        load_kw = row['beban_rumah_kw']
        time_factor = 5/60 
        
        energy_solar_kwh = solar_kw * time_factor
        energy_load_kwh = load_kw * time_factor
        
        net_energy = energy_solar_kwh - energy_load_kwh
        grid_import = 0
        
        if net_energy > 0: 
            energy_store = net_energy * bat_eff
            space = bat_cap - current_bat_kwh
            
            if energy_store <= space:
                current_bat_kwh += energy_store
            else:
                current_bat_kwh = bat_cap
                
        else: 
            energy_need = abs(net_energy)
            if current_bat_kwh >= energy_need:
                current_bat_kwh -= energy_need
            else:
                shortfall = energy_need - current_bat_kwh
                current_bat_kwh = 0
                grid_import = shortfall
        
        battery_soc_list.append(current_bat_kwh)
        grid_import_list.append(grid_import)
        grid_cost_list.append(grid_import * row['harga_listrik'])
        
    df['solar_output_kw'] = solar_output
    df['battery_level_kwh'] = battery_soc_list
    df['battery_percentage'] = (df['battery_level_kwh'] / bat_cap) * 100
    df['grid_import_kwh'] = grid_import_list
    df['biaya_listrik_rp'] = grid_cost_list
    
    return df