import os
from aiofiles import open as aopen
from loguru import logger
from lxml import etree
from pathlib import Path


import asyncio
import httpx

URL_BLOGGER = "https://vrelnir.blogspot.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.60",
    "cookie": os.getenv("COOKIE")
}
APK_URL_TEMP = "https://pixeldrain.com/u/chCgZGVa"


async def main():
    async with httpx.AsyncClient(headers=HEADERS, timeout=60) as client:
        latest_url = await fetch_latest_url(client)
        try:
            apk_url = await fetch_download_url(latest_url, client)
        except IndexError as e:
            apk_url = APK_URL_TEMP
        apk_download_url, apk_filename = await fetch_apk_url(apk_url, client)
        await download_apk(apk_download_url, apk_filename, client)


async def fetch_latest_url(client: httpx.AsyncClient) -> str:
    response = await client.get(URL_BLOGGER)
    text = response.text
    html = etree.HTML(text)
    latest_url = html.xpath('//a[contains(text(),"Degrees of Lewdity version")]/attribute::href')
    return latest_url[0]


async def fetch_download_url(latest_url: str, client: httpx.AsyncClient) -> str:
    response = await client.get(latest_url, follow_redirects=True)
    text = response.text
    with open("warning.html", "wb") as fp:
        fp.write(response.content)
    if "https://www.blogger.com/age-verification.g?" in text:  # 敏感内容警告
        html = etree.HTML(text)
        confirm_url = html.xpath('//a[@class="maia-button maia-button-primary"]/attribute::href')[0]
        response = await client.get(confirm_url, follow_redirects=False)
        location_url = response.headers.get("location", "")

        response = await client.get(location_url, follow_redirects=False)
        final_url = response.headers.get("location", "")

        response = await client.get(final_url, follow_redirects=False)
        text = response.text

    html = etree.HTML(text)
    download_urls = html.xpath("//a[text()='Android version']/attribute::href")
    return download_urls[-1]


async def fetch_apk_url(apk_url: str, client: httpx.AsyncClient) -> tuple[str, str]:
    response = await client.get(apk_url)
    text = response.text
    html = etree.HTML(text)
    pixel_file_name = html.xpath("//meta[contains(@content,'DegreesofLewdity')]/attribute::content")[0]
    pixel_file_id = apk_url.split("/")[-1]
    pixel_download_url = f"https://pixeldrain.com/api/file/{pixel_file_id}?download"
    return pixel_download_url, pixel_file_name


async def download_apk(apk_download_url: str, apk_filename: str, client: httpx.AsyncClient):
    chunks = await chunk_split(apk_download_url, client, 64)
    tasks = [
        chunk_download(apk_download_url, client, start, end, idx, len(chunks), Path("dol.apk"))
        for idx, (start, end) in enumerate(chunks)
    ]
    await asyncio.gather(*tasks)


async def chunk_split(url: str, client: httpx.AsyncClient, chunk: int = 2) -> list[list[int]]:
    """给大文件切片"""
    response = await client.head(url)
    filesize = int(response.headers["Content-Length"])
    step = filesize // chunk
    arr = range(0, filesize, step)
    result = [
        [arr[i], arr[i + 1] - 1]
        for i in range(len(arr) - 1)
    ]
    result[-1][-1] = filesize - 1
    return result


async def chunk_download(url: str, client: httpx.AsyncClient, start: int, end: int, idx: int, full: int, save_path: Path, headers_: dict = None):
    """切片下载"""
    if not save_path.exists():
        with open(save_path, "wb") as fp:
            pass
    headers = {"Range": f"bytes={start}-{end}"} | headers_ if headers_ else {"Range": f"bytes={start}-{end}"}
    response = await client.get(url, headers=headers, follow_redirects=True, timeout=60)
    async with aopen(save_path, "rb+") as fp:
        await fp.seek(start)
        await fp.write(response.content)
        logger.info(f"\t- Slice {idx + 1} / {full} downloaded")


if __name__ == '__main__':
    asyncio.run(main())
