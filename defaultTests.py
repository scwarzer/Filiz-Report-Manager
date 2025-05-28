import pandas as pd

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QMessageBox
)

from dataFetch import sort_by_timestamp

class DefaultTests(QDialog):
    def __init__(self, tester, df_all, device_id_input, selected_tests=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Default Tests")
        self.resize(900, 600)

        self.tester = tester
        self.df_all = df_all
        self.device_display = device_id_input
        self.selected_tests = selected_tests

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # === FILTRE TARAFI ===
        tests_layout = QVBoxLayout()
        tests_layout.addWidget(QLabel("Filter Test Datas:"))

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All", "Low Battery", "Low Signal", "Defect", "Malfunction",
            "Missed Data", "Log Data", "Duplicate Data",
            "Accelerometer Alert", "Mainboard Humidity", "Soil Sensor Humidity"
        ])
        self.filter_combo.currentIndexChanged.connect(self.update_table_by_filter)
        tests_layout.addWidget(self.filter_combo)

        combo_wrapper_layout = QHBoxLayout()
        combo_wrapper_layout.addLayout(tests_layout)
        self.main_layout.addLayout(combo_wrapper_layout)

        # === INFO TARAFI ===
        self.info_label = QLabel()
        self.main_layout.addWidget(self.info_label)

        self.table = QTableWidget()
        self.main_layout.addWidget(self.table)

        # === SUMMARY TARAFI ===
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(5)
        self.summary_table.setHorizontalHeaderLabels(["Device ID", "Test", "Error Count", "Total", "Rate"])
        self.main_layout.addWidget(self.summary_table)

        self.copy_btn = QPushButton("Copy Report")
        self.copy_btn.clicked.connect(self.copy_summary_to_clipboard)
        self.main_layout.addWidget(self.copy_btn)

        self.update_table_by_filter()

    def update_table_by_filter(self):
        if self.df_all is None:
            return

        df = self.df_all.copy()
        df, _ = self.tester.add_time_difference_column(df)
        selection = self.filter_combo.currentText()

        test_map = {
            "Low Battery": self.tester.filter_battery_data,
            "Low Signal": self.tester.filter_signal_data,
            "Defect": self.tester.filter_defect_data,
            "Malfunction": self.tester.filter_malfunction_data,
            "Missed Data": self.tester.filter_missed_data,
            "Duplicate Data": self.tester.filter_duplicate_data,
            "Accelerometer Alert": self.tester.filter_acc_alert,
            "Log Data": self.tester.filter_status_log,
            "Mainboard Humidity": self.tester.filter_mainboard_humidity,
            "Soil Sensor Humidity": self.tester.filter_soilsensor_humidity
        }

        if selection in test_map:
            filtered_df, info_text = test_map[selection](df)
        else:
            filtered_df = df
            info_text = f"📄 Total: {len(df)} record."

        self.info_label.setText(info_text)
        self.update_table(filtered_df)
        self.update_summary_box(df)

    def update_summary_box(self, df):
        if df is None or df.empty:
            self.summary_table.setRowCount(0)
            return

        device_id = str(self.device_display.text().strip())
        summary_funcs = [
            ("Low Battery", self.tester.filter_battery_data),
            ("Low Signal", self.tester.filter_signal_data),
            ("Defect", self.tester.filter_defect_data),
            ("Malfunction", self.tester.filter_malfunction_data),
            ("Missed Data", self.tester.filter_missed_data),
            ("Log Data", self.tester.filter_status_log),
            ("Duplicate Data", self.tester.filter_duplicate_data),
            ("Acc Alert", self.tester.filter_acc_alert),
            ("Mainboard Internal Humidity", self.tester.filter_mainboard_humidity),
            ("Soil Sensor Internal Humidity", self.tester.filter_soilsensor_humidity),
        ]

        if self.selected_tests:
            summary_funcs = [item for item in summary_funcs if item[0] in self.selected_tests]

        self.summary_table.setRowCount(len(summary_funcs))

        for i, (name, func) in enumerate(summary_funcs):
            filtered_df, _ = func(df.copy())
            error_count = len(filtered_df)
            total_count = len(df)
            error_rate = f"{(error_count / total_count * 100):.2f}%" if total_count > 0 else "N/A"

            self.summary_table.setItem(i, 0, QTableWidgetItem(device_id))
            self.summary_table.setItem(i, 1, QTableWidgetItem(name))
            self.summary_table.setItem(i, 2, QTableWidgetItem(str(error_count)))
            self.summary_table.setItem(i, 3, QTableWidgetItem(str(total_count)))
            self.summary_table.setItem(i, 4, QTableWidgetItem(error_rate))

    def update_table(self, df):
        self.table.clear()
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        for i in range(len(df)):
            for j in range(len(df.columns)):
                item = QTableWidgetItem(str(df.iloc[i, j]))
                self.table.setItem(i, j, item)

    def copy_summary_to_clipboard(self):
        row_count = self.summary_table.rowCount()
        col_count = self.summary_table.columnCount()

        if row_count == 0 or col_count == 0:
            QMessageBox.warning(self, "Warning", "Summary table is empty.")
            return

        headers = [self.summary_table.horizontalHeaderItem(col).text() for col in range(col_count)]
        data_lines = ["\t".join(headers)]

        for row in range(row_count):
            row_data = []
            for col in range(col_count):
                item = self.summary_table.item(row, col)
                text = item.text() if item else ""
                row_data.append(text)
            data_lines.append("\t".join(row_data))

        final_text = "\n".join(data_lines)

        clipboard = QApplication.clipboard()
        clipboard.setText(final_text)

        QMessageBox.information(self, "Copied", "Summary table copied to clipboard.")

class DataTests:
    def filter_battery_data(self, df):
        print("Status: Running Battery Test...")
        if "Bat" not in df.columns:
            return df, "Warning: 'Bat' column not found."
        df["Bat"] = pd.to_numeric(df["Bat"], errors='coerce')
        filtered_df = df[df["Bat"] < 3.60]
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        filtered_df = sort_by_timestamp(filtered_df)
        return filtered_df, f"Low Battery: {len(filtered_df)}"

    def filter_signal_data(self, df):
        print("Status: Running Signal Test...")
        if "PWR" not in df.columns:
            return df, "Warning: 'PWR' column not found."
        filtered_df = df[df["PWR"] < -90]
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        filtered_df = sort_by_timestamp(filtered_df)
        return filtered_df, f"Low Signal: {len(filtered_df)}"

    def filter_defect_data(self, df):
        print("Status: Running Defect Test...")
        if "Defect Code" not in df.columns:
            return df, "Warning: 'Defect Code' column not found."
        df["Defect Code"] = pd.to_numeric(df["Defect Code"], errors="coerce")
        filtered_df = df[df["Defect Code"] != 0]
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        filtered_df = sort_by_timestamp(filtered_df)
        return filtered_df, f"Defect: {len(filtered_df)}"

    def filter_malfunction_data(self, df):
        print("Status: Running Malfunction Test...")
        if "Malfunction" not in df.columns:
            return df, "Warning: 'Malfunction' column not found."
        filtered_df = df[df["Malfunction"] != "0_0"]
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        filtered_df = sort_by_timestamp(filtered_df)
        return filtered_df, f"Malfunction: {len(filtered_df)}"

    def filter_mainboard_humidity(self, df, threshold=60):
        print("Status: Running Mainboard Humidity Test...")
        col = "Main Board PCB Humidity"
        if col not in df.columns:
            return df, f"Warning: '{col}' column not found."
        df[col] = pd.to_numeric(df[col], errors="coerce")
        filtered_df = df[df[col] > threshold]
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        filtered_df = sort_by_timestamp(filtered_df)
        return filtered_df, f"Mainboard Internal Humidity: {len(filtered_df)}"

    def filter_soilsensor_humidity(self, df, threshold=60):
        print("Status: Running Soil Sensor Humidity Test...")
        col = "Soil Moisture Sensor PCB Humidity"
        if col not in df.columns:
            return df, f"Warning: '{col}' column not found."
        df[col] = pd.to_numeric(df[col], errors="coerce")
        filtered_df = df[df[col] > threshold]
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        filtered_df = sort_by_timestamp(filtered_df)
        return filtered_df, f"Soil Sensor Internal Humidity: {len(filtered_df)}"

    def filter_duplicate_data(self, df):
        print("Status: Running Duplicate Data Test...")
        if "LogDate" not in df.columns:
            return df, "Error: 'LogDate' column not found."
        df = df.copy()
        df["LogDate"] = pd.to_datetime(df["LogDate"], errors="coerce")
        duplicates = []
        grouped = df.groupby("LogDate")
        for _, group in grouped:
            if len(group) > 1:
                duplicates.append(group.iloc[1:])
        filtered_df = pd.concat(duplicates) if duplicates else pd.DataFrame(columns=df.columns)
        filtered_df = sort_by_timestamp(filtered_df)
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        return filtered_df, f"Duplicated (only duplicates showed): {len(filtered_df)}"

    def filter_missed_data(self, df, threshold_seconds=3600):
        print("Status: Running Missed Data Test...")
        if "DeltaSeconds_TS" not in df.columns:
            df, _ = self.add_time_difference_column(df)
        missed = df[(df["DeltaSeconds_TS"] > threshold_seconds) & (df["Status"].astype(str).str.strip() == "2G")]
        rows = []
        MAX_MISSING_ROWS = 5000
        for idx, row in missed.iterrows():
            end_time = row["TimestampRounded"]
            missing_count = int((row["DeltaSeconds_TS"] - threshold_seconds) // threshold_seconds)
            for i in range(1, missing_count + 1):
                if len(rows) >= MAX_MISSING_ROWS:
                    break
                new_time = end_time + pd.to_timedelta(threshold_seconds * i, unit="s")
                new_row = {col: None for col in df.columns}
                new_row["TimestampRounded"] = new_time
                rows.append(new_row)
        missing_df = pd.DataFrame(rows, columns=df.columns)
        final_df = missing_df.copy() if not missing_df.dropna(how="all").empty else pd.DataFrame(columns=df.columns)
        final_df = sort_by_timestamp(final_df, column_name="TimestampRounded")
        err_rate = len(missing_df) / len(df) if len(df) > 0 else 0
        return final_df, f"Missing Data: {len(missing_df)}"

    def filter_acc_alert(self, df):
        print("Status: Running Accelerometer Alert Test...")
        if "Acc" not in df.columns:
            return df, "Warning: 'Acc' column not found."
        filtered_df = df[~df["Acc"].astype(str).str.startswith("[OK]")]
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        filtered_df = sort_by_timestamp(filtered_df)
        return filtered_df, f"Accelerometer Alert: {len(filtered_df)}"

    def filter_status_log(self, df):
        print("Status: Running Status Log Test...")
        if "Status" not in df.columns:
            return df, "Warning: 'Status' column not found."
        filtered_df = df[df["Status"].astype(str).str.lower().str.contains("log")]
        err_rate = len(filtered_df) / len(df) if len(df) > 0 else 0
        filtered_df = sort_by_timestamp(filtered_df)
        return filtered_df, f"Log Data: {len(filtered_df)}"

    def add_time_difference_column(self, df):
        print("Status: Calculating time differences...")
        df = df.copy()
        if "LogDate" in df.columns:
            df.loc[:, "LogDate"] = pd.to_datetime(df["LogDate"], errors="coerce")
            df["DeltaSeconds"] = df["LogDate"].diff().dt.total_seconds().fillna(0).abs().astype(int)
        if "TimestampRounded" in df.columns:
            df.loc[:, "TimestampRounded"] = pd.to_datetime(df["TimestampRounded"], errors="coerce")
            df["DeltaSeconds_TS"] = df["TimestampRounded"].diff().dt.total_seconds().fillna(0).abs().astype(int)
        return df, "Status: DeltaSeconds and DeltaSeconds_TS columns added."
