# FlashbackRipper

Python script för att spara en hel Flashback-tråd till en textfil. Alla inlägg struktureras med datum, användarnamn och sidnummer.


## Prerequisites

- Python 3.7+
- Google Chrome
- Chromedriver.exe för din Chrome-version placerad i samma mapp som scriptet. Sidan där du laddar ned den finner du [här](https://googlechromelabs.github.io/chrome-for-testing/).
- Python libraries `selenium` och `beautifulsoup4` installerade:
```bash
pip install selenium beautifulsoup4
```


## Hur man använder

### ripper.py
Kör i cmd med:
```bash
cd <project-directory>
py ripper.py
```

Hämtar alla sidor från en Flashback-tråd och sparar inlägg, användarnamn och datum till `content.txt`.  
Om någon sida misslyckas sparas den i `failed_pages.txt` och skriver ut det i terminalen.

Programmet hanterar CAPTCHA- och säkerhetssidor genom att hoppa över dem. Scriptet pausar också ibland för att undvika bot-detection.

För att använda:
1. Redigera `settings.cfg` och fyll i base URL, start_page och end_page.
2. Kör scriptet.


### settings.cfg

- **base_url**: URL till tråden (utan sidnummer).
- **start_page**: Första sidan att hämta.
- **end_page**: Sista sidan att hämta (sätt till `-1` för att hämta alla sidor).

- **chromedriver**: Filnamnet på Chromedriver.
- **output_file**: Filnamn för där innehållet från Flashback sparas.
- **failed_pages_file**: Filnamn för där misslyckade sidonummer sparas.


### Notes

Scriptet är testat på Windows 10 och bör fungera på andra system med mindre justeringar.


## License

This project is licensed under the [MIT License](LICENSE).

