import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time

from modules import loader, calculator

st.set_page_config(page_title="Sistem Simulasi Energi", layout="wide")

if 'hasil_simulasi' not in st.session_state:
    st.session_state['hasil_simulasi'] = None

st.title("Simulasi Energi Multi-Lokasi")
st.markdown("Pilih lokasi dan rentang waktu dari database untuk memulai simulasi.")
st.divider()

col_db, col_spec = st.columns([1, 1.5], gap="large")

with col_db:
    st.subheader("📁 Sumber Data")
    
    list_lokasi = loader.get_list_lokasi()
    if not list_lokasi:
        st.error("Database kosong! Jalankan script 'setup_database_v2.py' dulu.")
        st.stop()
        
    selected_loc = st.selectbox("1. Pilih Lokasi Wilayah", list_lokasi)
    list_titik = loader.get_list_titik(selected_loc)
    selected_point = st.selectbox("2. Pilih Titik / Gedung", list_titik)
    available_years = loader.get_available_years(selected_loc, selected_point)
    
    if available_years:
        min_year, max_year = min(available_years), max(available_years)
        c1, c2 = st.columns(2)
        start_y = c1.selectbox("Dari Tahun", available_years, index=0)
        valid_end_years = [y for y in available_years if y >= start_y]
        end_y = c2.selectbox("Sampai Tahun", valid_end_years, index=len(valid_end_years)-1)
    else:
        st.warning("Tidak ada data tahunan di titik ini.")
        st.stop()

with col_spec:
    st.subheader("⚙️ Spesifikasi Sistem")
    
    s1, s2, s3 = st.columns(3)
    with s1:
        st.info("☀️ Solar Panel")
        p_solar = st.number_input("Kapasitas (kWp)", 1.0, 100.0, 5.0, 0.5)
        p_temp = st.number_input("Temp Coeff", -0.01, 0.0, -0.004, format="%.4f")
        
    with s2:
        st.warning("🔋 Baterai")
        p_bat = st.number_input("Kapasitas (kWh)", 1.0, 200.0, 10.0, 1.0)
        p_eff = st.number_input("Efisiensi (%)", 50, 100, 95) / 100
        
    with s3:
        st.success("⚡ Kondisi Awal")
        p_soc = st.slider("Initial SoC (%)", 0, 100, 50) / 100

st.markdown("---")
btn_run = st.button("PROSES DATA & JALANKAN SIMULASI", type="primary", use_container_width=True)

if btn_run:
    with st.spinner(f"Menggabungkan data {selected_loc} ({selected_point}) dari {start_y}-{end_y}..."):
        df_input = loader.load_and_merge_data(selected_loc, selected_point, start_y, end_y)
        time.sleep(0.5) 
    
    if df_input is not None:
        params = {
            'solar_capacity_kw': p_solar,
            'temp_coeff': p_temp,
            'battery_capacity_kwh': p_bat,
            'battery_efficiency': p_eff,
            'battery_initial_soc': p_soc
        }
        
        with st.spinner("Menghitung aliran energi fisik..."):
            df_result = calculator.run_simulation(df_input, params)
        
        st.session_state['hasil_simulasi'] = df_result
        st.session_state['info_simulasi'] = f"{selected_loc}_{selected_point}_{start_y}-{end_y}"
        
        st.success("Simulasi Selesai! Hasil tersimpan.")
    else:
        st.error("Gagal memproses data.")


if st.session_state['hasil_simulasi'] is not None:
    
    df_result = st.session_state['hasil_simulasi']
    file_name_info = st.session_state['info_simulasi']

    st.divider()
    total_days = len(df_result) / 288
    st.subheader(f"📊 Hasil Analisis: {file_name_info} ({int(total_days)} Hari)")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Produksi Solar", f"{df_result['solar_output_kw'].sum()*(5/60):,.0f} kWh")
    m2.metric("Konsumsi Beban", f"{df_result['beban_rumah_kw'].sum()*(5/60):,.0f} kWh")
    m3.metric("Impor PLN (Beli)", f"{df_result['grid_import_kwh'].sum():,.0f} kWh", delta_color="inverse")
    m4.metric("Total Tagihan", f"Rp {df_result['biaya_listrik_rp'].sum():,.0f}", delta_color="inverse")
    
    st.markdown("### 📈 Grafik Detail (Sampel 5 Hari Pertama)")
    subset = df_result.head(288 * 5)
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    
    ax1.set_title("Keseimbangan Daya (kW)")
    ax1.plot(subset['timestamp'], subset['solar_output_kw'], color='green', label='Solar', alpha=0.8)
    ax1.plot(subset['timestamp'], subset['beban_rumah_kw'], color='red', linestyle='--', label='Beban', alpha=0.8)
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)
    
    ax2.set_title("Level Baterai (%)")
    ax2.fill_between(subset['timestamp'], subset['battery_percentage'], color='blue', alpha=0.1)
    ax2.plot(subset['timestamp'], subset['battery_percentage'], color='blue')
    ax2.set_ylim(0, 105)
    ax2.grid(True, alpha=0.3)
    
    ax3.set_title("Pembelian Listrik Grid (kWh)")
    ax3.bar(subset['timestamp'], subset['grid_import_kwh'], color='black', width=0.01)
    ax3.grid(True, alpha=0.3)
    
    st.pyplot(fig)
    
    st.markdown("### 💾 Export Data")
    csv = df_result.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Laporan Lengkap (CSV)",
        data=csv,
        file_name=f"Laporan_{file_name_info}.csv",
        mime="text/csv",
        key='download-csv' 
    )