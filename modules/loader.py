import os
import pandas as pd
import streamlit as st

DATASET_DIR = "dataset"

def get_list_lokasi():
    if not os.path.exists(DATASET_DIR): return []
    items = os.listdir(DATASET_DIR)
    return sorted([item for item in items if os.path.isdir(os.path.join(DATASET_DIR, item))])

def get_list_titik(nama_lokasi):
    path_lokasi = os.path.join(DATASET_DIR, nama_lokasi)
    if not os.path.exists(path_lokasi): return []
    items = os.listdir(path_lokasi)
    titik = [item for item in items 
             if os.path.isdir(os.path.join(path_lokasi, item)) and item != "Price"]
    return sorted(titik)

def get_available_years(nama_lokasi, nama_titik):
    path_titik = os.path.join(DATASET_DIR, nama_lokasi, nama_titik)
    if not os.path.exists(path_titik): return []
    files = os.listdir(path_titik)
    return sorted([int(f.replace('.csv', '')) for f in files if f.endswith('.csv')])

def load_and_merge_data(nama_lokasi, nama_titik, start_year, end_year):
    list_df = []
    
    path_titik = os.path.join(DATASET_DIR, nama_lokasi, nama_titik)
    path_price = os.path.join(DATASET_DIR, nama_lokasi, "Price")
    
    for year in range(start_year, end_year + 1):
        
        file_data = os.path.join(path_titik, f"{year}.csv")
        file_price = os.path.join(path_price, f"{year}.csv")
        
        if os.path.exists(file_data) and os.path.exists(file_price):
            try:
                df_main = pd.read_csv(file_data)
                df_main['timestamp'] = pd.to_datetime(df_main['timestamp'])
                df_main = df_main.drop_duplicates(subset=['timestamp'], keep='first')
                
                df_price = pd.read_csv(file_price)
                df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
                df_price = df_price.drop_duplicates(subset=['timestamp'], keep='first')
                
                df_merged = pd.merge(df_main, df_price, on='timestamp', how='left')
                
                df_merged['harga_listrik'] = df_merged['harga_listrik'].ffill().fillna(0)
                
                list_df.append(df_merged)
                
            except Exception as e:
                st.error(f"Error membaca data tahun {year}: {e}")
        else:
            st.warning(f"File data/harga tahun {year} tidak lengkap. Dilewati.")
            
    if not list_df:
        return None
        
    full_df = pd.concat(list_df, ignore_index=True)
    
    full_df = full_df.drop_duplicates(subset=['timestamp'], keep='first')
    full_df = full_df.sort_values('timestamp').reset_index(drop=True)

    return full_df
    list_df = []
    
    path_titik = os.path.join(DATASET_DIR, nama_lokasi, nama_titik)
    
    path_price = os.path.join(DATASET_DIR, nama_lokasi, "Price")
    
    for year in range(start_year, end_year + 1):
        
        file_data = os.path.join(path_titik, f"{year}.csv")
        
        file_price = os.path.join(path_price, f"{year}.csv")
        
        if os.path.exists(file_data) and os.path.exists(file_price):
            try:
                df_main = pd.read_csv(file_data)
                df_main['timestamp'] = pd.to_datetime(df_main['timestamp'])
                
                df_price = pd.read_csv(file_price)
                df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
                
                df_merged = pd.merge(df_main, df_price, on='timestamp', how='left')
                df_merged['harga_listrik'] = df_merged['harga_listrik'].ffill().fillna(0)
                
                list_df.append(df_merged)
                
            except Exception as e:
                st.error(f"Error pada tahun {year}: {e}")
        else:
            st.warning(f"Data tahun {year} tidak lengkap (Cek folder Price/Titik). Dilewati.")
            
    if not list_df:
        return None
        
    full_df = pd.concat(list_df, ignore_index=True)
    full_df = full_df.sort_values('timestamp').reset_index(drop=True)

    return full_df