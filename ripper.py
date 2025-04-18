import os
import configparser
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time

# Get path to settings.cfg
script_dir = os.path.dirname(os.path.abspath(__file__))
config = configparser.ConfigParser()
config_path = os.path.join(script_dir, 'settings.cfg')
config.read(config_path)

# Access variables
chromedriver_path = os.path.join(script_dir, config.get('Paths', 'chromedriver'))
output_file = os.path.join(script_dir, config.get('Paths', 'output_file'))
failed_pages_file = os.path.join(script_dir, config.get('Paths', 'failed_pages_file'))

base_url = config.get('URL', 'base_url')
start_page = config.getint('URL', 'start_page')
end_page = config.getint('URL', 'end_page')

# Selenium setup
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--log-level=3")  # Tar bort onödiga chromium-error printouts
options.add_experimental_option('excludeSwitches', ['enable-logging'])
driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)

all_pages_content = ""
failed_pages = []
previous_page_content = None  # Used for duplication detection

def fetch_page(page_num):
    url = f"{base_url}p{page_num}"
    driver.get(url)
    time.sleep(1)  # Undviker bot-detection

    if "captcha" in driver.page_source.lower() or "säkerhetskontroll" in driver.page_source.lower():
        print(f"\033[91mCAPTCHA eller säkerhetssida på sida {page_num}. Hoppar över...\033[0m")
        failed_pages.append(page_num)
        return None

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "post_message"))
        )
    except:
        return False

    return BeautifulSoup(driver.page_source, "html.parser")

# Main loop
page_num = start_page

print("") # Empty line

while True:
    soup = fetch_page(page_num)

    retries = 0
    while soup is False and retries < 2:
        print(f"Misslyckades att hämta {page_num} pga bot-detection... Försöker igen.")
        time.sleep(5)  # Undviker bot-detection
        soup = fetch_page(page_num)
        retries += 1

    if soup is None:
        page_num += 1
        continue
    if soup is False:
        print(f"\033[91mSida {page_num} misslyckades efter 2 omförsök.\033[0m")
        failed_pages.append(page_num)
        page_num += 1
        continue

    posts = soup.find_all('div', class_='post-body')
    page_content = ""

    for post in posts:
        date_parent = post.find_previous('div', class_='post-heading')
        date_element = date_parent.get_text(strip=True).split("\n")[0] if date_parent else "Okänt datum"

        user_info = post.find('a', class_='post-user-username')
        username = user_info.get_text(strip=True) if user_info else "Okänd användare"

        message_div = post.find('div', class_='post_message')
        if not message_div:
            continue

        message_text = message_div.get_text(separator="\n", strip=True)

        page_content += (
            f"Datum: {date_element}\n"
            f"Användare: {username}\n"
            f"Inlägg:\n{message_text}\n"
            f"{'-'*60}\n\n"
        )

    if previous_page_content is not None and page_content == previous_page_content:
        print(f"\033[93mSida {page_num - 1} är sista sidan av tråden.\033[0m")
        break

    previous_page_content = page_content

    print(f"Hämtar sida {page_num}")

    all_pages_content += "\n" + "-"*20 + f"\nPAGE {page_num}\n" + "-"*20 + "\n\n"
    all_pages_content += page_content

    if page_num % 10 == 0:
        print("Pausar i fem sekunder... (Undviker bot-detection)")
        time.sleep(5)  # Undviker bot-detection

    page_num += 1

    if end_page != -1 and page_num > end_page:
        break

driver.quit()

# Save main text
with open(output_file, "w", encoding="utf-8") as f:
    f.write(all_pages_content)

# Save failed pages if any
if failed_pages:
    print("\n\033[91mMisslyckades att hämta följande sidor (efter 2 retries):\033[0m")
    print(failed_pages)

    with open(failed_pages_file, "w", encoding="utf-8") as f:
        for page in failed_pages:
            f.write(f"{page}\n")
    print(f"\n\033[91mMisslyckade sidor sparade i: {failed_pages_file}\033[0m")
else:
    print(f"\n\033[92mInga errors! \033[0m")

print(f"\n\033[92mAlla inlägg är nu sparade i:\033[0m \033[96m{output_file}\033[0m\n")
