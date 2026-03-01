import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import time as tm
import random
import json
import calendar

from datetime import time, datetime
from streamlit_gsheets import GSheetsConnection
from modules import loader, calculator
from modules import tariff_utils as t_utils
from modules import visualizer

def time_encoder(obj):
    """Mengubah object datetime.time menjadi string 'HH:MM' untuk JSON"""
    if isinstance(obj, time):
        return obj.strftime("%H:%M")
    raise TypeError("Type not serializable")

def apply_config(uploaded_file):
    """Membaca JSON dan update session_state"""
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            for k, v in data.items():
                if (k.startswith("t_") or k.startswith("time_")) and isinstance(v, str):
                    h, m = map(int, v.split(':'))
                    st.session_state[k] = time(h, m)
                else:
                    st.session_state[k] = v
            st.success("Config Loaded! Rerunning...")
            tm.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error loading config: {e}")

# ==========================================
# FUNGSI MANAJEMEN GOOGLE SHEETS
# ==========================================
TAB_CONFIG = "Config_History"
def get_gsheets_connection():
    """Membuat koneksi ke Google Sheets menggunakan st.connection"""
    return st.connection("gsheets", type=GSheetsConnection)

def load_config_history():
    """Mengambil 10 data konfigurasi terakhir dari Tab 'Config_History'"""
    try:
        conn = get_gsheets_connection()
        # Ganti URL ini dengan URL file Google Sheets 'Simulasi_DB' Anda nanti di file secrets
        df_history = conn.read(worksheet=TAB_CONFIG, ttl=300) 
        
        # Bersihkan data (buang baris kosong jika ada)
        df_history = df_history.dropna(subset=['Config_Name'])
        
        # Ambil 10 baris terakhir, urutkan dari yang terbaru (paling bawah) ke atas
        return df_history.tail(10).iloc[::-1]
    except Exception as e:
        st.error(f"⚠️ Gagal membaca histori config dari Google Sheets: {e}")
        raise e

def save_config_to_sheets(config_name, current_state):
    """Menyimpan state/pengaturan saat ini ke baris baru di Google Sheets"""
    try:
        conn = get_gsheets_connection()
        
        # 1. Baca data yang sudah ada
        df_existing = conn.read(worksheet=TAB_CONFIG, ttl=0)
        df_existing = df_existing.dropna(subset=['Config_Name'])
        
        # 2. Siapkan baris data baru sesuai dengan urutan header (28 Kolom)
        # Pastikan key dari current_state sesuai dengan st.session_state yang kita miliki
        new_row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Config_Name": config_name,
            
            # Waktu & Durasi
            "start_year": current_state.get("date_start", 2020),
            "end_year": current_state.get("date_end", 2020),
            
            # Lokasi & Dataset
            "use_rand_location": current_state.get("chk_loc", True),
            "region_fix": current_state.get("loc_region", ""),
            "point_fix": current_state.get("loc_point", ""),
            "use_rand_load_profile": current_state.get("chk_load", False),
            "load_profile_fix": current_state.get("sel_load_file", ""),
            
            # Solar PV
            "use_rand_solar": current_state.get("chk_solar", False),
            "solar_min": current_state.get("sol_min", 4.0),
            "solar_max": current_state.get("sol_max", 6.0),
            "solar_fix": current_state.get("sol_fix", 5.0),
            "temp_coeff": current_state.get("sol_temp", -0.004),
            "pr": current_state.get("sol_pr", 0.8),
            
            # Battery
            "use_rand_bat": current_state.get("chk_bat", False),
            "bat_min": current_state.get("bat_min", 8.0),
            "bat_max": current_state.get("bat_max", 12.0),
            "bat_fix": current_state.get("bat_fix", 10.0),
            "bat_eff": current_state.get("bat_eff", 0.95),
            "bat_init_soc": current_state.get("bat_soc_init", 0.5),
            "soc_min": current_state.get("bat_soc_range", (10, 90))[0] / 100 if "bat_soc_range" in current_state else 0.1,
            "soc_max": current_state.get("bat_soc_range", (10, 90))[1] / 100 if "bat_soc_range" in current_state else 0.9,
            
            # ToU / Tariff
            "vpp_thresh": current_state.get("vpp_threshold", 800),
            "t_peak_start": time_encoder(current_state.get("t_p_start", time(17,0))),
            "t_peak_end": time_encoder(current_state.get("t_p_end", time(20,0))),
            "t_offpeak_start": time_encoder(current_state.get("t_o_start", time(22,0))),
            "t_offpeak_end": time_encoder(current_state.get("t_o_end", time(6,0)))
        }
        
        # 3. Gabungkan dan Timpa file di Google Sheets
        df_new = pd.DataFrame([new_row])
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
        conn.update(worksheet=TAB_CONFIG, data=df_updated)
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal menyimpan ke Google Sheets: {e}")
        return False
    
def apply_row_to_session(selected_row):
    """Fungsi helper untuk menyuntikkan data sebaris ke dalam memori Streamlit"""
    mapping = {
        "use_rand_location": "chk_loc", "region_fix": "loc_region", "point_fix": "loc_point",
        "use_rand_load_profile": "chk_load", "load_profile_fix": "sel_load_file",
        "use_rand_solar": "chk_solar", "solar_min": "sol_min", "solar_max": "sol_max",
        "solar_fix": "sol_fix", "temp_coeff": "sol_temp", "pr": "sol_pr",
        "use_rand_bat": "chk_bat", "bat_min": "bat_min", "bat_max": "bat_max",
        "bat_fix": "bat_fix", "bat_eff": "bat_eff", "bat_init_soc": "bat_soc_init",
        "vpp_thresh": "vpp_threshold", "t_peak_start": "t_p_start", "t_peak_end": "t_p_end",
        "t_offpeak_start": "t_o_start", "t_offpeak_end": "t_o_end"
    }
    for db_col, widget_key in mapping.items():
        if db_col in selected_row:
            val = selected_row[db_col]
            if db_col.startswith("t_") and isinstance(val, str):
                try:
                    h, m = map(int, val.split(':'))
                    st.session_state[widget_key] = time(h, m)
                except: pass
            elif widget_key.startswith("chk_"):
                if pd.isna(val): st.session_state[widget_key] = False
                elif isinstance(val, str): st.session_state[widget_key] = (val.strip().upper() == "TRUE")
                else: st.session_state[widget_key] = bool(val)
            else:
                st.session_state[widget_key] = val
                
    if "soc_min" in selected_row and "soc_max" in selected_row:
        st.session_state["bat_soc_range"] = (int(float(selected_row["soc_min"])*100), int(float(selected_row["soc_max"])*100))
    if "start_year" in selected_row and not pd.isna(selected_row["start_year"]): 
        st.session_state["date_start"] = int(float(selected_row["start_year"]))
    if "end_year" in selected_row and not pd.isna(selected_row["end_year"]): 
        st.session_state["date_end"] = int(float(selected_row["end_year"]))


st.set_page_config(page_title="CER Simulation Data Generator", layout="wide")

st.markdown(
    """
    <style>
    /* 1. Sembunyikan indikator "Running..." global di pojok kanan atas */
    div[data-testid="stStatusWidget"] {
        visibility: hidden;
    }
    
    /* 2. Sembunyikan notifikasi cache "Running gsheets..." di pojok (Toast) */
    div[data-testid="stToastContainer"] {
        display: none;
    }
    
    /* 3. JURUS RAHASIA: Sembunyikan Cache Spinner bawaan Google Sheets di tengah layar */
    div[data-testid="stSpinner"]:has(code) {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if 'app_initialized' not in st.session_state:
    st.session_state['app_initialized'] = True
    df_hist = load_config_history()
    if not df_hist.empty:
        # Karena df_history sudah dibalik (.iloc[::-1]), index 0 adalah data teratas (terbaru)
        latest_config = df_hist.iloc[0]
        apply_row_to_session(latest_config)
        st.session_state['active_config'] = latest_config['Config_Name']

if 'hasil_simulasi' not in st.session_state:
    st.session_state['hasil_simulasi'] = None
    st.session_state['used_params'] = {} 
    st.session_state['info_simulasi'] = ""

with st.sidebar:
    st.header("☁️ Setup Config Manager")
    active_cfg = st.session_state.get('active_config', 'Belum Ada / Default')
    st.success(f"**Active Config:** {active_cfg}")
    st.markdown("Save and Load configuration")
    
    # ==========================================
    # 1. FITUR LOAD DARI GOOGLE SHEETS
    # ==========================================
    st.subheader("📂 Load History Config")
    df_history = load_config_history()
    
    if not df_history.empty:
        # Buat label dropdown biar rapi: "Timestamp | Nama Config"
        history_options = df_history['Timestamp'].astype(str) + " | " + df_history['Config_Name'].astype(str)
        selected_history_str = st.selectbox("Select Config:", history_options.tolist())
        
        if st.button("Apply Config", use_container_width=True):
            # 1. Cari data baris yang dipilih
            selected_row = df_history[history_options == selected_history_str].iloc[0]
            apply_row_to_session(selected_row)
            st.session_state['active_config'] = selected_row['Config_Name']

            st.success("✅ Config Applied! Rerunning...")
            tm.sleep(0.5)
            st.rerun()
    else:
        st.info("Belum ada histori di Google Sheets.")
        
    st.divider()
    
    # ==========================================
    # 2. FITUR SAVE KE GOOGLE SHEETS
    # ==========================================
    st.subheader("💾 Save Current Config")
    new_config_name = st.text_input("Config Name (ex: Exam Config 1)")
    
    if st.button("Save Config", type="primary", use_container_width=True):
        if new_config_name.strip() == "":
            st.warning("⚠️ Empty Config Name")
        else:
            with st.spinner("Saving to Google Sheets..."):
                # Lempar state aplikasi saat ini ke fungsi save yang kita buat
                success = save_config_to_sheets(new_config_name, st.session_state)
                
                if success:
                    st.session_state['active_config'] = new_config_name
                    st.success("✅ Succesfully Saved Config!")
                    tm.sleep(1)
                    st.rerun() # Refresh agar data baru langsung muncul di dropdown

    st.divider()


st.title("CER Simulation Data Generator")
st.markdown("Set parameter region and period to start generate data")
st.divider()

col_dp, col_spec = st.columns([1, 1], gap="medium")

with col_dp:
    st.subheader("📁 Data Parameter")
    
    col_location, col_tariff = st.columns([1, 1.4])

    with col_location:
        list_lokasi = loader.get_list_lokasi()
        if not list_lokasi:
            st.error("Database empty! Run script 'setup_database_v6.py' first!")
            st.stop()
            
        st.info("🌍 Location")
        
        use_rand_location = st.toggle("Randomize / Fixed Location", value=False, key="chk_loc")
        
        selected_loc = None
        selected_point = None

        if not use_rand_location:
            selected_loc = random.choice(list_lokasi)
            
            list_titik_random = loader.get_list_titik(selected_loc)
            
            if list_titik_random:
                selected_point = random.choice(list_titik_random)
            else:
                selected_point = None
                
        else:
            l1, l2 = st.columns(2)
            selected_loc = l1.selectbox("1. Choose Region", list_lokasi, key="loc_region")
            
            list_titik = loader.get_list_titik(selected_loc)
            selected_point = l2.selectbox("2. Choose Point", list_titik, key="loc_point")
        
        available_years = loader.get_available_years(selected_loc, selected_point)
        
        st.info("🕒 Duration")
        if available_years:
            min_year, max_year = min(available_years), max(available_years)
            y1, y2 = st.columns(2)
            
            # --- FIX: Start Date ---
            start_kwargs = {}
            if "date_start" not in st.session_state:
                start_kwargs["index"] = 0 # Gunakan default index 0 hanya jika tidak ada di memori
                
            start_y = y1.selectbox("Start Date", available_years, key="date_start", **start_kwargs)
            
            # --- FIX: End Date ---
            valid_end_years = [y for y in available_years if y >= start_y]
            end_kwargs = {}
            
            if "date_end" not in st.session_state:
                end_kwargs["index"] = len(valid_end_years) - 1
            elif st.session_state["date_end"] not in valid_end_years:
                # Pengaman: Jika data tahun akhir di memori ternyata lebih kecil dari tahun awal
                st.session_state["date_end"] = valid_end_years[-1]
                
            end_y = y2.selectbox("End Date", valid_end_years, key="date_end", **end_kwargs)
            
        else:
            st.warning("There is no data on this point!")
            st.stop()

        st.info("🏠 Load Profile")
        use_rand_load = st.toggle("Randomize / Fixed Load Profile", value=False, key="chk_load")

        selected_load_file = None 
        
        if use_rand_load:
            list_load_files = loader.get_list_load_profiles()
            
            if list_load_files:
                selected_load_file = st.selectbox("Select Profile Source", list_load_files, key="sel_load_file")
            else:
                st.error("No CSV files found in 'dataset/load_profile'!")
                st.stop()

    with col_tariff:
        st.info("⚙️ VPP Setting")
        vpp_price = st.number_input("Dispatch Price Threshold (AUD/MWh)", 0, 2000, 800, 10, key="vpp_threshold")

        st.info("💲 Tariff")

        st.text("Export")
        exp_price = st.number_input("Flat Price (AUD/kWh)", 0.0, 1.0, 0.08, 0.01, key="exp_tariff")

        st.text("Import")
        use_ToU = st.toggle("Flat / Time-Of-Use (ToU)", key="chk_tou")
        
        t_utils.initialize_session_state()
        
        if use_ToU:
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
        else:
            p_flat = st.number_input("Flat Price (AUD/kWh)", 0.0, 2.0, 0.2, 0.01, key="imp_tariff")


with col_spec:
    st.subheader("⚙️ System Specification")
    
    col_panel, col_battery = st.columns(2)
    with col_panel:
        st.info("☀️ Solar Panel / Photovoltaics")
        use_rand_solar = st.toggle("Randomize / Fixed Size", key="chk_solar")
        if not use_rand_solar:
            sc1, sc2 = st.columns(2)
            p_solar_min = sc1.number_input("Min (kWp)", 0.0, 1000.0, 4.0, step=0.5, key="sol_min")
            p_solar_max = sc2.number_input("Max (kWp)", 0.0, 1000.0, 6.0, step=0.5, key="sol_max")
        else:
            p_solar_fix = st.number_input("Capacity (kWp)", 1.0, 100.0, 5.0, 0.5, key="sol_fix")

        p_temp = st.number_input("Temp Coeff", -0.01, 0.0, -0.004, 0.0001, format="%.4f", key="sol_temp")
        p_pr = st.number_input("PR (except temperature derated)", 0.5, 1.0, 0.8, 0.01, format="%.2f", key="sol_pr")
        
    with col_battery:
        st.info("🔋 Battery")
        use_rand_bat = st.toggle("Randomize / Fixed Size", key="chk_bat")
        if not use_rand_bat:
            bc1, bc2 = st.columns(2)
            p_bat_min = bc1.number_input("Min (kWh)", 0.0, 1000.0, 8.0, step=1.0, key="bat_min")
            p_bat_max = bc2.number_input("Max (kWh)", 0.0, 1000.0, 12.0, step=1.0, key="bat_max")
        else:
            p_bat_fix = st.number_input("Capacity (kWh)", 1.0, 200.0, 10.0, 1.0, key="bat_fix")

        # b1, b2 = st.columns(2)
        # p_charger_pwr = b1.number_input("(-) Charge (kW)", 0, 10, 5, 1, key="bat_chg")
        # p_discharger_pwr = b2.number_input("(+) Discharge (kW)", 0, 10, 5, 1, key="bat_dis")
        
        p_eff = st.number_input("Round-Trip Efficiency (%)", 50, 100, 95, key="bat_eff") / 100
        p_soc = st.slider("Initial SoC (%)", 0, 100, 50, key="bat_soc_init") / 100
        range_soc = st.slider("SoC Constraint (%)", min_value=0, max_value=100, value=(10, 90), key="bat_soc_range")
        p_min_soc = range_soc[0] / 100
        p_max_soc = range_soc[1] / 100              

st.markdown("---")
btn_run = st.button("Process Parameter and Generate Data", type="primary", use_container_width=True)

if btn_run:
    is_solar_fixed = False 
    if not use_rand_solar:
        final_p_solar = round(random.uniform(p_solar_min, p_solar_max), 2)
        
    else:
        final_p_solar = p_solar_fix
        is_solar_fixed = True


    if not use_rand_bat:

        segment = 5
        bat_total_range = p_bat_max - p_bat_min
        bat_segment_width = bat_total_range / segment

        if is_solar_fixed:
            mid = (segment - 1) // 2
            start_seg = max(0, mid - 1)
            end_seg   = min(segment - 1, mid + 1)

        else:
            solar_range = p_solar_max - p_solar_min

            if solar_range <= 0:
                current_segment = (segment - 1) // 2
            else:
                relative_pos = (final_p_solar - p_solar_min) / solar_range
                raw_segment = int(relative_pos * segment)
                current_segment = max(0, min(segment - 1, raw_segment))

            start_seg = max(0, current_segment - 1)
            end_seg   = min(segment - 1, current_segment + 1)

        final_bat_min = p_bat_min + (start_seg * bat_segment_width)
        final_bat_max = p_bat_min + ((end_seg + 1) * bat_segment_width)

        final_p_bat = round(random.uniform(final_bat_min, final_bat_max), 2)

    else:
        final_p_bat = p_bat_fix

    # power Charger/Discharge battery
    auto_charge_power = round(final_p_bat * 0.3, 2)

    if not use_rand_load:
        all_files = loader.get_list_load_profiles()
        if all_files:
            final_load_file = random.choice(all_files)
        else:
            st.error("❌ No CSV files found in dataset/load_profile!")
            st.stop()
    else:
        final_load_file = selected_load_file

    with st.spinner(f"Combine data {selected_loc} ({selected_point}) dari {start_y}-{end_y}..."):
        df_input = loader.load_and_merge_data(
            selected_loc, 
            selected_point, 
            start_y, 
            end_y, 
            fixed_load_file=final_load_file 
        )
        tm.sleep(0.5) 
    
    if df_input is not None:
        params = {
            'solar_capacity_kw': final_p_solar, 
            'temp_coeff': p_temp,
            'pr': p_pr,
            'battery_capacity_kwh': final_p_bat, 
            'battery_efficiency': p_eff,
            'battery_initial_soc': p_soc,
            'max_charge_kw': auto_charge_power,
            'max_discharge_kw': auto_charge_power,
            'soc_min_pct': p_min_soc,
            'soc_max_pct': p_max_soc,
            'dispatch_price_threshold': vpp_price, 
            't_offpeak_start': st.session_state.t_o_start,
            't_offpeak_end': st.session_state.t_o_end,
            't_peak_start': st.session_state.t_p_start,
            't_peak_end': st.session_state.t_p_end
        }
        
        with st.spinner("Calculate Energy Flow..."):
            df_result = calculator.run_simulation(df_input, params)
        
        st.session_state['hasil_simulasi'] = df_result
        st.session_state['info_simulasi'] = f"{selected_loc}_{selected_point}_{start_y}-{end_y}"
        
        tariff_snapshot = {
            'is_tou': use_ToU,
            'export_price': exp_price
        }
        
        if use_ToU:
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
            tariff_snapshot['import_flat'] = p_flat

        st.session_state['used_params'] = {
            'solar': final_p_solar,
            'solar_pr': p_pr,
            'solar_temp': p_temp,
            'bat': final_p_bat,
            'bat_eff': p_eff,
            'bat_soc_init': p_soc,
            'bat_charge_kw': auto_charge_power,
            'bat_discharge_kw': auto_charge_power,
            'soc_min': p_min_soc,
            'soc_max': p_max_soc,
            'vpp_thresh': vpp_price,
            'tariff_data': tariff_snapshot,
            'location': f"{selected_loc} - {selected_point}",
            'period': f"{start_y} to {end_y}",
            'load_source': final_load_file 
        }
        
        st.success(f"Data Has Been Generated!")
    else:
        st.error("Failed to Generate the Data")
         
if st.session_state['hasil_simulasi'] is not None:
    
    df_result = st.session_state['hasil_simulasi']
    file_name_info = st.session_state['info_simulasi']
    used_p = st.session_state['used_params']
    t_data = used_p['tariff_data']

    st.divider()
    
    st.markdown("### 📋 Generated Simulation Info")
    
    with st.container(border=True):
        st.markdown(f"**📍 Location:** `{used_p['location']}` | **🗓️ Period:** `{used_p['period']}` | **🏠 Load:** `{used_p['load_source']}`")
        st.divider()
        
        c_sys1, c_sys2, c_sys3 = st.columns(3)
        
        with c_sys1:
            st.markdown("#### ☀️ Solar PV")
            st.markdown(f"""
            - Capacity: **{used_p['solar']} kWp**
            - PR: **{used_p['solar_pr']}**
            - Temp Coeff: **{used_p['solar_temp']}**
            """)
            
        with c_sys2:
            st.markdown("#### 🔋 Battery Storage")
            st.markdown(f"""
            - Capacity: **{used_p['bat']} kWh**
            - Power: **-{used_p['bat_charge_kw']} / +{used_p['bat_discharge_kw']} kW**
            - Efficiency: **{int(used_p['bat_eff']*100)}%**
            """)
            
        with c_sys3:
            st.markdown("#### ⚡ Control Logic")
            st.markdown(f"""
            - VPP Threshold: **{used_p['vpp_thresh']} AUD**
            - SoC Limits: **{int(used_p['soc_min']*100)}% - {int(used_p['soc_max']*100)}%**
            - Initial SoC: **{int(used_p['bat_soc_init']*100)}%**
            """)

    with st.expander("💲 View Applied Tariff Details", expanded=True):
        tc1, tc2 = st.columns(2)
        with tc1:
            st.markdown(f"**Export Tariff:**")
            st.markdown(f"⚡ Flat Rate: **{t_data['export_price']} AUD/kWh**")
        with tc2:
            st.markdown(f"**Import Tariff:**")
            if t_data['is_tou']:
                st.markdown("🕒 **Time-of-Use (ToU) Profile:**")
                st.markdown(f"""
                - **Peak:** {t_data['peak_price']} AUD <br> &nbsp;&nbsp;&nbsp; *({t_data['peak_start']} - {t_data['peak_end']})*
                - **Shoulder:** {t_data['shoulder_price']} AUD <br> &nbsp;&nbsp;&nbsp; *({t_data['shoulder_start']} - {t_data['shoulder_end']})*
                - **Off-Peak:** {t_data['offpeak_price']} AUD <br> &nbsp;&nbsp;&nbsp; *({t_data['offpeak_start']} - {t_data['offpeak_end']})*
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"🟦 Flat Rate: **{t_data['import_flat']} AUD/kWh**")

    st.markdown("### 💾 Export Data")
    
    df_export = df_result.copy()
    df_export = df_export.round(2)

    output_columns = [
        'timestamp',
        'irradiance',
        'temperature', 
        'solar_output_kw', 
        'load_profile',
        'price_profile',       
        'battery_soc_pct',     
        'battery_power_ac_kw',
        'grid_net_kw',
    ]
    final_cols = [c for c in output_columns if c in df_export.columns]
    df_export = df_export[final_cols]

    df_export = df_export.rename(columns={
        'irradiance': 'irradiance_Wh/m^2',
        'temperature': 'temperature_C',
        'load_profile': 'load_kW',
        'price_profile': 'price_AUD',
        'battery_soc_pct': 'battery_soc_%'
    })
    
    csv = df_export.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Dataset (CSV)",
        data=csv,
        file_name=f"Data_{file_name_info}.csv",
        mime="text/csv",
        key='download-csv' 
    )

    st.divider()
    st.subheader("📊 Detailed Analysis")
    
    df_result['year']  = df_result['timestamp'].dt.year
    df_result['month'] = df_result['timestamp'].dt.month
    
    available_years_vis = sorted(df_result['year'].unique())
    selected_vis_year = st.selectbox("Select Year:", available_years_vis)
    df_vis_year = df_result[df_result['year'] == selected_vis_year].copy()
    
    factor = 5/60
    col_load = 'load_profile' if 'load_profile' in df_vis_year.columns else 'beban_rumah_kw'
    col_bat  = 'battery_power_ac_kw' if 'battery_power_ac_kw' in df_vis_year.columns else 'battery_power_kw'
    
    total_solar = df_vis_year['solar_output_kw'].sum() * factor
    total_load  = df_vis_year[col_load].sum() * factor
    total_import = df_vis_year['grid_net_kw'].apply(lambda x: x if x > 0 else 0).sum() * factor
    
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Total Solar ({selected_vis_year})", f"{total_solar:,.2f} kWh")
    m2.metric(f"Total Load ({selected_vis_year})", f"{total_load:,.2f} kWh")
    m3.metric(f"Grid Import ({selected_vis_year})", f"{total_import:,.2f} kWh", delta_color="inverse")

    visualizer.plot_annual_overview(df_vis_year, col_bat, selected_vis_year)
    
    st.divider()

    @st.fragment
    def show_monthly_analysis_fragment():
        available_months = sorted(df_vis_year['month'].unique())
        month_map = {m: calendar.month_name[m] for m in available_months}
        
        selected_month_name = st.selectbox("Select Month for Profile:", list(month_map.values()))
        
        selected_vis_month = [k for k, v in month_map.items() if v == selected_month_name][0]
        df_vis_month = df_vis_year[df_vis_year['month'] == selected_vis_month].copy()
        
        visualizer.plot_monthly_analysis(df_vis_month, col_load, selected_month_name, selected_vis_year)

    show_monthly_analysis_fragment()