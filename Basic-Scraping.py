import tkinter as tk
from tkinter import scrolledtext, messagebox,filedialog
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import json
import os
import time
import re
from datetime import datetime, timedelta
import csv
import pandas as pd 
import random 

COOKIE_FILE = "cookies.json"
default_csv_path = "output_komentar.csv"
loaded_df = pd.DataFrame()

def load_existing_csv():
    global loaded_csv_path, loaded_df
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if file_path:
        loaded_csv_path = file_path
        try:
            loaded_df = pd.read_csv(file_path)
            messagebox.showinfo("Sukses", f"Berhasil memuat {file_path}")
        except Exception as e:
            messagebox.showerror("Gagal", f"Gagal memuat CSV: {e}")

def save_cookies(driver):
    with open(COOKIE_FILE, "w") as file:
        json.dump(driver.get_cookies(), file)
    print("[INFO] Cookie berhasil disimpan.")

def load_cookies(driver, url):
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as file:
            cookies = json.load(file)
            driver.get(url)
            for cookie in cookies:
                if "sameSite" in cookie:
                    del cookie["sameSite"]  # biar tidak error
                driver.add_cookie(cookie)
            print("[INFO] Cookie berhasil dimuat.")
        return True
    return False
def parse_comment_time(raw_time: str) -> str:
    now = datetime.now()

    if "-" in raw_time:  # Format MM-DD
        try:
            dt = datetime.strptime(raw_time, "%m-%d")
            dt = dt.replace(year=now.year)
            return dt.strftime("%d %B %Y")
        except:
            return raw_time

    match = re.match(r"(\d+)\s*([mhdw])", raw_time)
    if not match:
        match = re.match(r"(\d+)([mhdw])", raw_time)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if "m" in unit:
            return (now - timedelta(minutes=amount)).strftime("%d %B %Y %H:%M")
        elif "h" in unit:
            return (now - timedelta(hours=amount)).strftime("%d %B %Y %H:%M")
        elif "d" in unit:
            return (now - timedelta(days=amount)).strftime("%d %B %Y")
        elif "w" in unit:
            return (now - timedelta(weeks=amount)).strftime("%d %B %Y")

    return raw_time  # fallback


def scrape_comments():
    url = url_entry.get()
    total_all_comments = 0
    keywords = [k.strip().lower() for k in keyword_entry.get().split(',') if k.strip()]
    chrome_driver_path = r"C:\Users\ANGEL MARCELINA\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"
    matched_comments = []
   

    try:
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--window-size=1920,3000")

        service = Service(chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        logged_in = False
        if load_cookies(driver, "https://www.tiktok.com/"):
            driver.get("https://www.tiktok.com/")
            time.sleep(5)
            if "login" not in driver.current_url.lower():
                logged_in = True

        if not logged_in:
            driver.get("https://www.tiktok.com/login")
            messagebox.showinfo("Login", "Silakan login TikTok di browser yang muncul.\nKlik OK setelah login.")
            save_cookies(driver)

        driver.get(url)
        time.sleep(5)

        # Scroll dan scraping dilakukan dalam beberapa sesi
       
        max_retries=15 
        retries = 0
        last_count = -1# jeda antar sesi dalam detik
        seen_raw_html = set()
        all_results = []
        found = False

        while retries < max_retries:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(3, 4))

            buttons = driver.find_elements(By.XPATH, '//div[contains(@class, "DivViewRepliesContainer")]')
            print(f"[DEBUG] View Replies ditemukan: {len(buttons)}")

            for btn in buttons:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except Exception as e:
                    print("[SKIP Click]", e)

            containers = driver.find_elements(By.XPATH, '//div[contains(@class, "DivCommentItemWrapper")]')
            print(f"[DEBUG] Komentar terlihat di DOM: {len(containers)}")

            for container in containers:
                try:
                    html = container.get_attribute("outerHTML")
                    if html in seen_raw_html:
                        continue
                    seen_raw_html.add(html)

                    username_elem = container.find_element(By.XPATH, './/a[contains(@href, "/@")]')
                    username = username_elem.get_attribute('href').split('/')[-1]

                    # Coba comment-level-1 lalu fallback
                    try:
                        comment = container.find_element(By.XPATH, './/span[@data-e2e="comment-level-1"]/p').text.strip()
                        level = "utama"
                    except:
                        comment = container.find_element(By.XPATH, './/span[@data-e2e="comment-level-2"]/p').text.strip()
                        level = "reply"

                    # Coba ambil waktu
                    spans = container.find_elements(By.XPATH, './/span')
                    comment_time = "?"
                    for span in spans:
                        text = span.text.strip().lower()
                        if re.search(r"\d+[mhdw]\s*ago", text) or re.search(r"\d{1,2}-\d{1,2}", text):
                            cleaned_time = re.sub(r"ago", "", text).strip()
                            comment_time = parse_comment_time(cleaned_time)
                            break

                    print(f"[CAPTURED] @{username} ({comment_time}): {comment}")
                    all_results.append({
                        'username': username,
                        'comment': comment,
                        'level':level,
                        'comment_time': comment_time
                    })
                    if any(k in comment.lower() for k in keywords):
                        result_box.insert(tk.END, f"{username}: {comment} {comment_time}\n\n")
                        matched_comments.append({
                            "username": username,
                            "level": level,
                            "comment": comment,
                            "time": comment_time
                        })
                        found = True
                        total_all_comments+=1

                except Exception as e:
                    print("[SKIP KOMEN]", e)

            # Ulangi sampai tidak ada baru
            if len(seen_raw_html) == last_count:
                retries += 1
            else:
                retries = 0
                last_count = len(seen_raw_html)

            print(f"[DEBUG] Komentar unik terkumpul: {len(seen_raw_html)} (Retry {retries}/{max_retries})")

            if len(seen_raw_html) == last_count:
                retries += 1
                print(f"[INFO] Tidak ada komentar baru, retry ke-{retries}/{max_retries}")
            else:
                retries=0
                last_count = len(seen_raw_html)


            

        # for container in containers:
        #     try:
        #         # ambil username dari <a href="/@username">
        #         username_elem = container.find_element(By.XPATH, './/a[contains(@href, "/@")]')
        #         username = username_elem.get_attribute('href').split('/')[-1]
        #         html = container.get_attribute("outerHTML")
        #         jenis = "reply" if "comment-level-2" in html else "utama"

        # # Ambil isi komentar dari span data-e2e dan p di dalamnya
        #         # try:
        #         #     comment_elem = None
        #         #     for level in ["comment-level-1", "comment-level-2"]:
        #         #         try:
        #         #             comment_elem = container.find_element(By.XPATH, f'.//span[@data-e2e="{level}"]/p')
        #         #             break
        #         #         except:
        #         #             try:
        #         #                 comment_elem = container.find_element(By.XPATH, f'.//span[@data-e2e="{level}"]')
        #         #                 break
        #         #             except:
        #         #                 continue

        #         #     if comment_elem:
        #         #         comment = comment_elem.text.strip()
        #         #     else:
        #         #         comment = ""
        #         # except:
        #         #     comment = ""
        #         try:
        #             comment_elem = container.find_element(By.XPATH, './/span[@data-e2e="comment-level-1"]/p')
        #             comment = comment_elem.text.strip()
        #            
        #         except:
        #             try:
        #                 comment_elem = container.find_element(By.XPATH, './/span[@data-e2e="comment-level-2"]/p')
        #                 comment = comment_elem.text.strip()
        #                 level = "reply1"
        #             except:
        #                 comment = "[Komentar tidak ditemukan]"
                
        #         spans = container.find_elements(By.XPATH, './/span')
        #         comment_time = "?"

        #         for span in spans:
        #             text = span.text.strip().lower()
        #             print(f"[DEBUG] [Span check] {text}")  # debug bantu
        #             if re.search(r"\d+\s*[mhdw]\s+yang\s+lalu", text) or re.search(r"\d{1,2}-\d{1,2}", text):
        #                 cleaned_time = re.sub(r"yang lalu", "", text).strip()
        #                 comment_time = parse_comment_time(cleaned_time)
        #                 break
        #             elif re.search(r"\d+[mhdw]\s*ago", text):  # ✨ penanganan baru
        #                 cleaned_time = text.replace("ago", "").strip()
        #                 comment_time = parse_comment_time(cleaned_time)
        #                 break
        #         # time_elem = container.find_element(By.XPATH, './/span[contains(text(), "yang lalu") or contains(text(), "-")]')
        #         # raw_time = time_elem.text.strip()
        #         # parsed_time = parse_comment_time(raw_time)
               
        #         # comment_time = time_elem.text.strip()
        #         print(f"[DEBUG] @{username} {level}{jenis} ({comment_time}): {comment}")

        #         total_all_comments+=1
               
                

            # except Exception as e:
            #     print("[SKIP]", e)


        if not found:
            result_box.insert(tk.END, "Tidak ada komentar dengan keyword tersebut.")
        
        print(f"[INFO] Komentar berhasil diproses: {total_all_comments}")
        data_to_save = all_results if save_all_var.get() else matched_comments

        if data_to_save:
             new_df = pd.DataFrame(data_to_save)

             try:
                existing_df = pd.read_csv(default_csv_path)
             except FileNotFoundError:
                existing_df = pd.DataFrame()

             if not existing_df.empty:
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.drop_duplicates(subset=['username','level', 'comment', 'time'], inplace=True)
             else:
                combined_df = new_df

             combined_df.to_csv(default_csv_path, index=False)
             messagebox.showinfo("Sukses", f"Data berhasil disimpan ke {default_csv_path}")

        driver.quit()

    except Exception as e:
        messagebox.showerror("Error", f"Gagal scraping: {e}")

# GUI Setup
root = tk.Tk()
root.title("TikTok Scraper (Cookie Login + Username)")

tk.Label(root, text="TikTok Video URL:").grid(row=0, column=0, sticky="w")
url_entry = tk.Entry(root, width=60)
url_entry.grid(row=0, column=1, padx=5, pady=5)

tk.Label(root, text="Keyword:").grid(row=1, column=0, sticky="w")
keyword_entry = tk.Entry(root, width=30)
keyword_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)

tk.Button(root, text="Scrape", command=scrape_comments).grid(row=2, column=1, sticky="w", padx=5)

label = tk.Label(root, text="Klik tombol untuk memuat file CSV yang sudah ada:")
label.grid(row=3, column=1, sticky="w", padx=5)

save_all_var = tk.BooleanVar()
tk.Checkbutton(root, text="Simpan semua komentar", variable=save_all_var).grid(row=2, column=0, sticky="w", padx=5)


load_button = tk.Button(root, text="Load Existing CSV", command=load_existing_csv)
load_button.grid(row=4, column=1, sticky="w", padx=5)

result_box = scrolledtext.ScrolledText(root, width=80, height=20)
result_box.grid(row=5, column=0, columnspan=2, padx=5, pady=5)

root.mainloop()
