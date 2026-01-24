import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time as tm
import random  

from datetime import time
from modules import loader, calculator
from modules import tariff_utils as t_utils

# ==========================================
# 1. SETUP HALAMAN & SESSION STATE
# ==========================================
st.set_page_config(page_title="CER Simulation Data Generator", layout="wide")

if 'hasil_simulasi' not in st.session_state:
    st.session_state['hasil_simulasi'] = None
    st.session_state['used_params'] = {} 
    st.session_state['info_simulasi'] = ""

st.title("CER Simulation Data Generator")
st.markdown("Set parameter region and period to start generate data")
st.divider()

col_dp, col_spec = st.columns([1, 1], gap="medium")

# ==========================================
# 2. KOLOM KIRI: DATA & TARIFF
# ==========================================
with col_dp:
    st.subheader("📁 Data Parameter")
    
    col_location, col_tariff = st.columns([1, 1.4])

    # --- Bagian A: Lokasi & Waktu ---
    with col_location:
        list_lokasi = loader.get_list_lokasi()
        if not list_lokasi:
            st.error("Database empty! Run script 'setup_database_v6.py first!")
            st.stop()
            
        st.info("🌍 Location")
        l1 , l2 = st.columns(2)

        selected_loc = l1.selectbox("1. Choose Region", list_lokasi)
        list_titik = loader.get_list_titik(selected_loc)
        selected_point = l2.selectbox("2. Choose Point", list_titik)
        available_years = loader.get_available_years(selected_loc, selected_point)
        
        st.info("🕒 Duration")
        if available_years:
            min_year, max_year = min(available_years), max(available_years)
            y1, y2 = st.columns(2)
            start_y = y1.selectbox("Start Date", available_years, index=0)
            valid_end_years = [y for y in available_years if y >= start_y]
            end_y = y2.selectbox("End Date", valid_end_years, index=len(valid_end_years)-1)
        else:
            st.warning("There is no data on this point!")
            st.stop()

    # --- Bagian B: Tarif (VPP, Export, Import) ---
    with col_tariff:
        st.info("⚙️ VPP Setting")
        vpp_price = st.number_input("Dispatch Price Threshold (AUD/MWh)", 0, 2000, 800, 10)

        st.info("💲 Tariff")

        st.text("Export")
        exp_price = st.number_input("Flat Price (AUD/kWh)", 0.0, 1.0, 0.08, 0.01, key="exp_tariff")

        st.text("Import")
        use_ToU = st.toggle("Flat / Time-Of-Use (ToU)", key="chk_tou")
        
        # Inisialisasi Session State Tariff (dari modul tariff_utils)
        t_utils.initialize_session_state()
        
        hourly_prices = [0] * 24

        if use_ToU:
            # --- INPUT TIME OF USE ---
            st.markdown("Peak Time")
            c1, c2, c3 = st.columns([1, 1, 1])
            
            c1.time_input("Start", key="t_p_start", value=st.session_state.t_p_start, on_change=t_utils.sync_peak_start)
            c2.time_input("End", key="t_p_end", value=st.session_state.t_p_end, on_change=t_utils.sync_peak_end)
            p_peak = c3.number_input("Price (AUD/kWh)", 0.0, 2.0, 0.45, 0.01, key="pp")

            st.markdown("Off-Peak")
            c1, c2, c3 = st.columns([1, 1, 1])
            
            c1.time_input("Start", key="t_o_start", value=st.session_state.t_o_start, on_change=t_utils.sync_offpeak_start, label_visibility="collapsed")
            c2.time_input("End", key="t_o_end", value=st.session_state.t_o_end, on_change=t_utils.sync_offpeak_end, label_visibility="collapsed")
            p_offpeak = c3.number_input("Price (AUD/kWh)", 0.0, 2.0, 0.15, 0.01, label_visibility="collapsed", key="po")

            st.markdown("Shoulder Time")
            c1, c2, c3 = st.columns([1, 1, 1])
            
            c1.time_input("Start", key="t_s_start", value=st.session_state.t_s_start, on_change=t_utils.sync_shoulder_start, label_visibility="collapsed")
            c2.time_input("End", key="t_s_end", value=st.session_state.t_s_end, on_change=t_utils.sync_shoulder_end, label_visibility="collapsed")
            p_shoulder = c3.number_input("Price (AUD/kWh)", 0.0, 2.0, 0.25, 0.01, label_visibility="collapsed", key="ps")

            # Generate Array Harga 24 Jam
            hourly_prices = t_utils.generate_hourly_prices(p_peak, p_offpeak, p_shoulder)

        else:
            # --- INPUT FLAT ---
            p_flat = st.number_input("Flat Price (AUD/kWh)", 0.0, 2.0, 0.2, 0.01, key="imp_tariff")
            hourly_prices = [p_flat] * 24

# ==========================================
# 3. KOLOM KANAN: SYSTEM SPEC
# ==========================================
with col_spec:
    st.subheader("⚙️ System Specification")
    
    col_panel, col_battery = st.columns(2)
    with col_panel:
        st.info("☀️ Solar Panel / Photovoltaics")
        
        use_rand_solar = st.toggle("Randomize / Fixed Size", key="chk_solar")
        
        if not use_rand_solar:
            sc1, sc2 = st.columns(2)
            p_solar_min = sc1.number_input("Min (kWp)", 0.0, 1000.0, 4.0, step=0.5)
            p_solar_max = sc2.number_input("Max (kWp)", 0.0, 1000.0, 6.0, step=0.5)
        else:
            p_solar_fix = st.number_input("Capacity (kWp)", 1.0, 100.0, 5.0, 0.5)

        p_temp = st.number_input("Temp Coeff", -0.01, 0.0, -0.004, 0.0001, format="%.4f")
        p_pr = st.number_input("PR (except temperature derated)", 0.5, 1.0, 0.8, 0.01, format="%.2f")
        
    with col_battery:
        st.info("🔋 Battery")
        
        use_rand_bat = st.toggle("Randomize / Fixed Size", key="chk_bat")
        
        if not use_rand_bat:
            bc1, bc2 = st.columns(2)
            p_bat_min = bc1.number_input("Min (kWh)", 0.0, 1000.0, 8.0, step=1.0)
            p_bat_max = bc2.number_input("Max (kWh)", 0.0, 1000.0, 12.0, step=1.0)
        else:
            p_bat_fix = st.number_input("Capacity (kWh)", 1.0, 200.0, 10.0, 1.0)

        b1, b2 = st.columns(2)
        p_charger_pwr = b1.number_input("(-) Charge (kW)", 0, 10, 5, 1)
        p_discharger_pwr = b2.number_input("(+) Discharge (kW)", 0, 10, 5, 1)
        p_eff = st.number_input("Round-Trip Efficiency (%)", 50, 100, 95) / 100
        p_soc = st.slider("Initial SoC (%)", 0, 100, 50) / 100
        range_soc = st.slider("SoC Constraint (%)", min_value=0, max_value=100, value=(10, 90))
        p_min_soc = range_soc[0] / 100
        p_max_soc = range_soc[1] / 100              

st.markdown("---")
btn_run = st.button("Process Parameter and Generate Data", type="primary", use_container_width=True)

# ==========================================
# 4. EKSEKUSI SIMULASI (LOGIC)
# ==========================================
if btn_run:
    # A. Tentukan Kapasitas Fisik (Random/Fixed)
    if not use_rand_solar:
        final_p_solar = round(random.uniform(p_solar_min, p_solar_max), 2)
    else:
        final_p_solar = p_solar_fix
        
    if not use_rand_bat:
        final_p_bat = round(random.uniform(p_bat_min, p_bat_max), 2)
    else:
        final_p_bat = p_bat_fix

    # B. Load Data (Merge Cuaca + Harga CSV + Load Profile Random)
    with st.spinner(f"Combine data {selected_loc} ({selected_point}) dari {start_y}-{end_y}..."):
        df_input = loader.load_and_merge_data(selected_loc, selected_point, start_y, end_y)
        tm.sleep(0.5) 
    
    if df_input is not None:
        
        # C. Mapping Harga Import UI ke Dataframe (Override CSV)
        if 'hourly_prices' in locals():
            df_input['hour_index'] = df_input['timestamp'].dt.hour
            df_input['price_import'] = df_input['hour_index'].apply(lambda x: hourly_prices[x])
            df_input.drop(columns=['hour_index'], inplace=True)
            
        # D. Susun Parameter Lengkap untuk Kalkulator
        params = {
            # Fisik
            'solar_capacity_kw': final_p_solar, 
            'temp_coeff': p_temp,
            'pr': p_pr,
            'battery_capacity_kwh': final_p_bat, 
            'battery_efficiency': p_eff,
            'battery_initial_soc': p_soc,
            'max_charge_kw': p_charger_pwr,
            'max_discharge_kw': p_discharger_pwr,
            'soc_min_pct': p_min_soc,
            'soc_max_pct': p_max_soc,
            
            # Ekonomi (VPP & Export)
            'dispatch_price_threshold': vpp_price, 
            'export_tariff': exp_price,
            
            # Jadwal Waktu (PENTING untuk logika Baterai Baseline)
            't_offpeak_start': st.session_state.t_o_start,
            't_offpeak_end': st.session_state.t_o_end,
            't_peak_start': st.session_state.t_p_start,
            't_peak_end': st.session_state.t_p_end
        }
        
        # E. Jalankan Kalkulasi
        with st.spinner("Calculate Energy Flow..."):
            df_result = calculator.run_simulation(df_input, params)
        
        # Simpan Hasil ke Session State
        st.session_state['hasil_simulasi'] = df_result
        st.session_state['info_simulasi'] = f"{selected_loc}_{selected_point}_{start_y}-{end_y}"
        
        # --- REKAM SNAPSHOT TARIF UNTUK DISPLAY ---
        tariff_snapshot = {
            'is_tou': use_ToU,
            'export_price': exp_price
        }
        
        if use_ToU:
            # Rekam Detail ToU
            tariff_snapshot.update({
                'peak_price': p_peak,
                'peak_start': st.session_state.t_p_start.strftime("%H:%M"),
                'peak_end': st.session_state.t_p_end.strftime("%H:%M"),
                
                'offpeak_price': p_offpeak,
                'offpeak_start': st.session_state.t_o_start.strftime("%H:%M"),
                'offpeak_end': st.session_state.t_o_end.strftime("%H:%M"),
                
                'shoulder_price': p_shoulder,
                'shoulder_start': st.session_state.t_s_start.strftime("%H:%M"),
                'shoulder_end': st.session_state.t_s_end.strftime("%H:%M"),
            })
        else:
            # Rekam Flat
            tariff_snapshot['import_flat'] = p_flat

        # Simpan Parameter Terpakai
        st.session_state['used_params'] = {
            'solar': final_p_solar, 
            'bat': final_p_bat,
            'tariff_data': tariff_snapshot # <--- Disimpan di sini
        }
        
        st.success("Data Has Been Generated!")
    else:
        st.error("Failed to Generate the Data")

# ==========================================
# 5. VISUALISASI HASIL & DOWNLOAD
# ==========================================
if st.session_state['hasil_simulasi'] is not None:
    
    df_result = st.session_state['hasil_simulasi']
    file_name_info = st.session_state['info_simulasi']
    used_p = st.session_state['used_params']
    t_data = used_p['tariff_data']

    st.divider()
    
    # --- INFO CONFIG (SOLAR & BAT) ---
    st.info(f"✅ **System Configuration:** Solar {used_p['solar']} kWp | Battery {used_p['bat']} kWh")

    # --- INFO TARIFF DETAIL (EXPANDER) ---
    with st.expander("💲 View Applied Tariff Details (Import & Export)", expanded=True):
        tc1, tc2 = st.columns(2)
        
        with tc1:
            st.markdown(f"**Export Tariff:**")
            st.markdown(f"⚡ Flat Rate: **{t_data['export_price']} AUD/kWh**")
            
        with tc2:
            st.markdown(f"**Import Tariff:**")
            if t_data['is_tou']:
                st.markdown("🕒 **Time-of-Use (ToU) Profile:**")
                st.markdown(f"""
                - 🔥 **Peak:** {t_data['peak_price']} AUD <br> &nbsp;&nbsp;&nbsp; *({t_data['peak_start']} - {t_data['peak_end']})*
                - 🌤️ **Shoulder:** {t_data['shoulder_price']} AUD <br> &nbsp;&nbsp;&nbsp; *({t_data['shoulder_start']} - {t_data['shoulder_end']})*
                - 🌑 **Off-Peak:** {t_data['offpeak_price']} AUD <br> &nbsp;&nbsp;&nbsp; *({t_data['offpeak_start']} - {t_data['offpeak_end']})*
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"🟦 Flat Rate: **{t_data['import_flat']} AUD/kWh**")

    # --- DOWNLOAD BUTTON ---
    st.markdown("### 💾 Export Data")
    csv = df_result.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Dataset (CSV)",
        data=csv,
        file_name=f"Data_{file_name_info}.csv",
        mime="text/csv",
        key='download-csv' 
    )

    # --- METRICS ---
    total_days = len(df_result) / 288
    st.subheader(f"📊 Analysis Result: {file_name_info} ({int(total_days)} Days)")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Solar Output", f"{df_result['solar_output_kw'].sum()*(5/60):,.0f} kWh")
    m2.metric("Load", f"{df_result['load_profile'].sum()*(5/60):,.0f} kWh") # Menggunakan kolom baru 'load_profile'
    m3.metric("Grid Import", f"{df_result['grid_import_kwh'].sum():,.0f} kWh", delta_color="inverse")
      
    # --- CHARTS ---
    st.markdown("### 📈 Visualization (Sample for first 5-days)")
    subset = df_result.head(288 * 5)
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    
    # Grafik 1: Power Balance
    ax1.set_title("Solar Output vs Load (kW)")
    ax1.plot(subset['timestamp'], subset['solar_output_kw'], color='green', label='Solar', alpha=0.8)
    ax1.plot(subset['timestamp'], subset['load_profile'], color='red', linestyle='--', label='Load', alpha=0.8)
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)
    
    # Grafik 2: Battery SoC
    ax2.set_title("State of Charge (%)")
    ax2.fill_between(subset['timestamp'], subset['battery_soc_pct'], color='blue', alpha=0.1)
    ax2.plot(subset['timestamp'], subset['battery_soc_pct'], color='blue')
    ax2.set_ylim(0, 105)
    ax2.grid(True, alpha=0.3)
    
    # Grafik 3: Grid Interaction
    ax3.set_title("Grid Interaction (kW) - Positive: Import, Negative: Export")
    ax3.bar(subset['timestamp'], subset['grid_net_kwh'], color='black', width=0.01)
    ax3.grid(True, alpha=0.3)
    
    st.pyplot(fig)