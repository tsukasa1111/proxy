from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
import os
import json
import requests
from urllib.parse import urlparse, unquote
import sys

# 対話形式で入力を受け付ける
if __name__ == "__main__":
    deck_url = input("デッキのURLを入力してください: ").strip()
    SAVE_DIR = input("保存フォルダ名を入力してください: ").strip()
    if not deck_url or not SAVE_DIR:
        print("URLと保存フォルダ名は必須です。")
        sys.exit(1)
    os.makedirs(SAVE_DIR, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(deck_url)
        time.sleep(3)

        scroll_height = driver.execute_script("return document.body.scrollHeight")
        for y in range(0, scroll_height, 500):
            driver.execute_script(f"window.scrollTo(0, {y});")
            time.sleep(0.5)
        time.sleep(2)

        # モーダル画像（高画質）のみ取得
        img_elements = driver.find_elements(
            By.XPATH,
            "//img[contains(@src, 'storage.googleapis.com/ka-nabell-card-images/img/card/') and not(contains(@src, '/img/s/'))]"
        )
        print(f"✅ 高画質カード画像を {len(img_elements)} 枚検出")

        # カードごとの出現数カウント
        card_count = {}
        url_map = {}

        for img in img_elements:
            src = img.get_attribute("src") or ""
            if not src:
                srcset = img.get_attribute("srcset") or ""
                src = srcset.split()[0] if srcset else ""
            if src:
                filename = os.path.basename(unquote(urlparse(src).path))
                card_count[filename] = card_count.get(filename, 0) + 1
                url_map[filename] = src  # 最後のsrcで上書きOK

        print(f"🎴 カード種類数: {len(card_count)}")

        # カード画像を出現回数分保存（連番ファイル名）
        global_count = 1
        for filename, count in card_count.items():
            src = url_map[filename]
            for i in range(count):
                numbered_name = f"{global_count:03d}_{filename}"
                save_path = os.path.join(SAVE_DIR, numbered_name)

                headers = {"Referer": deck_url}
                resp = requests.get(src, headers=headers)
                if resp.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(resp.content)
                    print(f"[{global_count}] 保存成功: {numbered_name}")
                else:
                    print(f"[{global_count}] 保存失敗 ({resp.status_code}): {filename}")
                global_count += 1

        # deck_list.json も保存
        # json_path = os.path.join(SAVE_DIR, "deck_list.json")
        # with open(json_path, "w", encoding="utf-8") as f:
        #     json.dump(card_count, f, indent=2, ensure_ascii=False)
        # print(f"✅ 枚数記録を deck_list.json に保存: {json_path}")

    finally:
        driver.quit()