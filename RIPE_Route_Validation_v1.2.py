import json
import urllib.request
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import pytz
import streamlit as st
import time  # Add this to imports if not present

# Configuration
PREFIX_CONFIG = {
    "171.18.48.0/24": {"color": "royalblue", "label": "48.0/24"},
    "171.18.49.0/24": {"color": "forestgreen", "label": "49.0/24"},
    "171.18.50.0/24": {"color": "deepskyblue", "label": "50.0/24"},
    "171.18.51.0/24": {"color": "lightgreen", "label": "51.0/24"},
    "171.18.48.0/23": {"color": "red", "label": "48.0/23"},
    "171.18.50.0/23": {"color": "orange", "label": "50.0/23"}
}

PREFIXES = list(PREFIX_CONFIG.keys())

VALID_UPSTREAMS = {
    "171.18.48.0/24": ["AS3758"],
    "171.18.49.0/24": ["AS17645"],
    "171.18.50.0/24": ["AS3758"],
    "171.18.51.0/24": ["AS17645"],
    "171.18.48.0/23": ["AS3758", "AS17645"],
    "171.18.50.0/23": ["AS3758", "AS17645"]
}

ASN_PATTERNS = {
    'AS10236': {'hatch': '', 'label': 'AS10236 (solid)'},
    'AS19905': {'hatch': '//', 'label': 'AS19905 (diagonal)'},
    'OTHER': {'hatch': '..', 'label': 'Other ASNs (dotted)'},
    'AS3758': {'hatch': '', 'label': 'AS3758 (solid)'},
    'AS17645': {'hatch': '//', 'label': 'AS17645 (diagonal)'}
}

class DataStorage:
    def __init__(self, max_points=15):
        self.max_points = max_points
        self.timestamps = []
        self.stats_history = []
        
    def add_stats(self, stats, timestamp):
        # Only add if timestamp is different from last one
        if not self.timestamps or timestamp != self.timestamps[-1]:
            self.timestamps.append(timestamp)
            self.stats_history.append(stats)
            
            if len(self.timestamps) > self.max_points:
                self.timestamps.pop(0)
                self.stats_history.pop(0)
            
    def get_stats(self, index):
        if 0 <= index < len(self.stats_history):
            return self.stats_history[index]
        return None

def get_sgt_time():
    """Convert current UTC time to SGT"""
    utc_time = datetime.now(pytz.UTC)
    sgt = pytz.timezone('Asia/Singapore')
    return utc_time.astimezone(sgt)

def analyze_bgp_data(data, prefix):
    """Analyze BGP data for a single prefix"""
    stats = {
        'total_paths': 0,
        'AS10236': 0,
        'AS19905': 0,
        'OTHER': 0,
        'AS3758': 0,
        'AS17645': 0
    }

    valid_upstreams = VALID_UPSTREAMS[prefix]

    for rrc in data['data']['rrcs']:
        peers = rrc['peers']
        stats['total_paths'] += len(peers)

        for peer in peers:
            # Origin ASN counting
            if peer['asn_origin'] == '10236':
                stats['AS10236'] += 1
            elif peer['asn_origin'] == '19905':
                stats['AS19905'] += 1
            else:
                stats['OTHER'] += 1

            # Upstream ASN counting
            as_path = peer['as_path'].split()
            if len(as_path) >= 2:
                i = len(as_path) - 2
                while i >= 0 and as_path[i] == peer['asn_origin']:
                    i -= 1
                if i >= 0:
                    second_last = as_path[i]
                    if second_last == '3758' and 'AS3758' in valid_upstreams:
                        stats['AS3758'] += 1
                    elif second_last == '17645' and 'AS17645' in valid_upstreams:
                        stats['AS17645'] += 1

    return stats

def update_plots(new_stats, timestamp, time_to_next):
    """Update plots for Streamlit"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12))
    fig.suptitle('BGP Analysis Dashboard\nAll times in SGT (UTC+8)', fontsize=16, y=0.95)
    
    # Use session state data stores
    data_stores = st.session_state.data_stores
    
    # Plot existing data
    bar_width, timeframe_gap, bar_gap = 0.01, 0.02, 0.00
    
    # Get timestamps from first prefix's data store
    timestamps = data_stores[PREFIXES[0]].timestamps
    if not timestamps:
        st.warning("No data available yet. First update in progress...")
        return
        
    # ... rest of your plotting code ...

    # Update status info
    status_text = (
        f'Last Updated: {timestamp} SGT | '
        f'Next update in: {time_to_next} seconds | '
        f'Updates: {st.session_state.update_counter}'
    )
    plt.figtext(0.02, 0.02, status_text, ha='left', va='bottom', fontsize=10)
    
    st.pyplot(fig)
    plt.close('all')

def fetch_and_analyze_bgp():
    """Fetch and analyze BGP data for all prefixes"""
    sgt_time = get_sgt_time()
    timestamp = sgt_time.strftime('%H:%M')
    all_stats = {}
    
    for prefix in PREFIXES:
        url = f"https://stat.ripe.net/data/looking-glass/data.json?resource={prefix}"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode('utf-8'))
                all_stats[prefix] = analyze_bgp_data(data, prefix)
        except Exception as e:
            st.error(f"Error analyzing {prefix}: {str(e)}")
            all_stats[prefix] = None

    update_plots(all_stats, timestamp, 0)
    return all_stats

def main():
    """Main Streamlit application"""
    st.set_page_config(page_title="BGP Analysis Dashboard", layout="wide")
    st.title("BGP Analysis Dashboard")

    # Initialize or get session state
    if 'init' not in st.session_state:
        st.session_state.init = True
        st.session_state.data_stores = {prefix: DataStorage() for prefix in PREFIXES}
        st.session_state.update_time = get_sgt_time() - timedelta(minutes=2)
        st.session_state.update_counter = 0
    
    # Create placeholder for plots
    plot_placeholder = st.empty()
    
    # Get current time and check if update is needed
    current_time = get_sgt_time()
    time_since_last_update = (current_time - st.session_state.update_time).seconds
    time_to_next = max(0, 120 - time_since_last_update)

    # Update data if needed
    if time_since_last_update >= 120:
        try:
            with st.spinner('Fetching BGP data...'):
                all_stats = fetch_and_analyze_bgp()
                if any(all_stats.values()):
                    timestamp = current_time.strftime('%H:%M')
                    
                    # Update data stores
                    for prefix in PREFIXES:
                        if all_stats[prefix]:
                            st.session_state.data_stores[prefix].add_stats(
                                all_stats[prefix], timestamp
                            )
                    
                    st.session_state.update_time = current_time
                    st.session_state.update_counter += 1

                    # Update display
                    with plot_placeholder:
                        update_plots(all_stats, timestamp, 120)
        except Exception as e:
            st.error(f"Update failed: {str(e)}")
    else:
        # Just update the display with existing data
        with plot_placeholder:
            timestamp = current_time.strftime('%H:%M')
            update_plots(None, timestamp, time_to_next)

    # Add auto-refresh using Streamlit's native functionality
    time.sleep(1)
    st.rerun()

if __name__ == "__main__":
    main()