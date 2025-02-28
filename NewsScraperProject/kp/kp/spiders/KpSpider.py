import scrapy
from scrapy.selector import Selector

class KpspiderSpider(scrapy.Spider):
    name = "KpSpider"
    allowed_domains = ["kp.ru"]
    start_urls = ["https://www.kp.ru/online"]
    REQUIRED_QUANTITY = 30

    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "args": [
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            "headless": True,
        },
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.article_count = 0

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                },
                callback=self.parse,
            )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        page.set_default_timeout(10000)

        await page.wait_for_timeout(10000)

        while self.article_count < self.REQUIRED_QUANTITY:
            try:

                content = await page.content()
                selector = Selector(text=content)


                articles = selector.xpath('//a[contains(@class, "sc-1tputnk-2 drlShK")]')
                current_articles = articles[: self.REQUIRED_QUANTITY - self.article_count]
                self.logger.info(f"Найдено {len(current_articles)} статей.")


                for article in current_articles:
                    article_url = article.xpath("@href").get()
                    yield response.follow(
                        article_url,
                        callback=self.parse_article,
                        meta={"playwright": True},
                    )
                    self.article_count += 1
                    if self.article_count >= self.REQUIRED_QUANTITY:
                        print(f"Достигнут лимит в {self.REQUIRED_QUANTITY} статей. Останавливаемся.")
                        break


                if self.article_count >= self.REQUIRED_QUANTITY:
                    break


                button = page.locator('//button[contains(., "Показать еще")]')
                await button.wait_for(timeout=5000)


                is_disabled = await button.is_disabled()
                if is_disabled:

                    break

                await button.scroll_into_view_if_needed()
                await button.click()
                print("Нажали кнопку 'Показать еще'.")


                await page.wait_for_timeout(7000)

            except Exception as error:
                print(f"Ошибка: {error}")
                break


        await page.close()

    def parse_article(self, response):
        title = response.xpath('//h1/text()').get(default="").strip()
        description = response.xpath('//meta[@name="description"]/@content').get(default="").strip()
        article_text = " ".join(response.xpath('//p[contains(@class, "sc-1wayp1z-16 dqbiXu")]/text()').getall()).strip()
        publication_datetime = response.xpath('//span[contains(@class, "sc-j7em19-1 dtkLMY")]/text()').getall()
        header_photo_url = response.xpath('//meta[@property="og:image"]/@content').get()
        keywords = response.xpath('//meta[@name="keywords"]/@content').get(default="").split(", ")
        authors = response.xpath('//span[contains(@class, "sc-1jl27nw-1 bmkpOs")]/text()').getall()
        source_url = response.url

        yield {
            "title": title,
            "description": description,
            "article_text": article_text,
            "publication_datetime": publication_datetime,
            "header_photo_url": header_photo_url,
            "keywords": keywords,
            "authors": authors,
            "source_url": source_url,
        }