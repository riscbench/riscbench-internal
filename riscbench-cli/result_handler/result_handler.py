import sys
import os
import re
import matplotlib.pyplot as plt
import common

from .ila_handler import export_zoomed_waveforms

RECENT_RUN_PATH = ""

try:
    from PyQt5.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout, 
                                 QPushButton, QLabel, QFrame, QButtonGroup, QSizePolicy)
    from PyQt5.QtGui import QPixmap, QFont, QPainter
    from PyQt5.QtCore import Qt
except ImportError:
    print("\n" + "="*50)
    print("ERROR: PyQt5 is not installed in your Python environment.")
    print("Please install PyQt5 before running this application:")
    print("    pip install PyQt5")
    print("="*50 + "\n")
    sys.exit(1)

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)

    def setPixmap(self, pixmap):
        self.original_pixmap = pixmap
        super().setPixmap(QPixmap())  # Clear standard QLabel pixmap
        self.update()

    def setText(self, text):
        self.original_pixmap = None
        super().setText(text)
        self.update()

    def paintEvent(self, event):
        # Call superclass paintEvent to draw background/borders
        super().paintEvent(event)
        
        if self.original_pixmap and not self.original_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            
            # Get device pixel ratio for High DPI displays
            dpr = self.devicePixelRatioF()
            
            width = self.width()
            height = self.height()
            
            padding = 16
            avail_width = max(width - 2 * padding, 0)
            avail_height = max(height - 2 * padding, 0)
            
            if avail_width > 0 and avail_height > 0:
                # Scale using physical pixels for high quality
                scaled_width = int(avail_width * dpr)
                scaled_height = int(avail_height * dpr)
                
                scaled = self.original_pixmap.scaled(
                    scaled_width, scaled_height,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                
                # Tell the scaled pixmap its device pixel ratio
                scaled.setDevicePixelRatio(dpr)
                
                # Center the scaled image in logical coordinates
                logical_width = scaled.width() / dpr
                logical_height = scaled.height() / dpr
                x = int((width - logical_width) / 2)
                y = int((height - logical_height) / 2)
                painter.drawPixmap(x, y, scaled)
            painter.end()

class RiscBenchViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("RiscBench Results Viewer")
        self.resize(1100, 700)
        self.setMinimumSize(800, 500)
        
        # Main layout (horizontal)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar widget
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 30, 24, 30)
        sidebar_layout.setSpacing(12)
        
        # App Title
        title_label = QLabel("RiscBench")
        title_label.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title_label.setStyleSheet("color: #a855f7; margin-bottom: 2px;")
        
        subtitle_label = QLabel("Results Visualizer\n(Under Development v0.1)")
        subtitle_label.setFont(QFont("Segoe UI", 10))
        subtitle_label.setStyleSheet("color: #71717a; margin-bottom: 25px;")
        
        sidebar_layout.addWidget(title_label)
        sidebar_layout.addWidget(subtitle_label)
        
        # Button Group for exclusive selection
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        
        self.buttons = []
        button_info = [
            ("Waveform View #1"),
            ("Waveform View #2"),
            ("SIT Calculation"),
            ("FLOPs Profile\n(Disabled)"),
            ("Sweep Analysis\n(Disabled)")
        ]
        
        for i, name in enumerate(button_info):
            # Format text with line breaks for name and description
            btn = QPushButton(f"{name}")
            btn.setCheckable(True)
            btn.setFixedHeight(70)
            btn.setCursor(Qt.PointingHandCursor)
            
            # Map button click
            btn.clicked.connect(self.make_callback(i))
            
            if i >= 3:
                btn.setEnabled(False)
            
            sidebar_layout.addWidget(btn)
            self.btn_group.addButton(btn)
            self.buttons.append(btn)
            
        sidebar_layout.addStretch()
        
        # Footer in sidebar
        footer_label = QLabel("Status: Idle")
        footer_label.setFont(QFont("Segoe UI", 9))
        footer_label.setStyleSheet("color: #52525b;")
        sidebar_layout.addWidget(footer_label)
        
        # Right pane (Content container)
        self.content_frame = QFrame()
        self.content_frame.setObjectName("content_frame")
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(30, 30, 30, 30)
        
        # Image display area
        self.image_label = ImageLabel()
        self.image_label.setObjectName("image_label")
        self.image_label.setAlignment(Qt.AlignCenter)
        
        content_layout.addWidget(self.image_label)
        
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.content_frame)
        
        # QSS Stylesheet
        self.setStyleSheet("""
            QWidget {
                background-color: #09090b;
                color: #f4f4f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            
            #sidebar {
                background-color: #18181b;
                border-right: 1px solid #27272a;
            }
            
            #content_frame {
                background-color: #09090b;
            }
            
            #image_label {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 16px;
            }
            
            QPushButton {
                background-color: #27272a;
                color: #a1a1aa;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding-left: 20px;
                text-align: left;
                font-weight: bold;
                font-size: 13px;
                line-height: 1.4;
            }
            
            QPushButton:hover {
                background-color: #3f3f46;
                color: #f4f4f5;
                border-color: #52525b;
            }
            
            QPushButton:checked {
                background-color: #a855f7;
                color: #ffffff;
                border-color: #c084fc;
            }
            
            QPushButton:disabled {
                background-color: #18181b;
                color: #52525b;
                border-color: #27272a;
            }
        """)
        
        # Select first button by default and display image 1
        self.buttons[0].setChecked(True)
        self.active_idx = 0
        self.load_image(0)
        
    def make_callback(self, idx):
        return lambda: self.show_image(idx)
        
    def show_image(self, idx):
        self.active_idx = idx
        self.load_image(idx)
        
    def load_image(self, idx):
        global RECENT_RUN_PATH

        base_dir = RECENT_RUN_PATH
        image_name = f"image{idx+1}.png"
        image_path = os.path.join(base_dir, image_name)
        
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText(
                f"Visual Asset Not Found\n\n"
                f"Filename: {image_name}\n"
                f"Expected location:\n{image_path}\n\n"
                f"Please ensure the image is copied to this folder."
            )
            self.image_label.setStyleSheet("""
                #image_label {
                    background-color: #18181b;
                    color: #ef4444;
                    font-size: 15px;
                    font-weight: bold;
                    border: 1px solid #3f1a1a;
                    border-radius: 12px;
                    padding: 20px;
                }
            """)

def rh_ui(recent_run_path):
    global RECENT_RUN_PATH

    RECENT_RUN_PATH = recent_run_path

    # Enable High DPI scaling and high-resolution pixmaps before QApplication is created
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    viewer = RiscBenchViewer()
    viewer.show()
    sys.exit(app.exec_())

def rh_processor():
    print("Processing results from latest run...")

    target_ranges = [
        (1000, 2500),   # Range 1 -> Exports as image1.png
        (15000, 3000)   # Range 2 -> Exports as image2.png
    ]

    export_zoomed_waveforms(
        csv_file=f"{common.env.run_path}/ila_captured_data.csv", 
        sample_ranges=target_ranges,
        clk_period_ns=10.0  # 10ns clock period (100MHz)
    )

    generate_uart_plot(f"{common.env.run_path}/UART_results.csv", f"{common.env.run_path}/image3.png")
    

def generate_uart_plot(log_input, output_path=f"{common.env.run_path}/image3.png"):
 
    # Load lines either from file or raw string
    if os.path.isfile(log_input):
        with open(log_input, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    else:
        lines = log_input.strip().splitlines()

    # Regex pattern to match table rows: Vector Size | Cycles | Time (us) | MOPS
    row_pattern = re.compile(r'^\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)')

    vector_sizes = []
    mops_values = []

    for line in lines:
        # Strip timestamp prefix if present before first comma
        content = line.split(',', 1)[1] if ',' in line else line
        
        match = row_pattern.match(content)
        if match:
            v_size, _cycles, _time_us, mops = match.groups()
            vector_sizes.append(int(v_size))
            mops_values.append(float(mops))

    if not vector_sizes:
        raise ValueError("No valid benchmark data found in the input log.")

    # Create destination directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Plotting
    plt.figure(figsize=(10, 5))
    plt.plot(vector_sizes, mops_values, marker='o', color='#1f77b4', linewidth=2, label='MOPS')
    
    # Use logarithmic base 2 x-axis scaling for power-of-2 vector sizes
    plt.xscale('log', base=2)
    plt.xticks(vector_sizes, labels=[str(v) for v in vector_sizes], rotation=45)
    
    plt.title('WILL BE UPDATED', fontsize=12, fontweight='bold')
    plt.xlabel('Vector Size (Elements)', fontsize=10)
    plt.ylabel('MOPS (Million Operations / Sec)', fontsize=10)
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.tight_layout()

    plt.savefig(output_path, dpi=300)
    plt.close()
    
    print(f"Plot saved successfully to {output_path}")

