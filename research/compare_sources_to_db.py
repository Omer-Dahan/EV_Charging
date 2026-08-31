#!/usr/bin/env python3
"""
Comprehensive Comparison & Source Analysis Script:
Compares current ev_stations.db against live external sources, company APIs, and aggregators.
"""

import os
import sqlite3
import urllib.request
import json
import re
from typing import Dict, Any, List

DB_PATH = '/home/vm/projects/ev-charging-bot/data/ev_stations.db'
CELLO_TOKEN = os.environ.get('CELLO_TOKEN', '')

def get_db_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM locations')
    total = c.fetchone()[0]
    c.execute('SELECT provider_name, COUNT(*) FROM locations GROUP BY provider_name ORDER BY COUNT(*) DESC')
    prov_counts = dict(c.fetchall())
    
    # Check Beit El in DB
    c.execute("SELECT id, name, address, city, lat, lng, provider_name, sources FROM locations WHERE city LIKE '%בית אל%' OR address LIKE '%בית אל%' OR name LIKE '%בית אל%' OR (lat BETWEEN 31.92 AND 31.96 AND lng BETWEEN 35.20 AND 35.25)")
    beit_el_db = c.fetchall()
    
    conn.close()
    return total, prov_counts, beit_el_db

def fetch_cello_stats():
    req = urllib.request.Request(
        'https://api.prod.ev.cellocharge.com/evsfeed/api/v2/portal/locations',
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Authorization': f'Bearer {CELLO_TOKEN}',
            'Accept': 'application/json'
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    
    counts = {}
    beit_el = []
    for loc in data:
        pid = loc.get('providerId') or 'Unknown'
        counts[pid] = counts.get(pid, 0) + 1
        
        coords = loc.get('coordinates', {})
        lat = coords.get('lat', 0)
        lng = coords.get('lng', 0)
        addr = str(loc.get('address', '')) + ' ' + str(loc.get('name', '')) + ' ' + str(loc.get('city', ''))
        if 'בית אל' in addr or 'beit el' in addr.lower() or (31.92 < lat < 31.96 and 35.20 < lng < 35.25):
            beit_el.append(loc)
            
    return len(data), counts, beit_el

def fetch_interev_stats():
    req = urllib.request.Request(
        'https://interevserver.evgateway.com/common/map/filter?search=null',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    beit_el = []
    for s in data:
        lat = float(s.get('latitude', 0))
        lng = float(s.get('longitude', 0))
        addr = str(s.get('siteaddress', '')) + ' ' + str(s.get('siteName', ''))
        if 'בית אל' in addr or 'beit el' in addr.lower() or (31.92 < lat < 31.96 and 35.20 < lng < 35.25):
            beit_el.append(s)
    return len(data), beit_el

def fetch_afcon_stats():
    req = urllib.request.Request(
        'https://account.afconev.co.il/stationFacade/findSitesInBounds',
        data=json.dumps({
            'bounds': {'southWest': {'lat': 29.4, 'lng': 34.1}, 'northEast': {'lat': 33.4, 'lng': 35.9}},
            'filter': {}
        }).encode('utf-8'),
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/json;charset=UTF-8',
            'Referer': 'https://account.afconev.co.il/findCharger'
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    sites = data.get('data', [])
    beit_el = []
    for s in sites:
        lat = float(s.get('latitude', 0))
        lng = float(s.get('longitude', 0))
        name = str(s.get('dn', ''))
        if 'בית אל' in name or 'beit el' in name.lower() or (31.92 < lat < 31.96 and 35.20 < lng < 35.25):
            beit_el.append(s)
    return len(sites), beit_el

def fetch_zen_stats():
    req = urllib.request.Request(
        'https://zen-ev.com/locations',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8')
    coords = re.findall(r'data-lat="([^"]+)"\s+data-lng="([^"]+)"', html)
    return len(coords)

def fetch_tesla_stats():
    req = urllib.request.Request(
        'https://supercharge.info/service/supercharge/allSites',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    il_sites = [s for s in data if s.get('address', {}).get('country') == 'Israel' or s.get('location', {}).get('country') == 'Israel']
    return len(il_sites)

print('Running comparison analysis...')
db_total, db_provs, beit_el_db = get_db_stats()
cello_total, cello_provs, beit_el_cello = fetch_cello_stats()
interev_total, beit_el_interev = fetch_interev_stats()
afcon_total, beit_el_afcon = fetch_afcon_stats()
zen_total = fetch_zen_stats()
tesla_total = fetch_tesla_stats()

print(f'DB Total Locations: {db_total}')
print(f'CelloCharge Total Locations: {cello_total}')
print(f'InterEV Direct EVGateway Stations: {interev_total}')
print(f'Afcon Direct API Sites: {afcon_total}')
print(f'Zen Energy Website Stations: {zen_total}')
print(f'Tesla Supercharger Sites: {tesla_total}')

print('\n=== Provider Breakdown: DB vs CelloCharge ===')
all_prov_keys = sorted(set(list(db_provs.keys()) + list(cello_provs.keys())))
for p in all_prov_keys:
    in_db = db_provs.get(p, 0)
    in_cello = cello_provs.get(p, 0)
    diff = in_cello - in_db
    print(f'{p:25} | DB: {in_db:4} | Cello: {in_cello:4} | Diff: {diff:+4}')

print('\n=== Beit El Deep Dive ===')
print(f'In DB ({len(beit_el_db)}):')
for b in beit_el_db:
    print(' ', b)

print(f'\nIn CelloCharge ({len(beit_el_cello)}):')
for b in beit_el_cello:
    print(' ', b.get('id'), b.get('name'), b.get('city'), b.get('address'), b.get('coordinates'), b.get('providerId'))

print(f'\nIn InterEV EVGateway ({len(beit_el_interev)}):')
for b in beit_el_interev:
    print(' ', b.get('uuid'), b.get('siteName'), b.get('siteaddress'), b.get('latitude'), b.get('longitude'))
