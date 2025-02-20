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

def update_plots(all_stats, timestamp, time_to_next):
    """Update plots for Streamlit"""
    # Ensure we're using global data_stores
    global data_stores
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12))
    fig.suptitle('BGP Analysis Dashboard\nAll times in SGT (UTC+8)', fontsize=16, y=0.95)
    
    # Update data stores before plotting
    if all_stats:  # Only update if we have new stats
        for prefix in PREFIXES:
            if all_stats[prefix]:  # Check if stats exist for this prefix
                data_stores[prefix].add_stats(all_stats[prefix], timestamp)
    
    bar_width, timeframe_gap, bar_gap = 0.01, 0.02, 0.00
    
    timestamps = data_stores[PREFIXES[0]].timestamps
    x_positions = np.arange(len(timestamps)) * (len(PREFIXES) * (bar_width + bar_gap) + timeframe_gap)
    
    prefix_handles = []
    pattern_handles_origin = []
    pattern_handles_upstream = []
    
    for t_idx, _ in enumerate(timestamps):
        base_pos = x_positions[t_idx]
        
        for p_idx, prefix in enumerate(PREFIXES):
            stats = data_stores[prefix].get_stats(t_idx)
            if not stats:
                continue
                
            pos = base_pos + p_idx * (bar_width + bar_gap)
            color = PREFIX_CONFIG[prefix]["color"]
            
            # Plot stacked bars
            for ax, asn_list, pattern_handles, bottom in [
                (ax1, ['AS10236', 'AS19905', 'OTHER'], pattern_handles_origin, 0),
                (ax2, VALID_UPSTREAMS[prefix], pattern_handles_upstream, 0)
            ]:
                for asn in asn_list:
                    if stats[asn] > 0:
                        ax.bar(pos, stats[asn], bar_width, bottom=bottom,
                              color=color, hatch=ASN_PATTERNS[asn]['hatch'])
                        bottom += stats[asn]
            
            # Create legend handles once
            if t_idx == 0 and p_idx == 0:
                for p in PREFIXES:
                    prefix_handles.append(plt.Rectangle((0,0), 1, 1, 
                                       color=PREFIX_CONFIG[p]["color"],
                                       label=PREFIX_CONFIG[p]["label"]))
                
                for pattern_list, handles in [
                    (['AS10236', 'AS19905', 'OTHER'], pattern_handles_origin),
                    (['AS3758', 'AS17645'], pattern_handles_upstream)
                ]:
                    for asn in pattern_list:
                        handles.append(plt.Rectangle((0,0), 1, 1,
                                    fc='gray', hatch=ASN_PATTERNS[asn]['hatch'],
                                    label=ASN_PATTERNS[asn]['label']))

    # Configure plots with adjusted legend placement
    for ax, pattern_handles, title in [
        (ax1, pattern_handles_origin, 'Origin ASN Distribution'),
        (ax2, pattern_handles_upstream, 'Upstream ASN Distribution')
    ]:
        ax.set_title(title)
        ax.set_ylabel('Count')
        ax.set_xticks(x_positions + (len(PREFIXES) * (bar_width + bar_gap)) / 2)
        ax.set_xticklabels(timestamps, rotation=45)
        ax.grid(True, axis='y')
        
        # Adjust legend placement
        l1 = ax.legend(handles=prefix_handles, title="Prefixes",
                      bbox_to_anchor=(1.15, 1), loc='upper left')
        ax.add_artist(l1)
        ax.legend(handles=pattern_handles, title="ASN Types",
                 bbox_to_anchor=(1.15, 0.6), loc='upper left')

    # Adjust layout with more space for legends
    plt.tight_layout(rect=[0, 0.05, 0.85, 0.92])
    
    # Add timestamp and next update info
    plt.figtext(0.02, 0.02, 
                f'Last Updated: {timestamp} SGT | Next update in: {time_to_next} seconds', 
                ha='left', va='bottom', fontsize=10)
    
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
    
    # Initialize session state with better defaults
    if 'data_stores' not in st.session_state:
        st.session_state.data_stores = {prefix: DataStorage() for prefix in PREFIXES}
        st.session_state.update_time = get_sgt_time() - timedelta(minutes=2)
        st.session_state.last_stats = None
        st.session_state.update_counter = 0  # Add counter to track updates
    
    # Use global data_stores
    global data_stores
    data_stores = st.session_state.data_stores
    
    # Check timing using SGT
    current_time = get_sgt_time()
    time_since_last_update = (current_time - st.session_state.update_time).seconds
    
    # Fetch data if needed
    if time_since_last_update >= 120 or st.session_state.last_stats is None:
        with st.spinner('Fetching BGP data...'):
            new_stats = fetch_and_analyze_bgp()
            if any(new_stats.values()):  # Check if we got valid data
                st.session_state.last_stats = new_stats
                st.session_state.update_time = current_time
                st.session_state.update_counter += 1
    
    # Calculate time to next update
    time_to_next = max(0, 120 - time_since_last_update)
    
    # Display current data
    if st.session_state.last_stats:
        timestamp = current_time.strftime('%H:%M')
        update_plots(st.session_state.last_stats, timestamp, time_to_next)
        
        # Add update counter to verify updates are happening
        st.sidebar.markdown(f"""
        ### Debug Info
        Updates: {st.session_state.update_counter}
        Last Update: {st.session_state.update_time.strftime('%H:%M:%S')} SGT
        """)
    
    # Force refresh when timer hits zero
    if time_to_next <= 1:
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()