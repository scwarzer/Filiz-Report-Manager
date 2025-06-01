import os
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from PyQt5.QtCore import QObject, pyqtSignal

class Portal_dataFetch:
    def __init__(self, email, password, download_dir="temps", headless=True):
        self.email = email
        self.password = password
        self.download_path = os.path.join(os.getcwd(), download_dir)
        os.makedirs(self.download_path, exist_ok=True)
        self.driver = self._init_driver(headless)
        self.wait = WebDriverWait(self.driver, 15)
        print(f"Status: Initialized Portal dataFetch. headless={headless}, download:{self.download_path}")

    def _init_driver(self, headless):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
        prefs = {
            "download.default_directory": self.download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        print("Status: Chrome driver initialized.")
        return webdriver.Chrome(options=options)

    def login(self):
        print("Status: Navigating to login page...")
        self.driver.get("https://portal.doktar.io/auth/login")
        self.wait.until(EC.presence_of_element_located((By.ID, "input-email")))
        self.driver.find_element(By.ID, "input-email").send_keys(self.email)
        self.driver.find_element(By.ID, "input-password").send_keys(self.password)
        print("Status: Submitting login form...")
        self.driver.find_element(
            By.CSS_SELECTOR,
            "button.appearance-filled.full-width.size-large.status-primary"
        ).click()
        self.wait.until(EC.url_contains("/pages"))
        print("Status: Logged into portal.")

    def go_to_device_logs(self, device_id):
        url = f"https://portal.doktar.io/pages/filiz/{device_id}/filizLogList/2"
        print(f"Status: Navigating to device log page: {url}")
        self.driver.get(url)
        self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "nb-spinner")))
        print("Status: Portal page loaded.")

    def download_excel(self):
        print("Status: Looking for Excel button...")
        excel_button = self.driver.find_element(
            By.XPATH, "//button[.//i[contains(@class, 'fa-file-excel')]]"
        )
        self.driver.execute_script("arguments[0].click();", excel_button)
        print("Status: Excel download triggered.")

    def _get_downloaded_file(self, extension=".xlsx", wait_timeout=30):
        print(f"Status: Waiting for Excel file download... (timeout = {wait_timeout}s)")
        start_time = time.time()
        while time.time() - start_time < wait_timeout:
            files = [f for f in os.listdir(self.download_path) if f.endswith(extension)]
            if len(files) == 1:
                full_path = os.path.join(self.download_path, files[0])
                if not os.path.exists(full_path + ".crdownload"):
                    print(f"Status: Excel file downloaded: {full_path}")
                    return full_path
            time.sleep(0.5)
        print("Warning: Download timeout or file not completed.")
        return None

    def fetch_device_data(self, device_id):
        print(f"Status: Fetching data for device ID: {device_id}")
        self.login()
        self.go_to_device_logs(device_id)
        self.download_excel()

        print("Status: Checking downloaded files...")
        files = os.listdir(self.download_path)
        print(f"Status: Files in download path: {files}")

        file_path = self._get_downloaded_file()
        if file_path and os.path.exists(file_path):
            print(f"Status: Reading downloaded Excel file: {file_path}")
            try:
                df = pd.read_excel(file_path)
                print(f"Status: Excel data loaded into DataFrame. Shape: {df.shape}")
            except Exception as e:
                print(f"Error: Failed to read Excel file - {e}")
                df = pd.DataFrame()

            # Klasör temizliği
            for f in os.listdir(self.download_path):
                try:
                    os.remove(os.path.join(self.download_path, f))
                except Exception as e:
                    print(f"Warning: Could not remove file {f} - {e}")

            return df
        else:
            print("Error: No Excel file found after download.")
            print(f"Download directory: {self.download_path}")
            return None  # veya return pd.DataFrame() dersen uygulama çökmez

    def close(self):
        self.driver.quit()
        print("Status: Chrome driver closed.")

class Report_dataFetch:
    def __init__(self, base_url="https://report.admin.doktarim.com/sensor/values/by/device/id"):
        self.base_url = base_url

    def fetch_table_data(self, device_id):
        try:
            url = f"{self.base_url}?deviceId={device_id}"
            print(f"Status: Fetching report HTML data from: {url}")
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", {"id": "dataTable"})

            if not table:
                print("Error: HTML table not found.")
                return None

            headers = [th.text.strip() for th in table.find("thead").find_all("th")]
            rows = []
            for tr in table.find("tbody").find_all("tr"):
                cols = [td.text.strip() for td in tr.find_all("td")]
                rows.append(cols)

            df = pd.DataFrame(rows, columns=headers)
            print("Status: Report data parsed.")

            keep_columns = ["LogDate", "CreatedOn", "Acc", "Bat", "RC", "WSD", "LI", "Lat", "Lon"]
            df = df[[col for col in keep_columns if col in df.columns]]

            print("Status: Columns removed.")
            return df

        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
        except Exception as e:
            print(f"Unexpected error while parsing report: {e}")

        return None  # Her durumda fallback

class FetchWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, device_id, email, password):
        super().__init__()
        self.device_id = device_id
        self.email = email
        self.password = password

    def run(self):
        try:
            df = datafetch(self.device_id, self.email, self.password)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(str(e))

def datafetch(device_id, email, password, silent=True):
    print(f"Status: Fetching portal data for device {device_id}...")
    try:
        portal_client = Portal_dataFetch(email=email, password=password, headless=silent)
        try:
            portal_df = portal_client.fetch_device_data(str(device_id))
        finally:
            portal_client.close()
    except Exception as e:
        print(f"Error: Failed to fetch portal data - {e}")
        return None

    print("Status: Fetching report data...")
    try:
        report_fetcher = Report_dataFetch()
        report_df = report_fetcher.fetch_table_data(device_id)
        print(f"Status: Report data shape: {report_df.shape}")
    except Exception as e:
        print(f"Error: Failed to fetch report data - {e}")
        return None

    if portal_df is None or report_df is None:
        print("Error: One of the data sources returned None.")
        return None

    print("Status: Merging data...")
    try:
        merged_df = merge_data(report_df, portal_df)
        if merged_df is None or merged_df.empty:
            print("Warning: No data after merging.")
            return None
        print(f"Status: Merged data shape: {merged_df.shape}")
    except Exception as e:
        print(f"Error during merging data - {e}")
        return None

    print("Status: Cleaning and sorting data...")
    try:
        merged_df = split_gsm_info_column(merged_df)
        merged_df = filter_columns(merged_df)
        merged_df = sort_by_timestamp(merged_df)
    except Exception as e:
        print(f"Error during cleaning/sorting - {e}")
        return None

    print("Status: Data fetch complete.")
    return merged_df

def merge_data(report_df, portal_df):
    try:
        if report_df is None or portal_df is None:
            print("Error: One of the dataframes is None.")
            return None

        # Sütun isimlerini tanımla.
        portal_ts_col = "Log Date (Raw)"
        portal_acc_col = "Accelerometer"
        report_ts_col = "LogDate"
        report_acc_col = "Acc"

        # Rapor tarafının timestamp formatlanması gerekiyor. Bunlar merge işlemi için kullanılacak.
        portal_df["merge_key"] = pd.to_datetime(
            normalize_timestamp(portal_df, portal_ts_col), errors="coerce"
        )
        report_df["merge_key"] = pd.to_datetime(
            normalize_timestamp(report_df, report_ts_col, date_format="%d/%m/%Y %H:%M:%S"), errors="coerce"
        )

        # +2 saat ekle (GMT düzeltmesi ama şimdilik iptal ediyorum kafalar karışmasın.)
        #portal_df["merge_key"] += pd.Timedelta(hours=2)
        #report_df["merge_key"] += pd.Timedelta(hours=2)

        # Accelerometreyi eşleşme sütunu olarak kullan
        portal_df["acc_match"] = portal_df[portal_acc_col].astype(str).str.strip()
        report_df["acc_match"] = report_df[report_acc_col].astype(str).str.strip()

        # Merge sırasında duplicate olanlar tek hale gelsin. Zaten tamamen aynı veriler.
        portal_df_dedup = portal_df.drop_duplicates(subset=["merge_key", "acc_match"])

        # Merge işlemini gerçekleştir. Aynı col isimleri için suffix ekle.
        merged_df = pd.merge(
            report_df,
            portal_df_dedup,
            on=["merge_key", "acc_match"],
            how="inner",
            suffixes=("_report", "_portal")
        )

        # TimestampRounded sütununu ekle. Missed data için kullanılacak.
        merged_df["TimestampRounded"] = merged_df["merge_key"].dt.round("h")

        # Birleşme sırasında oluşan geçici sütunları kaldır
        merged_df.drop(columns=["merge_key", "acc_match"], inplace=True)

        print(f"Status: Merged {len(merged_df)} matched rows.")
        return merged_df

    except Exception as e:
        print(f"Error: Error during merge: {e}")
        return None

def normalize_timestamp(df, column_name, date_format=None):
    try:
        dt = pd.to_datetime(df[column_name], format=date_format, errors='coerce') if date_format \
             else pd.to_datetime(df[column_name], errors='coerce')
        return dt.dt.strftime("%Y-%m-%d %H:%M")
    except Exception as e:
        print(f"Error: Timestamp normalize failed on column '{column_name}': {e}")
        return pd.Series([None] * len(df))

def split_gsm_info_column(df, gsm_column="GSMInfo"):
    if gsm_column not in df.columns:
        print(f"Warning: Column '{gsm_column}' not found.")
        return df

    operator_list = []
    extra_columns_dicts = []

    for val in df[gsm_column]:
        parts = str(val).split(',')
        operator_list.append(parts[0] if parts else "")
        kv_dict = {}
        for item in parts[1:]:
            if ':' in item:
                k, v = item.split(':', 1)
                kv_dict[k.strip()] = v.strip()
        extra_columns_dicts.append(kv_dict)

    extra_df = pd.DataFrame(extra_columns_dicts)
    extra_df.insert(0, "Operator", operator_list)

    # Eğer "PWR" sütunu varsa temizleyip sayı yap
    if "PWR" in extra_df.columns:
        extra_df["PWR"] = (
            extra_df["PWR"]
            .astype(str)
            .str.replace("dbm", "", regex=False)
            .str.strip()
        )
        extra_df["PWR"] = pd.to_numeric(extra_df["PWR"], errors="coerce")

    # Orijinal GSM sütununu sil ve yenilerini ekle
    df = df.drop(columns=[gsm_column])
    for col in extra_df.columns:
        df[col] = extra_df[col]

    print(f"Status: '{gsm_column}' column has been split into {list(extra_df.columns)}")
    return df

def filter_columns(df):
    FILTERED_COLUMNS_ORDER = [
        "LogDate", "CreatedOn", "TimestampRounded", "DeviceId", "Master Device ID", "State", "Status", "Ver", "Malfunction", "Defect Code", "Bat", "Acc", "CPUTemp", "DevInfo",
        "LI", "RC", "WSD", "Light Intensity", "Precipitation (mm)", "Wind Speed & Direction", "Lat", "Lon", "Operator", "PWR", "Id", "LAC", "TAC", "MMC", "MNC", "IMSI", "IMEI", "Air Temperature", "Air Humidity",
        "Soil Surface Temperature", "Soil Surface Humidity", "Under Soil Moisture(20 cm)", "Under Soil Moisture(40 cm)",
        "Under Soil Moisture(60 cm)", "Under Soil Temperature - Filiz 1.7 - 20 cm - Data",
        "Under Soil Temperature - Filiz 1.7 - 40 cm", "Under Soil Temperature - Filiz 1.7 - 60 cm - Data", "SC1", "SC2",
        "SC3", "SC4", "SC5", "SC6", "SC7", "SC8", "Main Board PCB Humidity", "Main Board PCB Temperature",
        "Soil Moisture Sensor PCB Humidity", "Soil Moisture Sensor PCB Temperature"
    ]

    # Silinecek sütunları bul
    columns_to_drop = [col for col in df.columns if col not in FILTERED_COLUMNS_ORDER]
    if columns_to_drop:
        print(f"Status: Dropping columns not in allowed list: {columns_to_drop}")
        df = df.drop(columns=columns_to_drop)

    # Sıralamayı uygula
    existing_cols = [col for col in FILTERED_COLUMNS_ORDER if col in df.columns]
    df = df[existing_cols].copy()

    # LogDate sütununa 2 saat ekle ve formatla
    if "LogDate" in df.columns:
        df["LogDate"] = pd.to_datetime(df["LogDate"], format="%d/%m/%Y %H:%M:%S", errors="coerce", dayfirst=True) #+ pd.Timedelta(hours=2)
        df["LogDate"] = df["LogDate"].dt.strftime("%d/%m/%Y %H:%M:%S")

    print("Status: Unwanted columns dropped, reordered, and LogDate adjusted.")
    return df

def sort_by_timestamp(df, column_name="LogDate", ascending=False):
    if column_name in df.columns:
        try:
            df.loc[:, column_name] = pd.to_datetime(df[column_name], errors="coerce", dayfirst=True)
            df = df.sort_values(column_name, ascending=ascending)
          #  print(f"Status: '{column_name}' sorted ({'ascending' if ascending else 'descending'}).")
        except Exception as e:
            print(f"Warning: Could not sort by '{column_name}': {e}")
    else:
        print(f"Warning: '{column_name}' column not found for sorting.")
    return df