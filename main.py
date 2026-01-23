import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time
import random  

from modules import loader, calculator

st.set_page_config(page_title="CER Simulation Data Generator", layout="wide")

if 'hasil_simulasi' not in st.session_state:
    st.session_state['hasil_simulasi'] = None
    st.session_state['used_params'] = {} 

st.title("CER Simulation Data Generator")
st.markdown("Set parameter region and period to start generate data")
st.divider()

col_db, col_spec = st.columns([1, 1.5], gap="large")

with col_db:
    st.subheader("📁 Data Parameter")
    
    list_lokasi = loader.get_list_lokasi()
    if not list_lokasi:
        st.error("Database empty! Run script 'setup_database_v2.py first!")
        st.stop()
        
    st.info("🌍 Location")
    r1 , r2 = st.columns(2)

    selected_loc = r1.selectbox("1. Choose Region", list_lokasi)
    list_titik = loader.get_list_titik(selected_loc)
    selected_point = r2.selectbox("2. Choose Point", list_titik)
    available_years = loader.get_available_years(selected_loc, selected_point)
    
    st.info("🕒 Duration")
    if available_years:
        min_year, max_year = min(available_years), max(available_years)
        c1, c2 = st.columns(2)
        start_y = c1.selectbox("Start Date", available_years, index=0)
        valid_end_years = [y for y in available_years if y >= start_y]
        end_y = c2.selectbox("End Date", valid_end_years, index=len(valid_end_years)-1)
    else:
        st.warning("There is no data on this point!")
        st.stop()
    


with col_spec:
    st.subheader("⚙️ System Specification")
    
    s1, s2 = st.columns(2)
    with s1:
        st.info("☀️ Solar Panel / Photovoltaics")
        
        use_rand_solar = st.checkbox("Randomize Capacity (Solar)", key="chk_solar")
        
        if use_rand_solar:
            sc1, sc2 = st.columns(2)
            p_solar_min = sc1.number_input("Min (kWp)", 0.0, 1000.0, 4.0, step=0.5)
            p_solar_max = sc2.number_input("Max (kWp)", 0.0, 1000.0, 6.0, step=0.5)
        else:
            p_solar_fix = st.number_input("Capacity (kWp)", 1.0, 100.0, 5.0, 0.5)

        p_temp = st.number_input("Temp Coeff", -0.01, 0.0, -0.004, 0.0001, format="%.4f")
        p_pr = st.number_input("PR (except temperature derated)", 0.5, 1.0, 0.8, 0.01, format="%.2f")
        
    with s2:
        st.warning("🔋 Battery")
        
        use_rand_bat = st.checkbox("Randomize Capacity (Batt)", key="chk_bat")
        
        if use_rand_bat:
            bc1, bc2 = st.columns(2)
            p_bat_min = bc1.number_input("Min (kWh)", 0.0, 1000.0, 8.0, step=1.0)
            p_bat_max = bc2.number_input("Max (kWh)", 0.0, 1000.0, 12.0, step=1.0)
        else:
            p_bat_fix = st.number_input("Capacity (kWh)", 1.0, 200.0, 10.0, 1.0)

        b1, b2 = st.columns(2)
        p_chgr_pwr = b1.number_input("(-) Charge Power (kW)", 0, 10, 5, 1)
        p_dchgr_pwr = b2.number_input("(+) Discharge Power (kW)", 0, 10, 5, 1)
        p_eff = st.number_input("Efficiency (%)", 50, 100, 95) / 100
        p_soc = st.slider("Initial SoC (%)", 0, 100, 50) / 100         

st.markdown("---")
btn_run = st.button("Process Parameter and Generate Data", type="primary", use_container_width=True)

if btn_run:
    if use_rand_solar:
        final_p_solar = round(random.uniform(p_solar_min, p_solar_max), 2)
    else:
        final_p_solar = p_solar_fix
        
    if use_rand_bat:
        final_p_bat = round(random.uniform(p_bat_min, p_bat_max), 2)
    else:
        final_p_bat = p_bat_fix

    with st.spinner(f"Combine data {selected_loc} ({selected_point}) dari {start_y}-{end_y}..."):
        df_input = loader.load_and_merge_data(selected_loc, selected_point, start_y, end_y)
        time.sleep(0.5) 
    
    if df_input is not None:
        params = {
            'solar_capacity_kw': final_p_solar, 
            'temp_coeff': p_temp,
            'battery_capacity_kwh': final_p_bat, 
            'battery_efficiency': p_eff,
            'battery_initial_soc': p_soc
        }
        
        with st.spinner("Calculate Energy Flow..."):
            df_result = calculator.run_simulation(df_input, params)
        
        st.session_state['hasil_simulasi'] = df_result
        st.session_state['info_simulasi'] = f"{selected_loc}_{selected_point}_{start_y}-{end_y}"
        st.session_state['used_params'] = {'solar': final_p_solar, 'bat': final_p_bat}
        
        st.success("Data Has Been Generated!")
    else:
        st.error("Failed to Generate the Data")


if st.session_state['hasil_simulasi'] is not None:
    
    df_result = st.session_state['hasil_simulasi']
    file_name_info = st.session_state['info_simulasi']
    used_p = st.session_state['used_params']

    st.divider()
    
    st.info(f"✅ Simulation generated using: **Solar Capacity: {used_p['solar']} kWp** | **Battery Capacity: {used_p['bat']} kWh**")

    
    st.markdown("### 💾 Export Data")
    csv = df_result.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Dataset (CSV)",
        data=csv,
        file_name=f"Data_{file_name_info}.csv",
        mime="text/csv",
        key='download-csv' 
    )

    total_days = len(df_result) / 288
    st.subheader(f"📊 Analysis Result: {file_name_info} ({int(total_days)} Days)")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Solar Ouput", f"{df_result['solar_output_kw'].sum()*(5/60):,.0f} kWh")
    m2.metric("Load", f"{df_result['beban_rumah_kw'].sum()*(5/60):,.0f} kWh")
    m3.metric("Grid Import", f"{df_result['grid_import_kwh'].sum():,.0f} kWh", delta_color="inverse")
      
    st.markdown("### 📈 Visualization (Sample for first 5-days)")
    subset = df_result.head(288 * 5)
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    
    ax1.set_title("Solar Output vs Load (kW)")
    ax1.plot(subset['timestamp'], subset['solar_output_kw'], color='green', label='Solar', alpha=0.8)
    ax1.plot(subset['timestamp'], subset['beban_rumah_kw'], color='red', linestyle='--', label='Beban', alpha=0.8)
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)
    
    ax2.set_title("State of Charge (%)")
    ax2.fill_between(subset['timestamp'], subset['battery_percentage'], color='blue', alpha=0.1)
    ax2.plot(subset['timestamp'], subset['battery_percentage'], color='blue')
    ax2.set_ylim(0, 105)
    ax2.grid(True, alpha=0.3)
    
    ax3.set_title("Grid Import (kWh)")
    ax3.bar(subset['timestamp'], subset['grid_import_kwh'], color='black', width=0.01)
    ax3.grid(True, alpha=0.3)
    
    st.pyplot(fig)
    