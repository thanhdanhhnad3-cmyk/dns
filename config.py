"""
Configuration for NextDNS Auto-Register Tool
"""
import os

# NextDNS API
NEXTDNS_BASE_URL = "https://api.nextdns.io"
NEXTDNS_WEB_URL = "https://my.nextdns.io"
NEXTDNS_LOGIN_URL = f"{NEXTDNS_BASE_URL}/accounts/@login"
NEXTDNS_ME_URL = f"{NEXTDNS_BASE_URL}/accounts/@me"
NEXTDNS_ACCOUNT_URL = f"{NEXTDNS_WEB_URL}/account"

# Tinyhost API
TINYHOST_BASE_URL = "https://tinyhost.shop"
TINYHOST_RANDOM_DOMAINS_URL = f"{TINYHOST_BASE_URL}/api/random-domains/"
TINYHOST_INBOX_URL = f"{TINYHOST_BASE_URL}/api/email/{{domain}}/{{user}}/"

# Defaults
DEFAULT_PASSWORD_CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_PASSWORD_LENGTH = 14

# Timing
EMAIL_POLL_INTERVAL = 3      # seconds between email checks
EMAIL_POLL_TIMEOUT = 120     # max seconds to wait for email

# Output
OUTPUT_FILE = "api_keys.txt"
LOG_FILE = "nextdns_tool.log"
