import os
import pandas as pd
import numpy as np
import streamlit as st
import random
import calendar

DATASET_DIR = "dataset"
LOAD_PROFILE_DIR = os.path.join(DATASET_DIR, "load_profile")

ROWS_PER_DAY = 288
IDX_FEB_29_START = 59 * ROWS_PER_DAY  
IDX_FEB_28_START = 58 * ROWS_PER_DAY  

def get_list_lokasi():
    if not os.path.exists(DATASET_DIR): return []
    items = os.listdir(DATASET_DIR)
    return sorted([item for item in items if os.path.isdir(os.path.join(DATASET_DIR, item)) and item != "load_profile"])

def get_list_titik(nama_lokasi):
    path_lokasi = os.path.join(DATASET_DIR, nama_lokasi)
    if not os.path.exists(path_lokasi): return []
    items = os.listdir(path_lokasi)
    return sorted([item for item in items if os.path.isdir(os.path.join(path_lokasi, item)) and item != "Price"])

def get_available_years(nama_lokasi, nama_titik):
    path_price = os.path.join(DATASET_DIR, nama_lokasi, "Price")
    if not os.path.exists(path_price): return []
    files = os.listdir(path_price)
    years = []
    for f in files:
        if f.endswith('.csv'):
            try: years.append(int(f.replace('.csv', '')))
            except ValueError: pass 
    return sorted(years)

# ==========================================
# 1. LOAD GENERIC ARRAYS (RAW SPEED)
# ==========================================

@st.cache_data(show_spinner=False)
def load_solar_array(path_file):
    """
    Load CSV Solar -> Langsung ambil kolom data -> Jadi Array.
    TANPA parsing tanggal, TANPA sorting.
    """
    if not os.path.exists(path_file): return None, None
    try:
        # Baca CSV
        df = pd.read_csv(path_file)
        
        # Cari nama kolom (case insensitive)
        col_irr = next((c for c in df.columns if 'irradiance' in c.lower() or 'glob' in c.lower()), None)
        col_temp = next((c for c in df.columns if 'temperature' in c.lower() or 'amb' in c.lower()), None)
        
        if not col_irr: return None, None

        # Langsung convert ke Numpy (Sangat Cepat)
        arr_irr = df[col_irr].to_numpy()
        
        # Jika ada data suhu ambil, jika tidak buat array rata 25 derajat
        arr_temp = df[col_temp].to_numpy() if col_temp else np.full(len(arr_irr), 25.0)
        
        return arr_irr, arr_temp
    except Exception:
        return None, None

def load_load_profile_array():
    """
    Load CSV Load Profile -> Langsung ambil kolom data -> Jadi Array.
    """
    if not os.path.exists(LOAD_PROFILE_DIR): return None, "No Folder"
    files = [f for f in os.listdir(LOAD_PROFILE_DIR) if f.endswith('.csv')]
    if not files: return None, "Empty"
    
    selected_file = random.choice(files)
    path_file = os.path.join(LOAD_PROFILE_DIR, selected_file)
    
    try:
        df = pd.read_csv(path_file)
        
        # Cari kolom beban
        col_load = next((c for c in df.columns if 'beban' in c.lower() or 'load_profile' in c.lower()), None)
        if not col_load: return None, "Invalid CSV"
        
        # Langsung convert ke Numpy
        return df[col_load].to_numpy(), selected_file
    except Exception:
        return None, "Error Read"

def get_master_solar_path(folder_path):
    if not os.path.exists(folder_path): return None
    files = sorted([f for f in os.listdir(folder_path) if f.endswith('.csv')])
    return os.path.join(folder_path, files[0]) if files else None

# ==========================================
# 2. MAIN LOGIC (INDEX SPLICING)
# ==========================================

def load_and_merge_data(nama_lokasi, nama_titik, start_year, end_year):
    path_titik = os.path.join(DATASET_DIR, nama_lokasi, nama_titik)
    path_price_dir = os.path.join(DATASET_DIR, nama_lokasi, "Price")
    
    # 1. SIAPKAN ARRAY MASTER (1 TAHUN)
    solar_path = get_master_solar_path(path_titik)
    if not solar_path:
        st.error("File Solar Master tidak ditemukan.")
        return None
        
    base_irr, base_temp = load_solar_array(solar_path)
    base_load, load_name = load_load_profile_array()
    
    if base_irr is None or base_load is None:
        st.error("Gagal memuat data array Solar/Load.")
        return None
        
    st.toast(f"Profile: {load_name}")

    # Siapkan Slice Array untuk Kabisat (Copy Data 28 Feb)
    # Index 16704 s/d 16992 (Data 288 baris milik tanggal 28 Feb)
    extra_irr = base_irr[IDX_FEB_28_START:IDX_FEB_29_START]
    extra_temp = base_temp[IDX_FEB_28_START:IDX_FEB_29_START]
    extra_load = base_load[IDX_FEB_28_START:IDX_FEB_29_START]

    list_df_final = []

    # 2. LOOP TAHUN (PRICE BACKBONE)
    for year in range(start_year, end_year + 1):
        file_price = os.path.join(path_price_dir, f"{year}.csv")
        if not os.path.exists(file_price): continue
            
        try:
            # Load Price (Masih perlu parsing timestamp ini karena ini backbone waktu kita)
            df_price = pd.read_csv(file_price)
            df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
            # Sort Price tetap diperlukan agar urutan backbone benar
            df_price = df_price.sort_values('timestamp').reset_index(drop=True)

            if 'harga_listrik' in df_price.columns:
                df_price.rename(columns={'harga_listrik': 'price_import'}, inplace=True)

            # Cek Kabisat
            is_leap = calendar.isleap(year)
            
            # Buat Array Tahunan Solar/Load (Splicing)
            if is_leap:
                # Sisipkan data 28 Feb untuk menjadi 29 Feb
                curr_irr = np.concatenate([base_irr[:IDX_FEB_29_START], extra_irr, base_irr[IDX_FEB_29_START:]])
                curr_temp = np.concatenate([base_temp[:IDX_FEB_29_START], extra_temp, base_temp[IDX_FEB_29_START:]])
                curr_load = np.concatenate([base_load[:IDX_FEB_29_START], extra_load, base_load[IDX_FEB_29_START:]])
            else:
                # Bukan kabisat, pakai array master apa adanya
                curr_irr = base_irr
                curr_temp = base_temp
                curr_load = base_load
            
            # Tempel ke DataFrame
            len_price = len(df_price)
            len_data = len(curr_irr)
            
            # Safety Logic: Potong jika array kepanjangan, Pad 0 jika kedekitan
            if len_price <= len_data:
                df_price['irradiance'] = curr_irr[:len_price]
                df_price['temperature'] = curr_temp[:len_price]
                df_price['load_profile'] = curr_load[:len_price]
            else:
                pad_len = len_price - len_data
                df_price['irradiance'] = np.pad(curr_irr, (0, pad_len), 'edge')
                df_price['temperature'] = np.pad(curr_temp, (0, pad_len), 'edge')
                df_price['load_profile'] = np.pad(curr_load, (0, pad_len), 'edge')

            cols = ['timestamp', 'price_import', 'irradiance', 'temperature', 'load_profile']
            list_df_final.append(df_price[cols])
            
        except Exception as e:
            st.error(f"Error processing year {year}: {e}")

    if not list_df_final: return None

    return pd.concat(list_df_final, ignore_index=True)