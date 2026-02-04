import os
import pandas as pd
import streamlit as st
import random 

DATASET_DIR = "dataset"
LOAD_PROFILE_DIR = os.path.join(DATASET_DIR, "load_profile")


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
            try:
                years.append(int(f.replace('.csv', '')))
            except ValueError: pass 
    return sorted(years)

@st.cache_data(show_spinner=False)
def load_generic_year_data(folder_path):
    """Load Master Solar File (Cached)"""
    if not os.path.exists(folder_path): return None
    
    files = sorted([f for f in os.listdir(folder_path) if f.endswith('.csv')])
    if not files: return None
    
    ref_file = os.path.join(folder_path, files[0]) 
    try:
        df = pd.read_csv(ref_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
        
        if 'suhu' in df.columns:
            df.rename(columns={'suhu': 'temperature'}, inplace=True)
            
        df['month'] = df['timestamp'].dt.month
        df['day'] = df['timestamp'].dt.day
        df['hour'] = df['timestamp'].dt.hour
        df['minute'] = df['timestamp'].dt.minute
        
        return df.drop(columns=['timestamp'])
    except Exception as e:
        st.error(f"Error reading master solar: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_single_load_profile(path_file):
    """Helper untuk load 1 file load profile spesifik (Cached)"""
    try:
        df = pd.read_csv(path_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
        
        if 'beban_rumah_kw' in df.columns:
            df.rename(columns={'beban_rumah_kw': 'load_profile'}, inplace=True)
            
        df['month'] = df['timestamp'].dt.month
        df['day'] = df['timestamp'].dt.day
        df['hour'] = df['timestamp'].dt.hour
        df['minute'] = df['timestamp'].dt.minute
        
        return df.drop(columns=['timestamp'])
    except Exception:
        return None

def get_random_load_profile_path():
    """Hanya mengambil path file, tidak me-load datanya (agar random tetap jalan di main)"""
    if not os.path.exists(LOAD_PROFILE_DIR): return None
    files = [f for f in os.listdir(LOAD_PROFILE_DIR) if f.endswith('.csv')]
    if not files: return None
    selected_file = random.choice(files)
    return os.path.join(LOAD_PROFILE_DIR, selected_file), selected_file


def load_and_merge_data(nama_lokasi, nama_titik, start_year, end_year):
    path_titik = os.path.join(DATASET_DIR, nama_lokasi, nama_titik)
    path_price_dir = os.path.join(DATASET_DIR, nama_lokasi, "Price")
    
    df_solar_master = load_generic_year_data(path_titik)
    
    load_path_info = get_random_load_profile_path()
    if not load_path_info:
        st.error("Gagal memilih load profile.")
        return None
    
    path_load, load_filename = load_path_info
    st.toast(f"🎲 Load Profile: {load_filename}")
    
    df_load_master = load_single_load_profile(path_load)

    if df_solar_master is None or df_load_master is None:
        st.error("Data Master Corrupt/Missing.")
        return None
    
    solar_feb28 = df_solar_master[
        (df_solar_master['month'] == 2) & (df_solar_master['day'] == 28)
    ].sort_values(['hour', 'minute'])
    
    load_feb28 = df_load_master[
        (df_load_master['month'] == 2) & (df_load_master['day'] == 28)
    ].sort_values(['hour', 'minute'])

    list_df_final = []

    for year in range(start_year, end_year + 1):
        file_price = os.path.join(path_price_dir, f"{year}.csv")
        if not os.path.exists(file_price): continue
            
        try:
            df_price = pd.read_csv(file_price)
            df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
            
            if df_price['timestamp'].duplicated().any():
                df_price = df_price.drop_duplicates(subset=['timestamp'])
            
            df_price = df_price.sort_values('timestamp')
            
            if 'harga_listrik' in df_price.columns:
                df_price.rename(columns={'harga_listrik': 'price_import'}, inplace=True)
            
            df_price['month'] = df_price['timestamp'].dt.month
            df_price['day'] = df_price['timestamp'].dt.day
            df_price['hour'] = df_price['timestamp'].dt.hour
            df_price['minute'] = df_price['timestamp'].dt.minute
            
            df_merged = pd.merge(df_price, df_solar_master, on=['month', 'day', 'hour', 'minute'], how='left')
            df_merged = pd.merge(df_merged, df_load_master, on=['month', 'day', 'hour', 'minute'], how='left')
            
            mask_nan = df_merged['irradiance'].isna()
            
            if mask_nan.any():
                fill_irr = solar_feb28['irradiance'].values
                fill_temp = solar_feb28['temperature'].values
                fill_load = load_feb28['load_profile'].values
                
                try:
                    df_merged.loc[mask_nan, 'irradiance'] = fill_irr
                    df_merged.loc[mask_nan, 'temperature'] = fill_temp
                    df_merged.loc[mask_nan, 'load_profile'] = fill_load
                except ValueError:
                    df_merged.loc[mask_nan, 'irradiance'] = 0
                    df_merged.loc[mask_nan, 'temperature'] = 25
                    df_merged.loc[mask_nan, 'load_profile'] = 0

            cols_to_keep = ['timestamp', 'price_import', 'irradiance', 'temperature', 'load_profile']
            df_final = df_merged[[c for c in cols_to_keep if c in df_merged.columns]]
            
            df_final = df_final.ffill().fillna(0)
            list_df_final.append(df_final)
            
        except Exception as e:
            st.error(f"Error processing {year}: {e}")

    if not list_df_final: return None

    return pd.concat(list_df_final, ignore_index=True)