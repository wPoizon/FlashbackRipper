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

# Page to resume from, if this thread has already been scanned.
resume_page = None


def create_thread_output_folder():
    """
    Creates or reuses the output folder for the current thread.

    If the thread folder already exists, it is reused.
    Existing progress is loaded so the thread can resume
    from the last successfully saved page.
    """

    global output_file
    global failed_pages_file
    global links_file
    global all_pages_content
    global failed_pages
    global resume_page

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

    # Reuse the existing folder instead of creating
    # "Thread (2)", "Thread (3)", etc.
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

    # ---------------------------------------------------------
    # Load existing progress
    # ---------------------------------------------------------

    if os.path.exists(output_file):

        print(
            f"Hittade befintlig tråd: {thread_folder}"
        )

        print(
            "Läser tidigare sparad progress..."
        )

        with open(
            output_file,
            "r",
            encoding="utf-8"
        ) as f:
            existing_content = f.read()

        # Find all saved page headers.
        page_matches = re.findall(
            r'\|\s*SIDA\s+(\d+)\s+\|',
            existing_content
        )

        if page_matches:

            last_saved_page = max(
                int(page)
                for page in page_matches
            )

            all_pages_content = existing_content

            resume_page = last_saved_page

            print(
                f"Senast sparade sida: {last_saved_page}"
            )

            print(
                f"Återupptar från sida {resume_page} "
                f"(sidan skannas om)."
            )

        else:

            print(
                "Ingen sparad sida hittades. "
                "Börjar från start_page."
            )

    # ---------------------------------------------------------
    # Load failed pages
    # ---------------------------------------------------------

    if os.path.exists(failed_pages_file):

        with open(
            failed_pages_file,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                line = line.strip()

                if line.isdigit():

                    page = int(line)

                    if page not in failed_pages:
                        failed_pages.append(page)


def remove_page_from_saved_content(page_num):
    """
    Removes the saved content for page_num and all pages after it.

    This allows the last saved page to be scanned again without
    duplicating its content.
    """

    global all_pages_content

    if not all_pages_content:
        return

    page_pattern = re.compile(
        rf'\n?-{{14}}\n'
        rf'\|  SIDA {page_num}\s+\|\n'
        rf'-{{14}}\n'
    )

    match = page_pattern.search(
        all_pages_content
    )

    if match:

        all_pages_content = (
            all_pages_content[:match.start()]
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


def initialize_thread():
    """
    Loads the first page only to determine the thread title,
    then creates/reuses the thread folder and loads progress.

    This MUST happen before the main loop determines page_num.
    """

    global thread_title

    url = f"{base_url}p{start_page}"

    driver.get(url)

    time.sleep(1)

    thread_title = driver.title.strip()

    create_thread_output_folder()


def fetch_page(page_num):

    url = f"{base_url}p{page_num}"

    driver.get(url)

    time.sleep(1)  # Undviker bot-detection

    if (
        "captcha" in driver.page_source.lower()
        or "säkerhetskontroll" in driver.page_source.lower()
    ):

        print(
            f"\033[91mCAPTCHA eller säkerhetssida på sida "
            f"{page_num}. Hoppar över...\033[0m"
        )

        if page_num not in failed_pages:
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
# INITIALIZE THREAD BEFORE MAIN LOOP
# ---------------------------------------------------------

try:

    initialize_thread()

    print(
        f"Börjar läsa tråd: {thread_title}"
    )

    # -----------------------------------------------------
    # Determine where to start
    # -----------------------------------------------------

    if resume_page is not None:

        # Existing thread.
        #
        # The last saved page is deliberately scanned again.
        page_num = resume_page

        # Remove the old copy of this page before rescanning.
        remove_page_from_saved_content(
            page_num
        )

    else:

        # New thread.
        page_num = start_page

    print(
        f"Startar skanning från sida {page_num}"
    )

    # ---------------------------------------------------------
    # Main loop
    # ---------------------------------------------------------

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

            if page_num not in failed_pages:

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

        # A page that loaded successfully no longer belongs
        # in the failed-page list.
        if page_num in failed_pages:

            failed_pages.remove(
                page_num
            )

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