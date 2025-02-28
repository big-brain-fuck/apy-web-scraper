# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


import pymongo

class MongoDBPipeline:
    def __init__(self, mongo_uri, mongo_db, mongo_collection):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=crawler.settings.get("MONGO_DATABASE", "news_db"),
            mongo_collection=crawler.settings.get("MONGO_COLLECTION", "news"),
        )

    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item, spider):
        self.db[self.mongo_collection].update_one(
            {"source_url": item["source_url"]}, {"$set": dict(item)}, upsert=True
        )
        return item

import base64
from io import BytesIO
from PIL import Image
import aiohttp
from aiohttp.client_exceptions import InvalidURL

class PhotoDownloaderPipeline:
    def __init__(self, result_image_quality: int):
        self.result_image_quality = result_image_quality

    @classmethod
    def from_crawler(cls, crawler):
        result_image_quality = crawler.settings.get("RESULT_IMAGE_QUALITY", 35)
        return cls(result_image_quality=result_image_quality)

    def compress_image(self, image_content: bytes):
        input_buffer = BytesIO(image_content)
        output_buffer = BytesIO()
        img = Image.open(input_buffer)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(output_buffer, format="JPEG", quality=self.result_image_quality, optimize=True)
        return output_buffer.getvalue()

    async def _download_photo_to_base64(self, url: str):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        return ""
                    content = await response.read()
                    compressed_bytes = self.compress_image(image_content=content)
                    return base64.b64encode(compressed_bytes).decode("utf-8")
            except (InvalidURL, aiohttp.ClientError):
                return ""

    async def process_item(self, item, spider):
        if item.get("header_photo_url"):
            item["header_photo_base64"] = await self._download_photo_to_base64(item["header_photo_url"])
        return item
