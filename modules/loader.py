import os
import pandas as pd
import streamlit as st

DATASET_DIR = "dataset"

def get_list_lokasi():
    """Mengambil daftar folder Lokasi"""
    if not os.path.exists(DATASET_DIR):
        return []
    items = os.listdir(DATASET_DIR)
    lokasi = [item for item in items if os.path.isdir(os.path.join(DATASET_DIR, item))]
    return sorted(lokasi)

def get_list_titik(nama_lokasi):
    """Mengambil daftar folder Titik di dalam Lokasi"""
    path_lokasi = os.path.join(DATASET_DIR, nama_lokasi)
    if not os.path.exists(path_lokasi):
        return []
    items = os.listdir(path_lokasi)
    titik = [item for item in items if os.path.isdir(os.path.join(path_lokasi, item))]
    return sorted(titik)

def get_available_years(nama_lokasi, nama_titik):
    """Melihat tahun apa saja yang tersedia (2023.csv, dll)"""
    path_titik = os.path.join(DATASET_DIR, nama_lokasi, nama_titik)
    if not os.path.exists(path_titik):
        return []
    files = os.listdir(path_titik)
    years = [int(f.replace('.csv', '')) for f in files if f.endswith('.csv')]
    return sorted(years)

def load_and_merge_data(nama_lokasi, nama_titik, start_year, end_year):
    """
    Fungsi Utama:
    1. Loop dari start_year ke end_year.
    2. Gabung semua file CSV tahunan.
    3. Ambil price_profile.csv dari folder Lokasi.
    4. Gabungkan harga ke data utama berdasarkan Jam.
    """
    
    list_df = []
    path_titik = os.path.join(DATASET_DIR, nama_lokasi, nama_titik)
    
    for year in range(start_year, end_year + 1):
        file_path = os.path.join(path_titik, f"{year}.csv")
        
        if os.path.exists(file_path):
            try:
                df_year = pd.read_csv(file_path)
                df_year['timestamp'] = pd.to_datetime(df_year['timestamp'])
                list_df.append(df_year)
            except Exception as e:
                st.error(f"Gagal baca file {year}.csv: {e}")
        else:
            st.warning(f"Data tahun {year} tidak ditemukan, dilewati.")
            
    if not list_df:
        return None 
        
    full_df = pd.concat(list_df, ignore_index=True)
    full_df = full_df.sort_values('timestamp').reset_index(drop=True)
    
    path_price = os.path.join(DATASET_DIR, nama_lokasi, "price_profile.csv")
    
    if os.path.exists(path_price):
        df_price = pd.read_csv(path_price)
        
        full_df['temp_hour'] = full_df['timestamp'].dt.hour
        
        full_df = full_df.merge(df_price, left_on='temp_hour', right_on='jam', how='left')
        
        full_df = full_df.drop(columns=['temp_hour', 'jam'])
        
        full_df = full_df.rename(columns={'harga_per_kwh': 'harga_listrik'})
        
    else:
        st.error(f"File harga tidak ditemukan di {nama_lokasi}/price_profile.csv")
        return None

    return full_df