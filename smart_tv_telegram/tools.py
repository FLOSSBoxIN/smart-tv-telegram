import asyncio
import concurrent.futures
import re
import typing


range_regex = re.compile(r"bytes=([0-9]+)-")
named_media_types = ["document", "video", "audio", "video_note", "animation"]

_executor = concurrent.futures.ThreadPoolExecutor()
_loop = asyncio.get_event_loop()


def ascii_only(haystack: str) -> str:
    return "".join(c for c in haystack if ord(c) < 128)


def run_method_in_executor(func):
    async def wraps(*args):
        return await _loop.run_in_executor(_executor, func, *args)
    return wraps


def parse_http_range(http_range: str, block_size: int) -> typing.Tuple[int, int]:
    matches = range_regex.search(http_range)

    if matches is None:
        raise ValueError()

    offset = matches.group(1)

    if not offset.isdigit():
        raise ValueError()

    offset = int(offset)
    safe_offset = (offset // block_size) * block_size
    data_to_skip = offset - safe_offset

    return safe_offset, data_to_skip
