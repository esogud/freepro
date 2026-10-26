import os
import random
import re
import string
import time
import uuid
import secrets
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests
from threading import local, Lock
import httpx

# --- KONFİGÜRASYON ---
INPUT_FILE = "okinsta.txt"
SCANNED_FILE = "tarananlar.txt"
PROXY_FILE = "proxies.txt"  # Klasördeki proxy dosyamız
TARGET_CYCLE_LIMIT = 360

# Global Değişkenler
scanned_database = set()
failed_proxies = set()
lock = Lock()
stop_flag = False
active_proxy = None

# --- DİNAMİK TLS İMPERSONATE PROFİLLERİ ---
IMPERSONATE_PROFILES = ["chrome119", "chrome120", "safari17_0", "edge101"]

# --- THREAD-LOCAL SESSION ---
thread_local = local()

def test_proxy(proxy_str):
    """Proxy'nin canlı çalışıp çalışmadığını çok kısa sürede test eder"""
    try:
        res = requests.get("https://httpbin.org/ip", proxies={"http": proxy_str, "https": proxy_str}, timeout=2)
        if res.status_code == 200:
            return True
    except:
        pass
    return False

def load_proxies_from_file():
    """proxies.txt dosyasından proxy'leri okur"""
    proxies = []
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                p = line.strip()
                if p and not p.startswith("#"):
                    if "://" not in p:
                        p = f"http://{p}"
                    proxies.append(p)
    return proxies

def get_fresh_working_proxy():
    global failed_proxies
    print(f"\n🔍 [DOSYA PROXY] '{PROXY_FILE}' dosyasından proxy'ler sırayla test ediliyor...")
    
    pool = load_proxies_from_file()
    
    if not pool:
        print(f"⚠️ '{PROXY_FILE}' dosyası boş veya bulunamadı! Sunucu IP'si ile devam ediliyor...")
        return None

    random.shuffle(pool)
    valid_pool = [p for p in pool if p not in failed_proxies]
    
    if not valid_pool:
        print("⚠️ Tüm proxy'ler kara listede, liste sıfırlanıyor...")
        with lock:
            failed_proxies.clear()
        valid_pool = pool

    # Sıralı (Linear) test mantığı - Asla askıda kalmaz, ölü olanı anında atlar
    for proxy in valid_pool:
        print(f"testing proxy: {proxy} ...", end="\r")
        if test_proxy(proxy):
            print(f"\n⚡ [CANLI PROXY BULUNDU] ---> {proxy}")
            return proxy
            
    print("\n⚠️ Dosyadaki hiçbir proxy'den canlı yanıt alınamadı, sunucu IP'si ile devam ediliyor...")
    return None

# --- TARANANLARI YÜKLE ---
if os.path.exists(SCANNED_FILE):
    with open(SCANNED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            scanned_database.add(line.strip().lower())
    print(f"✅ {len(scanned_database)} adet eski taranan kayıt yüklendi.")


def proxy_ip_reset(reason_msg=""):
    global active_proxy, stop_flag, failed_proxies
    
    if active_proxy:
        with lock:
            failed_proxies.add(active_proxy)
            print(f"🚫 [KARA LİSTE] Patlayan proxy eklendi: {active_proxy}")

    print(f"\n📡 [ROTASYON] {reason_msg} Dosyadan sıradaki alternatif proxy seçiliyor...")
    active_proxy = get_fresh_working_proxy()
    stop_flag = False
    print("🌐 Yeni bağlantı hazır!")


def verify_masked_email(full_email, response_text):
    match = re.search(r"We sent a code to\s+([^\s<>\"]+)", response_text)
    if not match:
        return False
    masked_email = match.group(1).rstrip(".,;")
    if masked_email.lower() == full_email.lower():
        return True
    try:
        m_
