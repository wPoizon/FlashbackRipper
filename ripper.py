import os
import configparser
import re
from selenium import webdriver
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
chromedriver_path = os.path.join(
    script_dir,
    config.get('Paths', 'chromedriver')
)

# Output filenames from settings.cfg.
# A separate folder will be created for every thread.
output_filename = os.path.basename(
    config.get('Paths', 'output_file')
)

failed_pages_filename = os.path.basename(
    config.get('Paths', 'failed_pages_file')
)

links_filename = os.path.basename(
    config.get('Paths', 'links_file')
)

# Use the directory configured for output_file as the root output directory.
output_root = os.path.join(
    script_dir,
    os.path.dirname(config.get('Paths', 'output_file'))
)

output_file = None
failed_pages_file = None
links_file = None


base_url = config.get('URL', 'base_url')
start_page = config.getint('URL', 'start_page')
end_page = config.getint('URL', 'end_page')

if not base_url.strip():
    print(
        "\n\033[91mSaknas Flashback URL.\033[0m "
        "Fyll i en URL i settings.cfg 'base_url' och "
        "starta programmet igen för att söka igenom en tråd.\n"
    )
    exit()


# Selenium setup
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--log-level=3")
options.add_experimental_option(
    'excludeSwitches',
    ['enable-logging']
)

driver = webdriver.Chrome(options=options)


all_pages_content = ""

# Dictionary containing all unique links.
#
# The URL itself is the key.
# Each URL contains lists of all pages, posts and users
# where that URL was found.
found_links = {}

failed_pages = []
previous_page_content = None
thread_title = ""


def create_thread_output_folder():
    """
    Creates a unique output folder for the current thread.

    The folder is based on the thread title. Characters that are not
    suitable for Windows/Linux filenames are removed or replaced.
    If the folder already exists, a numbered suffix is added so that
    previous runs are never overwritten.
    """

    global output_file
    global failed_pages_file
    global links_file

    safe_title = re.sub(
        r'[<>:"/\\|?*]',
        '_',
        thread_title
    )

    safe_title = re.sub(
        r'\s+',
        ' ',
        safe_title
    ).strip(' ._')

    if not safe_title:
        safe_title = "Okänd tråd"

    thread_folder = os.path.join(
        output_root,
        safe_title
    )

    # Never overwrite an existing thread folder.
    if os.path.exists(thread_folder):
        counter = 2

        while os.path.exists(
            f"{thread_folder} ({counter})"
        ):
            counter += 1

        thread_folder = f"{thread_folder} ({counter})"

    os.makedirs(
        thread_folder,
        exist_ok=True
    )

    output_file = os.path.join(
        thread_folder,
        output_filename
    )

    failed_pages_file = os.path.join(
        thread_folder,
        failed_pages_filename
    )

    links_file = os.path.join(
        thread_folder,
        links_filename
    )

    print(
        f"Trådens filer sparas i: {thread_folder}"
    )


def save_progress():
    """
    Saves the current progress to all three files.
    """

    # -----------------------------------------------------
    # Save content.txt
    # -----------------------------------------------------

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            f"Titel: \n{thread_title}\n\n"
        )

        f.write(
            f"URL: \n{base_url}\n\n"
        )

        f.write(
            all_pages_content
        )

    # -----------------------------------------------------
    # Save links.txt
    # -----------------------------------------------------

    with open(
        links_file,
        "w",
        encoding="utf-8"
    ) as f:

        for url, data in found_links.items():

            pages = ", ".join(
                str(page)
                for page in data["pages"]
            )

            posts = ", ".join(
                f"#{post}"
                for post in data["posts"]
            )

            users = ", ".join(
                data["users"]
            )

            f.write(
                f"{url} - "
                f"page {pages} - "
                f"post {posts} - "
                f"posted by {users}\n"
            )

    # -----------------------------------------------------
    # Save failed_pages.txt
    # -----------------------------------------------------

    with open(
        failed_pages_file,
        "w",
        encoding="utf-8"
    ) as f:

        for page in failed_pages:
            f.write(
                f"{page}\n"
            )


def fetch_page(page_num):

    url = f"{base_url}p{page_num}"

    driver.get(url)

    time.sleep(1)  # Undviker bot-detection

    global thread_title

    if page_num == start_page and not thread_title:
        thread_title = driver.title.strip()
        create_thread_output_folder()

    if (
        "captcha" in driver.page_source.lower()
        or "säkerhetskontroll" in driver.page_source.lower()
    ):

        print(
            f"\033[91mCAPTCHA eller säkerhetssida på sida "
            f"{page_num}. Hoppar över...\033[0m"
        )

        failed_pages.append(page_num)

        # Save failed page immediately.
        save_progress()

        return None

    try:

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, "post_message")
            )
        )

    except:

        return False

    return BeautifulSoup(
        driver.page_source,
        "html.parser"
    )


def extract_links(
    message_div,
    page_num,
    post_number,
    username
):
    """
    Finds URLs in the original post.

    Quoted posts are removed before searching for URLs.

    Each unique URL is stored only once. If the same URL
    occurs in another post, its page, post number and
    username are appended to the existing entry.
    """

    # Create a separate copy so that the original
    # message is not modified.
    message_for_links = BeautifulSoup(
        str(message_div),
        "html.parser"
    )

    # -----------------------------------------------------
    # Remove quoted posts
    # -----------------------------------------------------

    quote_selectors = [
        "blockquote",
        ".quote",
        ".bbcode_quote",
        ".quotecontent",
        ".quotetitle",
        ".quote_body",
        ".quote-content",
    ]

    for selector in quote_selectors:

        for quote in message_for_links.select(selector):
            quote.decompose()

    # -----------------------------------------------------
    # Get remaining text
    # -----------------------------------------------------

    message_text = message_for_links.get_text(
        separator="\n",
        strip=True
    )

    # -----------------------------------------------------
    # Find URLs
    # -----------------------------------------------------

    url_pattern = r'https?://[^\s<>"\']+'

    urls = re.findall(
        url_pattern,
        message_text,
        re.IGNORECASE
    )

    # Avoid finding the exact same URL multiple times
    # within the same post.
    seen_urls = set()

    for url in urls:

        # Remove punctuation that can be attached
        # to the end of a URL in normal text.
        url = url.rstrip(
            '.,!?;:)\'"'
        )

        if not url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        # -------------------------------------------------
        # New URL
        # -------------------------------------------------

        if url not in found_links:

            found_links[url] = {
                "pages": [],
                "posts": [],
                "users": []
            }

        # -------------------------------------------------
        # Add this occurrence
        # -------------------------------------------------

        found_links[url]["pages"].append(
            page_num
        )

        found_links[url]["posts"].append(
            post_number
        )

        found_links[url]["users"].append(
            username
        )


# ---------------------------------------------------------
# Main loop
# ---------------------------------------------------------

page_num = start_page
title_printed = False

print("")


try:

    while True:

        soup = fetch_page(page_num)

        retries = 0

        while soup is False and retries < 2:

            print(
                f"Misslyckades att hämta {page_num} "
                f"pga bot-detection... Försöker igen."
            )

            time.sleep(5)

            soup = fetch_page(page_num)

            retries += 1

        if soup is None:

            page_num += 1

            if (
                end_page != -1
                and page_num > end_page
            ):
                break

            continue

        if soup is False:

            print(
                f"\033[91mSida {page_num} misslyckades "
                f"efter 2 omförsök.\033[0m"
            )

            failed_pages.append(
                page_num
            )

            save_progress()

            page_num += 1

            if (
                end_page != -1
                and page_num > end_page
            ):
                break

            continue

        # -------------------------------------------------
        # Thread title
        # -------------------------------------------------

        if not title_printed:

            print(
                f"Börjar läsa tråd: {thread_title}"
            )

            title_printed = True

        # -------------------------------------------------
        # Find posts
        # -------------------------------------------------

        posts = soup.find_all(
            "div",
            class_="post-body"
        )

        page_content = ""

        for post in posts:

            # -------------------------------------------------
            # Date + post number
            # -------------------------------------------------

            date_parent = post.find_previous(
                "div",
                class_="post-heading"
            )

            date_element = (
                date_parent.get_text(strip=True)
                .split("\n")[0]
                if date_parent
                else "Okänt datum"
            )

            # The thread-local post number is included
            # in the date string, for example:
            #
            # "Igår, 23:23#95"

            post_match = re.search(
                r'#(\d+)',
                date_element
            )

            post_number = (
                post_match.group(1)
                if post_match
                else "?"
            )

            # -------------------------------------------------
            # Username
            # -------------------------------------------------

            user_info = post.find(
                "a",
                class_="post-user-username"
            )

            username = (
                user_info.get_text(strip=True)
                if user_info
                else "Okänd användare"
            )

            # -------------------------------------------------
            # Message
            # -------------------------------------------------

            message_div = post.find(
                "div",
                class_="post_message"
            )

            if not message_div:
                continue

            # -------------------------------------------------
            # Find links in original post
            # -------------------------------------------------

            extract_links(
                message_div,
                page_num,
                post_number,
                username
            )

            # -------------------------------------------------
            # Save post text
            # -------------------------------------------------

            message_text = message_div.get_text(
                separator="\n",
                strip=True
            )

            page_content += (
                f"\n{'-' * 60}\n\n"
                f"Datum: {date_element}\n"
                f"Användare: {username}\n"
                f"Inlägg:\n{message_text}\n"
            )

        page_content += (
            f"\n{'-' * 60}\n"
        )

        # -----------------------------------------------------
        # Check for duplicate final page
        # -----------------------------------------------------

        if (
            previous_page_content is not None
            and page_content == previous_page_content
        ):

            print(
                f"\033[93mSida {page_num - 1} är sista "
                f"sidan av tråden.\033[0m"
            )

            break

        previous_page_content = page_content

        print(
            f"Hämtar sida {page_num}"
        )

        all_pages_content += (
            "\n"
            + "-" * 14
            + f"\n|  SIDA {page_num}   |\n"
            + "-" * 14
            + "\n\n"
        )

        all_pages_content += page_content

        # -----------------------------------------------------
        # Save progress after every page
        # -----------------------------------------------------

        save_progress()

        # -----------------------------------------------------
        # Pause every 10 pages
        # -----------------------------------------------------

        if page_num % 10 == 0:

            print(
                "Pausar i fem sekunder... "
                "(Undviker bot-detection)"
            )

            time.sleep(5)

        page_num += 1

        if (
            end_page != -1
            and page_num > end_page
        ):
            break

finally:

    driver.quit()


# ---------------------------------------------------------
# Final status
# ---------------------------------------------------------

if failed_pages:

    print(
        "\n\033[91mMisslyckades att hämta följande "
        "sidor (efter 2 retries):\033[0m"
    )

    print(
        failed_pages
    )

else:

    print(
        "\n\033[92mInga errors! \033[0m"
    )


print(
    f"\n\033[92mAlla inlägg är nu sparade i:\033[0m "
    f"\033[96m{output_file}\033[0m"
)

print(
    f"\033[92mAlla länkar är nu sparade i:\033[0m "
    f"\033[96m{links_file}\033[0m\n"
)