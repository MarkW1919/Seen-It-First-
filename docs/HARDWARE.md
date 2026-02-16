# RepoScan Pro - Hardware Guide

## NVIDIA Jetson Orin Nano Super (8GB)

### Specifications
- **GPU**: 1024 CUDA cores + 32 Tensor Cores (Ampere)
- **CPU**: 6-core Arm Cortex-A78AE
- **RAM**: 8GB LPDDR5
- **AI Performance**: 67 TOPS (INT8)
- **Power**: 7W-15W configurable
- **Storage**: NVMe SSD slot (M.2 Key M)

### Power Modes
```bash
# MAXN mode (15W) - recommended for scanning
sudo nvpmodel -m 0
sudo jetson_clocks

# 15W mode with power-saving
sudo nvpmodel -m 1

# Check current mode
nvpmodel -q
```

### Memory Budget
| Component | RAM Usage |
|-----------|-----------|
| System/OS | ~1.0 GB |
| YOLOv8n Vehicle Det | ~0.5 GB |
| YOLOv8n Plate Det | ~0.5 GB |
| CRNN OCR | ~0.2 GB |
| EfficientNet YMM | ~0.3 GB |
| DeepSORT Tracker | ~0.2 GB |
| PostgreSQL | ~0.5 GB |
| Redis | ~0.1 GB |
| Backend + Frontend | ~0.3 GB |
| **Total** | **~3.6 GB** |
| **Available Buffer** | **~4.4 GB** |

## Sony Starvis 2 IMX685 Camera

### Specifications
- **Sensor**: 1/1.2" CMOS, Starvis 2 technology
- **Resolution**: 4K (3840x2160) / 1080p for LPR
- **Interface**: MIPI CSI-2 (4 lanes)
- **Sensitivity**: 0.001 lux (with IR)
- **Dynamic Range**: 90 dB (HDR mode)
- **Frame Rate**: 60fps @ 1080p, 30fps @ 4K

### Connection
```
Jetson Orin Nano       IMX685 Camera
┌──────────────┐      ┌──────────────┐
│  CSI-2 Port  │──────│  MIPI Out    │
│  (22-pin)    │      │  (15/22-pin) │
│              │      │              │
│  I2C (ctrl)  │──────│  I2C (cfg)   │
│  GPIO 18     │──────│  IR LED PWR  │
│  GPIO 23     │──────│  IR Cut Filt │
└──────────────┘      └──────────────┘
```

### Verify Camera
```bash
# Check if camera is detected
v4l2-ctl --list-devices

# Test CSI camera capture
gst-launch-1.0 nvarguscamerasrc sensor-id=0 \
  ! 'video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1' \
  ! nvvidconv ! xvimagesink
```

## PTZ Assembly (Optional)

### Components
- Pan motor: Nema 17 stepper or 28BYJ-48
- Tilt motor: SG90/MG996R servo
- RS-485 adapter: USB-to-RS-485 converter
- Protocol: Pelco-D at 9600 baud

### Wiring
```
Jetson USB     RS-485 Adapter    PTZ Motor Controller
┌─────────┐   ┌──────────────┐  ┌───────────────────┐
│ USB Port│───│ USB  │ A+ B- │──│ RS-485 In         │
└─────────┘   └──────────────┘  │ Motor Connections  │
                                └───────────────────┘
```

## Vehicle Installation

### Power
- 12V vehicle power → 5V/4A DC-DC converter → Jetson barrel jack
- Use automotive-grade fuse and voltage regulator
- Connect to always-on or ACC-switched circuit based on preference

### Mounting
- Mount camera behind windshield (upper center or passenger side)
- Angle camera slightly downward (5-10 degrees) for plate visibility
- Ensure clear view of oncoming and parked vehicles
- IR illuminators should face forward for night operation

### Thermal
- Ensure adequate ventilation around Jetson enclosure
- Operating range: -25°C to 50°C (with heatsink)
- Monitor GPU temperature via system dashboard
- Thermal throttling begins at 97°C
