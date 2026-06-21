import os
from dotenv import load_dotenv

load_dotenv()

AGENT_CONFIGS = {
    "conductor":   {"agent_id": os.environ["ConductorID"],   "api_key": os.environ["ConductorBandAPI"]},
    "upper_left":  {"agent_id": os.environ["UpperleftID"],   "api_key": os.environ["UpperleftBandAPI"]},
    "upper_right": {"agent_id": os.environ["UpperRightID"],  "api_key": os.environ["UpperRightBandAPI"]},
    "lower":       {"agent_id": os.environ["LowerID"],       "api_key": os.environ["LowerBandAPI"]},
    "threat":      {"agent_id": os.environ["ThreatID"],      "api_key": os.environ["ThreatBandAPI"]},
    "spine":       {"agent_id": os.environ["SpineID"],       "api_key": os.environ["SpineBandAPI"]},
}

WS_URL = "wss://app.band.ai/api/v1/socket/websocket"
REST_URL = "https://app.band.ai"
