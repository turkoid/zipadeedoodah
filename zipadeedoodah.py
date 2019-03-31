import argparse
import asyncio
import os
import sys
import time
from typing import List
from urllib.parse import ParseResult
from urllib.parse import urlparse

from aiohttp import ClientSession
from pyppeteer import launch
from pyppeteer.browser import Browser

ZIPPYSHARE_SCRIPT_ELEMENT = "document.getElementById('dlbutton')"


class InvalidZippyShareLink(Exception):
    def __init__(self, link: str):
        self.link = link

    def __str__(self):
        return f"Invalid Zippyshare URL: {self.link}"


class ZippyMetadata:
    def __init__(self, url: str):
        self.url: str = url
        result: ParseResult = urlparse(url)
        self.base_url = f"{result.scheme}://{result.netloc}"
        self.script: str = None
        self.download_path: str = None

    @property
    def download_url(self) -> str:
        return f"{self.base_url}{self.download_path}"


class ZipaDeeDooDah:
    def __init__(self):
        self.links: List[ZippyMetadata] = None
        self.target_directory: str = None
        self._parse_arguments()

    def _build_arg_parser(self):
        parser = argparse.ArgumentParser(description="Downloads Zippyshare links")
        parser.add_argument(
            "-d", "--directory", default="./", help="Target download directory"
        )
        parser.add_argument("-f", "--file", help="A file contain with Zippyshare links")
        parser.add_argument("-l", "--links", nargs="*", help="Zippyshare URLs")
        return parser

    def _parse_arguments(self):
        parser = self._build_arg_parser()
        args = parser.parse_args()

        if args.file and args.links:
            sys.exit("--file and --links cannot be used together")
        links: list = None
        if args.file:
            with open(args.file, "r") as f:
                links = [
                    link.strip() for link in f.readlines() if link and link.strip()
                ]
        if args.links:
            links = args.links
        if not links:
            sys.exit("No links found!")
        self.links = [ZippyMetadata(link) for link in links]

        self.target_directory = args.directory
        if not os.path.exists(self.target_directory):
            create_directory = input(
                f"{self.target_directory} does not exist. Do you want to create it? "
            )
            create_directory = create_directory or "n"
            create_directory = create_directory.strip().lower()
            if create_directory in ["y", "yes"]:
                os.makedirs(self.target_directory)
            else:
                sys.exit(f"{self.target_directory} does not exist.")

    @staticmethod
    def get_script_from_html(html: str) -> str:
        link_setter_index = html.find(f"{ZIPPYSHARE_SCRIPT_ELEMENT}.href = ")
        script_start = '<script type="text/javascript">'
        script_start_index = html.rfind(script_start, 0, link_setter_index)
        script_start_index += len(script_start)
        script_end = "</script>"
        script_end_index = html.find(script_end, link_setter_index)
        script = html[script_start_index:script_end_index]
        return script

    async def _get_download_link(
        self, metadata: ZippyMetadata, browser: Browser, session: ClientSession
    ) -> bool:
        async with session.get(metadata.url) as response:
            assert response.status == 200
            html = await response.text()
            script = ZipaDeeDooDah.get_script_from_html(html)
            fake_script = script.replace(ZIPPYSHARE_SCRIPT_ELEMENT, "dlbutton")
            render_script = (
                f"() => {{ var dlbutton = {{}}; {fake_script} return dlbutton.href; }}"
            )
            page = await browser.newPage()
            download_path = await page.evaluate(render_script)
            await page.close()
            metadata.script = script
            metadata.download_path = download_path
            return True

    async def _get_download_links(self) -> List[str]:
        browser = await launch(autoClose=False)
        async with ClientSession() as session:
            tasks = [
                self._get_download_link(metadata, browser, session)
                for metadata in self.links
            ]
            _ = await asyncio.gather(*tasks)
        await browser.close()
        return [metadata.download_url for metadata in self.links]

    def get_download_links(self) -> List[str]:
        asyncio.run(self._get_download_links())


if __name__ == "__main__":
    s = time.perf_counter()
    zippy = ZipaDeeDooDah()
    zippy.get_download_links()
    elapsed = time.perf_counter() - s
    print(f"Scraped {len(zippy.links)} links in {elapsed:0.2f} seconds.")
