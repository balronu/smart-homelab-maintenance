"""Constants for the offline-testable Home Assistant adapter."""

DOMAIN = "smart_homelab_maintenance"
VERSION = "0.1.0-beta.21"
CARD_VERSION = VERSION
AGENT_API_CONTRACT = "1.1"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 3600
CONF_AGENT_URL = "agent_url"
CONF_TOKEN = "token"
CONF_CA_FILE = "ca_file"
CONF_SCAN_INTERVAL = "scan_interval"
ACTIONS = ("check", "preflight", "get_job", "get_job_events", "dry_run")
