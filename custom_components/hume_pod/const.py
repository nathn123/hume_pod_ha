"""Constants for the Hume Body Pod integration."""

from __future__ import annotations

DOMAIN = "hume_pod"
MANUFACTURER = "Hume Health"
MODEL = "Body Pod"
MODEL_PERSON = "Body Pod profile"

SUBENTRY_PERSON = "person"

# Person subentry data
CONF_SEX = "sex"
CONF_BIRTHDATE = "birthdate"
CONF_HEIGHT = "height"
CONF_ACTIVITY = "activity"
CONF_EXPECTED_WEIGHT = "expected_weight"

# Scale entry options
CONF_WEIGHT_TOLERANCE = "weight_tolerance"
CONF_FAT_TOLERANCE = "fat_tolerance"
DEFAULT_WEIGHT_TOLERANCE = 3.0  # kg
DEFAULT_FAT_TOLERANCE = 4.0  # percentage points
# Which impedance band feeds the composition equations (see README).
CONF_IMPEDANCE_INPUT = "impedance_input"
IMPEDANCE_INPUT_OPTIONS = ["low_band", "high_band"]
DEFAULT_IMPEDANCE_INPUT = "low_band"
# Opt-in CSV log of raw BLE frames (see raw_store.py and the README).
CONF_LOG_RAW_PACKETS = "log_raw_packets"
DEFAULT_LOG_RAW_PACKETS = False
# Optional per-person webhook (see webhook.py and the README): when a person's
# profile carries a URL, their weigh-ins are POSTed there. Empty URL = off.
CONF_WEBHOOK_URL = "webhook_url"
CONF_WEBHOOK_TOKEN = "webhook_token"
WEBHOOK_TIMEOUT = 10  # seconds

SEX_MALE = "male"
SEX_FEMALE = "female"

ACTIVITY_LEVELS = ["sedentary", "moderate", "active"]

# Seconds
SESSION_TIMEOUT = 120
POST_IMPEDANCE_GRACE = 5
NO_DATA_TIMEOUT = 60  # connected but silent -> give up and say so
WARNING_INTERVAL = 600  # don't repeat the same kind of warning more than every 10 min
COOLDOWN_AFTER_SESSION = 45

STORAGE_VERSION = 1

EVENT_MEASUREMENT = f"{DOMAIN}_measurement"

SERVICE_ASSIGN = "assign_weigh_in"
SERVICE_DISCARD = "discard_weigh_in"
ATTR_PERSON = "person"
ATTR_SCALE = "scale"

# Dispatched whenever any scale's data changes (used by the dashboard card feed)
SIGNAL_UPDATED = f"{DOMAIN}_updated"

FRONTEND_URL_BASE = f"/{DOMAIN}_static"
CARD_FILENAME = "hume-pod-card.js"
