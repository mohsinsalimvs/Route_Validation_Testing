import json
import urllib.request
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import time
import pytz
import sys
import streamlit as st

# Define prefixes and their colors
PREFIX_CONFIG = {
    "171.18.48.0/24": {"color": "royalblue", "label": "48.0/24"},
    "171.18.49.0/24": {"color": "forestgreen", "label": "49.0/24"},
    "171.18.50.0/24": {"color": "deepskyblue", "label": "50.0/24"},
    "171.18.51.0/24": {"color": "lightgreen", "label": "51.0/24"},
    "171.18.48.0/23": {"color": "red", "label": "48.0/23"},
    "171.18.50.0/23": {"color": "orange", "label": "50.0/23"}
}

PREFIXES = list(PREFIX_CONFIG.keys())

# Define valid upstream combinations
VALID_UPSTREAMS = {
    "171.18.48.0/24": ["AS3758"],
    "171.18.49.0/24": ["AS17645"],
    "171.18.50.0/24": ["AS3758"],
    "171.18.51.0/24": ["AS17645"],
    "171.18.48.0/23": ["AS3758", "AS17645"],
    "171.18.50.0/23": ["AS3758", "AS17645"]
}

# Define ASN patterns
ASN_PATTERNS = {
    'AS10236': {'hatch': '', 'label': 'AS10236 (solid)'},
    'AS19905': {'hatch': '//', 'label': 'AS19905 (diagonal)'},
    'OTHER': {'hatch': '..', 'label': 'Other ASNs (dotted)'},
    'AS3758': {'hatch': '', 'label': 'AS3758 (solid)'},
    'AS17645': {'hatch': '//', 'label': 'AS17645 (diagonal)'}
}

# Create figure with two subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
fig.suptitle('BGP Analysis Dashboard\nAll times in SGT (UTC+8)', fontsize=16)

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

data_stores = {prefix: DataStorage() for prefix in PREFIXES}

def get_sgt_time():
    """Convert current UTC time to SGT"""
    utc_time = datetime.now(pytz.UTC)
    sgt = pytz.timezone('Asia/Singapore')
    return utc_time.astimezone(sgt)

def countdown(seconds):
    """Display countdown timer"""
    end_time = datetime.now() + timedelta(seconds=seconds)
    
    while datetime.now() < end_time:
        remaining = end_time - datetime.now()
        mins, secs = divmod(remaining.seconds, 60)
        timeformat = f'\rNext update in: {mins:02d}:{secs:02d}'
        sys.stdout.write(timeformat)
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write('\r' + ' ' * 50 + '\r')
    sys.stdout.flush()

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

            # Upstream ASN counting (only valid combinations)
            as_path = peer['as_path'].split()
            if len(as_path) >= 2:
                second_last = as_path[-2]
                asn_origin = peer['asn_origin']

                i = len(as_path) - 2
                while i >= 0 and as_path[i] == asn_origin:
                    i -= 1
                if i >= 0:
                    second_last = as_path[i]
                    if second_last == '3758' and 'AS3758' in valid_upstreams:
                        stats['AS3758'] += 1
                    elif second_last == '17645' and 'AS17645' in valid_upstreams:
                        stats['AS17645'] += 1

    return stats

def update_plots(all_stats, timestamp):
    """Update plots for Streamlit"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
    
    # Reduced spacing parameters
    bar_width = 0.01  # Smaller bars
    timeframe_gap = 0.02  # Smaller gap between timeframes
    bar_gap = 0.00  # Minimal gap between bars in cluster
    
    for prefix in PREFIXES:
        data_stores[prefix].add_stats(all_stats[prefix], timestamp)
    
    timestamps = data_stores[PREFIXES[0]].timestamps
    x_positions = np.arange(len(timestamps)) * (len(PREFIXES) * (bar_width + bar_gap) + timeframe_gap)
    
    # Create separate legends for prefixes and patterns
    prefix_handles = []
    pattern_handles_origin = []
    pattern_handles_upstream = []
    
    # Plot bars for each timestamp
    for t_idx, _ in enumerate(timestamps):
        base_pos = x_positions[t_idx]
        
        for p_idx, prefix in enumerate(PREFIXES):
            stats = data_stores[prefix].get_stats(t_idx)
            if not stats:
                continue
                
            pos = base_pos + p_idx * (bar_width + bar_gap)
            color = PREFIX_CONFIG[prefix]["color"]
            
            # Stacked bar for origin ASNs
            bottom = 0
            for asn in ['AS10236', 'AS19905', 'OTHER']:
                if stats[asn] > 0:
                    ax1.bar(pos, stats[asn], bar_width, bottom=bottom,
                           color=color, hatch=ASN_PATTERNS[asn]['hatch'])
                    bottom += stats[asn]
            
            # Stacked bar for upstream ASNs (only valid combinations)
            bottom = 0
            valid_upstreams = VALID_UPSTREAMS[prefix]
            for asn in valid_upstreams:
                if stats[asn] > 0:
                    ax2.bar(pos, stats[asn], bar_width, bottom=bottom,
                           color=color, hatch=ASN_PATTERNS[asn]['hatch'])
                    bottom += stats[asn]
            
            # Create legend handles (only once)
            if t_idx == 0 and p_idx == 0:
                for p in PREFIXES:
                    h = plt.Rectangle((0,0), 1, 1, 
                                    color=PREFIX_CONFIG[p]["color"],
                                    label=PREFIX_CONFIG[p]["label"])
                    prefix_handles.append(h)
                
                for asn in ['AS10236', 'AS19905', 'OTHER']:
                    h = plt.Rectangle((0,0), 1, 1, 
                                    fc='gray', hatch=ASN_PATTERNS[asn]['hatch'],
                                    label=ASN_PATTERNS[asn]['label'])
                    pattern_handles_origin.append(h)
                
                for asn in ['AS3758', 'AS17645']:
                    h = plt.Rectangle((0,0), 1, 1, 
                                    fc='gray', hatch=ASN_PATTERNS[asn]['hatch'],
                                    label=ASN_PATTERNS[asn]['label'])
                    pattern_handles_upstream.append(h)

    # Configure plots
    for ax, pattern_handles in [(ax1, pattern_handles_origin), (ax2, pattern_handles_upstream)]:
        ax.set_xticks(x_positions + (len(PREFIXES) * (bar_width + bar_gap)) / 2)
        ax.set_xticklabels(timestamps, rotation=45)
        ax.grid(True, axis='y')
        
        l1 = ax.legend(handles=prefix_handles, title="Prefixes",
                      bbox_to_anchor=(1.01, 1), loc='upper left')
        ax.add_artist(l1)
        ax.legend(handles=pattern_handles, title="ASN Types",
                 bbox_to_anchor=(1.01, 0.6), loc='upper left')

    ax1.set_title('Origin ASN Distribution')
    ax2.set_title('Upstream ASN Distribution')
    ax1.set_ylabel('Count')
    ax2.set_ylabel('Count')

    # Show last 5 timeframes
    if len(x_positions) > 5:
        for ax in [ax1, ax2]:
            ax.set_xlim(x_positions[-5] - timeframe_gap,
                       x_positions[-1] + len(PREFIXES) * (bar_width + bar_gap) + timeframe_gap)

    # Adjust layout to make room for legends and timestamp
    plt.tight_layout(rect=[0, 0.02, 0.85, 0.98])
    
    # Add timestamp with adjusted position
    plt.figtext(0.84, 0.02, f'Last Updated: {timestamp}', 
                ha='right', va='bottom', fontsize=8)

    # Replace display code with Streamlit
    st.pyplot(fig)
    plt.close('all')

def fetch_and_analyze_bgp():
    """Fetch and analyze BGP data for all prefixes"""
    sgt_time = get_sgt_time()
    timestamp = sgt_time.strftime('%H:%M')
    utc_time = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n=== Analysis at {sgt_time.strftime('%Y-%m-%d %H:%M')} SGT ({utc_time}) ===")

    all_stats = {}
    
    for prefix in PREFIXES:
        url = f"https://stat.ripe.net/data/looking-glass/data.json?resource={prefix}"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode('utf-8'))
                all_stats[prefix] = analyze_bgp_data(data, prefix)
                
                stats = all_stats[prefix]
                print(f"\nPrefix: {prefix}")
                print(f"Origin ASNs - AS10236: {stats['AS10236']}, "
                      f"AS19905: {stats['AS19905']}, "
                      f"Others: {stats['OTHER']}")
                print(f"Upstream ASNs - ", end='')
                for asn in VALID_UPSTREAMS[prefix]:
                    print(f"{asn}: {stats[asn]} ", end='')
                print()
                
        except Exception as e:
            print(f"Error analyzing {prefix}: {e}")
            all_stats[prefix] = None

    update_plots(all_stats, timestamp)
    return all_stats

def main():
    """Streamlit main function"""
    # Page configuration
    st.set_page_config(page_title="BGP Analysis Dashboard", layout="wide")
    st.title("BGP Analysis Dashboard")
    
    # Initialize session state
    if 'data_stores' not in st.session_state:
        st.session_state.data_stores = {prefix: DataStorage() for prefix in PREFIXES}
        st.session_state.update_time = datetime.now() - timedelta(minutes=2)
        st.session_state.last_stats = None
    
    # Use global data_stores
    global data_stores
    data_stores = st.session_state.data_stores
    
    # Create placeholders
    status_placeholder = st.sidebar.empty()
    graph_placeholder = st.empty()
    
    # Check if we need initial data or an update
    current_time = datetime.now()
    time_since_last_update = (current_time - st.session_state.update_time).seconds
    
    # Fetch data if it's time for an update or we have no data
    if time_since_last_update >= 120 or st.session_state.last_stats is None:
        with st.spinner('Fetching BGP data...'):
            st.session_state.last_stats = fetch_and_analyze_bgp()
            st.session_state.update_time = current_time
    
    # Update display
    time_to_next = 120 - time_since_last_update
    status_placeholder.markdown(f"""
        ### Status
        Next update in: {time_to_next} seconds  
        Last updated: {st.session_state.update_time.strftime('%Y-%m-%d %H:%M:%S')}
    """)
    
    # Display current data
    if st.session_state.last_stats:
        sgt_time = get_sgt_time()
        timestamp = sgt_time.strftime('%H:%M')
        with graph_placeholder:
            update_plots(st.session_state.last_stats, timestamp)
    
    # Schedule next update
    time.sleep(2)
    st.rerun()

if __name__ == "__main__":
    main()
