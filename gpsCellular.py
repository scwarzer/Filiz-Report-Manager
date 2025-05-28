import os
from datetime import datetime
from math import atan2, cos, sin, radians

import requests
import pandas as pd
import folium
from geopy.distance import geodesic
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)

from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QVBoxLayout, QDialog, QMessageBox

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure(figsize=(6, 4))
        self.axes = fig.add_subplot(111)
        super().__init__(fig)

class gpsCellularAnalyzer(QDialog):
    def __init__(self, df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GPS-Cellular Analyze")
        self.setMinimumSize(800, 600)
        self.success = False  # Başarılı işlem takibi

        layout = QVBoxLayout()
        self.setLayout(layout)

        # === Konum kontrolü ===
        try:
            print("Status: Checking device coordinates...")
            device_df = df[(df["Lat"] != "-999") & (df["Lon"] != "-999")]
            if device_df.empty:
                raise ValueError("No valid coordinates found.")

            latest = device_df.sort_values("LogDate").iloc[-1]
            device_lat = self.convert_nmea_to_decimal(latest["Lat"])
            device_lon = self.convert_nmea_to_decimal(latest["Lon"])

            if device_lat is None or device_lon is None:
                raise ValueError("Invalid coordinates.")

            print(f"Status: Device coordinates OK - Lat: {device_lat}, Lon: {device_lon}")

        except Exception as e:
            print(f"Status: Map generation failed - {e}")
            return

        self.success = True

        # === Harita ===
        map_view = QWebEngineView()
        layout.addWidget(map_view)

        try:
            print("Status: Creating map...")
            fmap = folium.Map(location=[device_lat, device_lon], zoom_start=13)

            folium.Marker(
                [device_lat, device_lon],
                tooltip=f"Device Location: {device_lat}, {device_lon}",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(fmap)

            unique_stations = df[["MMC", "MNC", "LAC", "Id"]].drop_duplicates()

            for _, row in unique_stations.iterrows():
                mcc, mnc, lac, cid = row["MMC"], row["MNC"], row["LAC"], row["Id"]

                if any(pd.isna([mcc, mnc, lac, cid])):
                    continue

                latlon = self.get_location_from_mylnikov(str(mcc), str(mnc), str(lac), str(cid))
                if latlon:
                    distance_km = geodesic((device_lat, device_lon), latlon).km
                    radius_m = distance_km * 1000

                    # 📍 Baz istasyon marker'ı
                    folium.Marker(
                        latlon,
                        tooltip=f"Base Station\nMCC: {mcc}, MNC: {mnc}, LAC: {lac}, CID: {cid}",
                        icon=folium.Icon(color="red", icon="tower")
                    ).add_to(fmap)

                    # 🟢 Cihaz merkezli daire
                    folium.Circle(
                        location=[device_lat, device_lon],
                        radius=radius_m,
                        color='green',
                        fill=True,
                        fill_opacity=0.05
                    ).add_to(fmap)

                    # 📌 Açı yönü (radyan)
                    d_lat = latlon[0] - device_lat
                    d_lon = latlon[1] - device_lon
                    angle_rad = atan2(d_lat, d_lon)

                    # 💬 Etiket konumu (dairenin sınırında)
                    label_lat = device_lat + (radius_m / 111320) * sin(angle_rad)
                    label_lon = device_lon + (radius_m / (111320 * cos(radians(device_lat)))) * cos(angle_rad)

                    folium.Marker(
                        location=(label_lat, label_lon),
                        icon=folium.DivIcon(
                            html=f'<div style="font-size: 10pt; color: black; font-weight: bold;">{radius_m:.0f}m</div>'
                        )
                    ).add_to(fmap)
            print("Status: Map built with base stations and connections.")

        except Exception as e:
            print(f"Status: Error while creating map - {e}")
            return

        try:
            temps_dir = os.path.join(os.getcwd(), "temps")
            os.makedirs(temps_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = os.path.join(temps_dir, f"map_{timestamp}.html")
            fmap.save(html_file)
            file_path = os.path.abspath(html_file)
            local_url = QUrl.fromLocalFile(file_path)
            map_view.load(local_url)
            print(f"Status: Map saved to {file_path}")
        except Exception as e:
            print(f"Status: Failed to load map into QWebEngineView - {e}")
            return

        # === Grafik ve Toolbar ===
        self.canvas = MplCanvas(self)
        self.toolbar = NavigationToolbar(self.canvas, self)  # 🔹 Toolbar oluştur

        layout.addWidget(self.toolbar)  # 🔹 Toolbar'ı önce ekle
        layout.addWidget(self.canvas)  # 🔹 Ardından grafik canvas'ını ekle

        try:
            self.run_analysis(df)
        except Exception as e:
            print(f"Status: Failed to run analysis - {e}")

    def run_analysis(self, df):
        print("Status: Starting analysis...")

        if not all(col in df.columns for col in ["MMC", "MNC", "LAC", "Id", "PWR"]):
            print("Status: Required columns missing in dataframe.")
            QMessageBox.warning(self, "Missing Data", "PWR veya hücre bilgileri eksik.")
            return

        self.canvas.axes.clear()

        device_id = str(df["DeviceId"].iloc[0]) if "DeviceId" in df.columns else "Unknown"
        grouped = df.groupby(["MMC", "MNC", "LAC", "Id"])
        valid_pwr = df["PWR"][df["PWR"] < 0]

        if valid_pwr.empty:
            print("Status: No valid PWR data found (< 0).")
            QMessageBox.warning(self, "Warning", "No valid PWR data found (< 0).")
            return

        min_pwr = int(valid_pwr.min() // 5 * 5)
        max_pwr = int(valid_pwr.max() // 5 * 5) + 5
        bins = list(range(min_pwr, max_pwr + 1, 5))

        for (mcc, mnc, lac, cid), group in grouped:
            label = f"{mcc}-{mnc}-{lac}-{cid}"
            tower_pwr = group["PWR"]
            tower_pwr = tower_pwr[tower_pwr < 0]
            if tower_pwr.empty:
                continue

            self.canvas.axes.hist(
                tower_pwr,
                bins=bins,
                alpha=1,
                label=label
            )

        self.canvas.axes.set_title(f"Cell Tower - PWR Histogram (Device ID: {device_id})")
        self.canvas.axes.set_xlabel("PWR (Signal Strength, dBm)")
        self.canvas.axes.set_ylabel("Data Count")
        self.canvas.axes.legend(fontsize='x-small')
        self.canvas.axes.grid(True)
        self.canvas.draw()
        print("Status: Analysis complete and histogram rendered.")


    def convert_nmea_to_decimal(self, coord_str):
        try:
            direction = coord_str[-1]  # Son karakter yön
            value = float(coord_str[:-1])  # Son karakter hariç sayısal değer

            degrees = int(value // 100)
            minutes = value - degrees * 100
            decimal = degrees + minutes / 60

            if direction in ["S", "W"]:
                decimal = -decimal

            return decimal
        except Exception as e:
            print(f"Status: Conversion failed for {coord_str}: {e}")
            return None

    def hex_to_int(value):
        try:
            return int(value, 16) if isinstance(value, str) else int(value)
        except ValueError:
            print(f"Status: Invalid hex: {value}")
            return None

    def get_location_from_mylnikov(self, mcc, mnc, lac_hex, cid_hex):
        try:
            lac = int(lac_hex, 16)
            cid = int(cid_hex, 16)
        except ValueError:
            print(f"Status: Mylnikov cannot convert LAC/CID ({lac_hex}/{cid_hex}) to integer.")
            return None

        url = (
            "https://api.mylnikov.org/geolocation/cell?"
            f"v=1.1&data=open&mcc={mcc}&mnc={mnc}&lac={lac}&cellid={cid}"
        )

        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_data = response.json()
                if json_data["result"] == 200:
                    location = json_data["data"]
                    return (location["lat"], location["lon"])
                else:
                    print(f"Status: Mylnikov have no result for {mcc}-{mnc}-{lac}-{cid}")
            else:
                print(f"Status: Mylnikov HTTP error: {response.status_code}")
        except Exception as e:
            print("Status: Mylnikov error:", e)

        return None