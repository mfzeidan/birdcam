# Birdcam - Bird Feeder Camera System

A Raspberry Pi 5 camera system that watches bird feeders, captures photos when
motion is detected, and uses Claude AI to identify bird species. Non-bird photos
are automatically deleted, so the gallery only shows confirmed bird sightings.

## Quick Access

- **Web App:** http://birdcam.local:5000
- **Live Feed:** http://birdcam.local:5000/stream
- **SSH:** `ssh <user>@birdcam.local`

## How It Works

1. Camera watches the bird feeders via live video stream
2. Motion detection compares frames and triggers on significant changes
3. When motion is detected, a photo is captured
4. The photo is sent to Claude AI (Sonnet) for bird identification
5. If a bird is detected: saved to gallery with species label
6. If no bird (wind, etc.): photo is automatically deleted

**Cost control:** Claude Vision only runs during active hours (default 6:45 AM –
6:30 PM). Outside that window, motion captures are skipped entirely so no API
calls are made overnight.

## Common Tasks

### View the web app
Open http://birdcam.local:5000 in any browser on the same WiFi network.

### Adjust motion sensitivity
1. Open the web app
2. Click **Settings** button
3. Use the sliders:
   - **Adaptive Multiplier**: Higher = less sensitive (default 8x). If too many
     wind triggers, increase this. If birds are being missed, decrease it.
   - **Cooldown**: Minimum seconds between captures (default 15s)
   - **Min MSE Threshold**: Minimum motion level to consider (default 15)
4. Click **Apply Settings** — changes take effect immediately and persist

### Check camera angle
Click **Check Angle** on the web app. Claude will analyze the current view and
suggest improvements for better bird identification.

### Restart the service
```bash
sudo systemctl restart birdcam
```

### Check if it's running
```bash
sudo systemctl status birdcam
```

### View logs
```bash
# Recent logs
sudo journalctl -u birdcam -n 50 --no-pager

# Follow logs live
sudo journalctl -u birdcam -f

# Just bird detections
sudo journalctl -u birdcam | grep BIRD
```

### Stop/Start the service
```bash
sudo systemctl stop birdcam
sudo systemctl start birdcam
```

## Configuration

All settings are in `~/birdcam/config.yaml`. Edit with:
```bash
nano ~/birdcam/config.yaml
```
Then restart: `sudo systemctl restart birdcam`

### Key settings

| Setting | File Location | What It Does |
|---------|--------------|--------------|
| `motion.adaptive_multiplier` | config.yaml | How far above baseline motion must spike to trigger (8 = 8x) |
| `motion.cooldown_seconds` | config.yaml | Min seconds between captures |
| `motion.mse_threshold` | config.yaml | Absolute minimum motion level |
| `camera.scaler_crop` | config.yaml | Digital zoom region `[x, y, width, height]` |
| `vision.enabled` | config.yaml | true/false to enable Claude bird ID |
| `vision.model` | config.yaml | Which Claude model to use |
| `vision.active_start` | config.yaml | Time vision turns on (default `"06:45"` = 6:45 AM) |
| `vision.active_end` | config.yaml | Time vision turns off (default `"18:30"` = 6:30 PM) |
| `storage.max_photos` | config.yaml | Max photos before oldest are deleted |

### API Key

The Claude API key is stored in `~/birdcam/.env`:
```
ANTHROPIC_API_KEY=<your-key-here>
```

## File Structure

```
~/birdcam/
├── app.py              # Main entry point
├── camera.py           # Camera management (picamera2)
├── motion.py           # Motion detection (adaptive threshold)
├── storage.py          # Photo storage and metadata
├── vision.py           # Claude AI bird identification
├── web.py              # Flask web server and API
├── config.py           # Configuration loader
├── config.yaml         # All tunable settings
├── .env                # API key (secret)
├── metadata.json       # Photo metadata database
├── captures/           # Full-size bird photos
│   └── thumbs/         # Gallery thumbnails
├── templates/          # HTML templates
├── static/             # CSS
├── venv/               # Python virtual environment
├── birdcam.log         # Application log file
└── birdcam.service     # systemd service definition
```

## Setup

### Static IP (optional)
To set a static IP on the Pi's WiFi connection:
```bash
sudo nmcli connection modify '<WIFI_SSID>' ipv4.method manual ipv4.addresses <IP>/24 ipv4.gateway <GATEWAY> ipv4.dns <DNS>
sudo nmcli connection up '<WIFI_SSID>'
```

### Systemd service
Copy the service file and enable it:
```bash
sudo cp ~/birdcam/birdcam.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now birdcam
```

## Troubleshooting

### Web app not loading
1. Check if service is running: `sudo systemctl status birdcam`
2. Check for errors: `sudo journalctl -u birdcam -n 20`
3. Restart: `sudo systemctl restart birdcam`

### Camera not working
1. Check if camera is detected: `rpicam-hello --list-cameras`
2. Make sure no other process is using the camera
3. Restart the service

### Too many false triggers (wind)
Increase the adaptive multiplier via the web Settings panel or in config.yaml.

### Not catching birds
Decrease the adaptive multiplier. Also check that the camera angle covers
the feeders — use the "Check Angle" button.

### Claude API errors
1. Check the API key in `~/birdcam/.env`
2. Check your Anthropic account has credits
3. Look at logs: `sudo journalctl -u birdcam | grep Vision`
