import concurrent.futures
import requests
from fp.fp import FreeProxy

def get_raw_proxies(count=15):
    """free-proxy kütüphanesinden birden fazla proxy toplar"""
    proxies = set()
    print("Proxy adresleri toplanıyor...")
    
    # İstediğiniz sayıda farklı proxy çekmeye çalışalım
    for _ in range(count):
        try:
            p = FreeProxy(https=True).get()
            if p:
                proxies.add(p)
        except Exception:
            pass
            
    print(f"Toplam {len(proxies)} adet ham proxy toplandı. Canlılık testleri başlatılıyor...\n")
    return list(proxies)

def test_proxy(proxy):
    """Tek bir proxy'nin çalışıp çalışmadığını ve hızını test eder"""
    test_url = "https://httpbin.org/ip"
    proxies_dict = {
        "http": proxy,
        "https": proxy
    }
    try:
        # 4 saniye zaman aşımı ile test isteği atıyoruz
        response = requests.get(test_url, proxies=proxies_dict, timeout=4)
        if response.status_code == 200:
            return proxy
    except Exception:
        pass
    return None

def main():
    raw_list = get_raw_proxies(count=20)
    if not raw_list:
        print("Hiç proxy toplanamadı. Lütfen tekrar deneyin.")
        return

    working_proxies = []
    
    # Multithreading (Çoklu İş Parçacığı) ile aynı anda hızlıca test ediyoruz
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(test_proxy, raw_list)
        
        for proxy in results:
            if proxy:
                print(f"[ŞU AN ÇALIŞIYOR / LIVE] ---> {proxy}")
                working_proxies.append(proxy)

    print("\n" + "="*40)
    print(f"Tarama Tamamlandı. Toplam Çalışan Proxy Sayısı: {len(working_proxies)}")
    print("="*40)
    
    # İsterseniz çalışanları bir dosyaya da kaydedebilirsiniz:
    if working_proxies:
        with open("working_proxies.txt", "w") as f:
            for p in working_proxies:
                f.write(f"{p}\n")
        print("Çalışan proxy'ler 'working_proxies.txt' dosyasına kaydedildi.")

if __name__ == "__main__":
    main()
