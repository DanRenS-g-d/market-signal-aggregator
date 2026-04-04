"""
Marine Traffic Module — AIS Vessel Tracking
Uses aisstream.io WebSocket API (free) to monitor:
- Oil tanker congestion near Colombian ports (EC, GPRK signal)
- Tanker traffic at global chokepoints (Hormuz, Suez)
- Bulk carrier activity near Brazilian ports (EWZ signal)
- Container traffic near Korean/Taiwan ports (EWY/EWT signal)
 
Signal logic:
- High tanker congestion near Colombia → bearish EC (supply backed up)
- Low tanker activity → bullish EC (demand flowing)
- Blocked chokepoint → bullish EC/GPRK (supply disruption = price spike)
"""
 
import os, sys, json, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
AISSTREAM_API_KEY = os.environ.get("AISSTREAM_API_KEY", "351428cce9792853680a1009dd3df6256631334c")
 
# ── Bounding boxes for key maritime zones ─────────────────────
ZONES = {
    # Colombia oil ports
    "colombia_caribbean": {
        "bbox":    [[9.0, -76.5], [11.5, -74.0]],  # Cartagena, Barranquilla
        "tickers": ["EC", "GPRK"],
        "type":    "oil_export",
    },
    "colombia_pacific": {
        "bbox":    [[3.5, -77.5], [6.0, -76.5]],   # Buenaventura
        "tickers": ["EC"],
        "type":    "oil_export",
    },
    # Global oil chokepoints
    "strait_of_hormuz": {
        "bbox":    [[25.5, 56.0], [27.0, 57.5]],
        "tickers": ["EC", "GPRK"],
        "type":    "chokepoint",
    },
    "suez_canal": {
        "bbox":    [[29.5, 32.0], [31.5, 33.0]],
        "tickers": ["EC", "GPRK", "EWZ"],
        "type":    "chokepoint",
    },
    # Brazil ports (EWZ)
    "brazil_santos": {
        "bbox":    [[-24.5, -46.5], [-23.5, -45.5]],
        "tickers": ["EWZ"],
        "type":    "bulk_export",
    },
    # Korea/Taiwan ports (EWY/EWT)
    "korea_busan": {
        "bbox":    [[34.8, 128.8], [35.5, 129.5]],
        "tickers": ["EWY"],
        "type":    "container",
    },
    "taiwan_kaohsiung": {
        "bbox":    [[22.4, 120.1], [22.8, 120.4]],
        "tickers": ["EWT"],
        "type":    "container",
    },
}
 
# Vessel types to track per zone type
VESSEL_TYPES_BY_ZONE = {
    "oil_export":  [80, 81, 82, 83, 84],   # tanker types
    "chokepoint":  [80, 81, 82, 83, 84],
    "bulk_export": [70, 71, 72, 73, 74, 75, 76, 77, 78, 79],  # bulk carriers
    "container":   [70, 71, 72, 73, 74, 75, 76, 77, 78, 79],
}
 
# Congestion thresholds (vessels in zone)
CONGESTION_HIGH = 15   # >15 vessels = high congestion
CONGESTION_LOW  = 3    # <3 vessels = very low activity
 
 
async def fetch_zone_vessels(zone_name: str, zone_config: dict,
                              duration_seconds: int = 30) -> list:
    """
    Connect to aisstream.io WebSocket and collect vessel data
    for a specific geographic zone.
    """
    import websockets
 
    vessels = []
    bbox    = zone_config["bbox"]
 
    subscribe_msg = {
        "APIKey":       AISSTREAM_API_KEY,
        "BoundingBoxes": [bbox],
        "FilterMessageTypes": ["PositionReport"],
    }
 
    try:
        async with websockets.connect("wss://stream.aisstream.io/v0/stream",
                                       ping_interval=20) as ws:
            await ws.send(json.dumps(subscribe_msg))
 
            deadline = asyncio.get_event_loop().time() + duration_seconds
            while asyncio.get_event_loop().time() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
 
                    if data.get("MessageType") == "PositionReport":
                        meta    = data.get("MetaData", {})
                        pos     = data.get("Message", {}).get("PositionReport", {})
                        ship_type = meta.get("ShipType", 0)
 
                        vessels.append({
                            "mmsi":      meta.get("MMSI"),
                            "name":      meta.get("ShipName", "Unknown").strip(),
                            "lat":       pos.get("Latitude"),
                            "lon":       pos.get("Longitude"),
                            "speed":     pos.get("Sog", 0),       # speed over ground
                            "status":    pos.get("NavigationalStatus", 0),
                            "ship_type": ship_type,
                        })
 
                except asyncio.TimeoutError:
                    break
                except Exception:
                    break
 
    except Exception as e:
        print(f"    [AIS] Error in zone {zone_name}: {e}")
 
    return vessels
 
 
def analyze_zone(zone_name: str, zone_config: dict, vessels: list) -> dict:
    """Analyze vessel data and generate trading signal."""
    zone_type    = zone_config["type"]
    allowed_types = VESSEL_TYPES_BY_ZONE.get(zone_type, [])
 
    # Filter relevant vessel types
    relevant = [v for v in vessels
                if v["ship_type"] in allowed_types or not allowed_types]
 
    # Count anchored vs moving vessels
    anchored = [v for v in relevant if v.get("status") == 1]  # 1 = anchored
    moving   = [v for v in relevant if v.get("speed", 0) > 0.5]
    total    = len(relevant)
 
    # Congestion signal
    if total > CONGESTION_HIGH:
        congestion = "high"
    elif total < CONGESTION_LOW:
        congestion = "low"
    else:
        congestion = "normal"
 
    # Anchoring ratio — high anchoring = vessels waiting = congestion
    anchor_ratio = len(anchored) / total if total > 0 else 0
 
    # Generate signal per zone type
    if zone_type in ("oil_export", "chokepoint"):
        if congestion == "high" and anchor_ratio > 0.4:
            signal    = "bearish"   # backed up supply
            signal_str = "bearish — high tanker congestion"
        elif congestion == "low":
            signal    = "bullish"   # demand flowing, low supply backup
            signal_str = "bullish — low tanker activity, demand flowing"
        elif zone_type == "chokepoint" and congestion == "high":
            signal    = "bullish"   # blocked chokepoint = supply disruption
            signal_str = "bullish — chokepoint congestion, supply disruption"
        else:
            signal    = "neutral"
            signal_str = "neutral — normal traffic"
 
    elif zone_type in ("bulk_export", "container"):
        if congestion == "high":
            signal    = "bullish"   # high activity = strong demand
            signal_str = "bullish — high port activity, strong demand"
        elif congestion == "low":
            signal    = "bearish"   # low activity = weak demand
            signal_str = "bearish — low port activity, weak demand"
        else:
            signal    = "neutral"
            signal_str = "neutral — normal traffic"
    else:
        signal     = "neutral"
        signal_str = "neutral"
 
    return {
        "zone":         zone_name,
        "tickers":      zone_config["tickers"],
        "total_vessels": total,
        "anchored":     len(anchored),
        "moving":       len(moving),
        "congestion":   congestion,
        "anchor_ratio": round(anchor_ratio, 2),
        "signal":       signal,
        "signal_str":   signal_str,
    }
 
 
def aggregate_ticker_signals(zone_results: list) -> dict:
    """
    Combine signals from multiple zones per ticker.
    If majority of zones are bullish → bullish overall.
    """
    ticker_votes = {}
 
    for zone in zone_results:
        for ticker in zone["tickers"]:
            if ticker not in ticker_votes:
                ticker_votes[ticker] = {"bullish": 0, "bearish": 0, "neutral": 0, "zones": []}
            ticker_votes[ticker][zone["signal"]] += 1
            ticker_votes[ticker]["zones"].append(zone["zone"])
 
    ticker_signals = {}
    for ticker, votes in ticker_votes.items():
        total   = votes["bullish"] + votes["bearish"] + votes["neutral"]
        if votes["bullish"] > votes["bearish"]:
            signal = "bullish"
            conf   = round(votes["bullish"] / total, 2)
        elif votes["bearish"] > votes["bullish"]:
            signal = "bearish"
            conf   = round(votes["bearish"] / total, 2)
        else:
            signal = "neutral"
            conf   = 0.0
 
        ticker_signals[ticker] = {
            "signal":     signal,
            "confidence": conf,
            "votes":      votes,
        }
 
    return ticker_signals
 
 
def run_marine_traffic() -> dict:
    """
    Main entry point — runs all zone monitoring and returns signals.
    Uses asyncio to run WebSocket connections.
    """
    print(f"\n[Marine Traffic] Scanning {len(ZONES)} maritime zones...")
 
    async def run_all():
        zone_results = []
        for zone_name, zone_config in ZONES.items():
            print(f"    [AIS] Scanning {zone_name}...")
            vessels = await fetch_zone_vessels(zone_name, zone_config,
                                               duration_seconds=20)
            result  = analyze_zone(zone_name, zone_config, vessels)
            zone_results.append(result)
            print(f"    [AIS] {zone_name}: {result['total_vessels']} vessels "
                  f"— {result['signal_str']}")
        return zone_results
 
    try:
        zone_results    = asyncio.run(run_all())
        ticker_signals  = aggregate_ticker_signals(zone_results)
 
        print(f"\n    [Marine] Ticker signals:")
        for ticker, data in ticker_signals.items():
            print(f"    [Marine] {ticker}: {data['signal']} (conf={data['confidence']:.2f})")
 
        return {
            "zones":   zone_results,
            "tickers": ticker_signals,
        }
 
    except Exception as e:
        print(f"    [Marine Traffic] Error (non-fatal): {e}")
        return {}
 
 
def format_marine_for_telegram(marine_data: dict) -> str:
    """Format marine traffic signals for Telegram."""
    if not marine_data or not marine_data.get("tickers"):
        return ""
 
    significant = {k: v for k, v in marine_data["tickers"].items()
                   if v["signal"] != "neutral"}
    if not significant:
        return ""
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚢 <b>MARINE TRAFFIC SIGNAL</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Oil tanker & cargo vessel activity</i>")
 
    for ticker, data in significant.items():
        emoji = "📈" if data["signal"] == "bullish" else "📉"
        lines.append(f"\n{emoji} <b>{ticker}</b>: {data['signal'].upper()} "
                     f"(conf={int(data['confidence']*100)}%)")
 
    # Show notable zone events
    zones = marine_data.get("zones", [])
    notable = [z for z in zones
               if z["signal"] != "neutral" and z["total_vessels"] > 0]
    if notable:
        lines.append("")
        for z in notable[:3]:
            lines.append(f"  {z['zone']}: {z['total_vessels']} vessels — {z['signal_str']}")
 
    lines.append("")
    lines.append("<i>Source: AIS vessel tracking data</i>")
    return "\n".join(lines)
 
 
if __name__ == "__main__":
    result = run_marine_traffic()
    print(format_marine_for_telegram(result))