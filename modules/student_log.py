import streamlit as st
import pandas as pd
import json
import zlib
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

TAB_LOGS = "Student_Logs"

def get_gsheets_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def generate_seed_from_nim(nim):
    """Mengubah teks NIM menjadi angka integer yang 100% konsisten untuk seed randomizer."""
    nim_clean = str(nim).strip().upper()
    return zlib.crc32(nim_clean.encode('utf-8'))

def save_log_to_sheets(nim, config_name, used_params_dict):
    """Menyimpan riwayat generate siswa ke database (Metadata JSON)"""
    try:
        conn = get_gsheets_connection()
        df_existing = conn.read(worksheet=TAB_LOGS, ttl=0)
        
        json_snapshot = json.dumps(used_params_dict)
        
        new_row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "NIM": str(nim).strip().upper(),
            "Config_Name": config_name,
            "Parameter_Snapshot": json_snapshot
        }
        
        df_new = pd.DataFrame([new_row])
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
        conn.update(worksheet=TAB_LOGS, data=df_updated)
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"⚠️ Failed To Save Student Log: {e}")
        return False

def get_student_logs():
    """Mengambil riwayat log mahasiswa dari Google Sheets"""
    try:
        conn = get_gsheets_connection()
        df = conn.read(worksheet=TAB_LOGS, ttl=0)
        df = df.dropna(subset=['NIM', 'Timestamp'])
        return df
    except Exception as e:
        st.error(f"⚠️ Gagal mengambil data log: {e}")
        return pd.DataFrame()