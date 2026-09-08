from collections import namedtuple

# kind is "text", "image", or "files". For text, data is a str and mime is
# None. For image, data is raw bytes and mime is the target used to fetch
# it (e.g. "image/png"). For files, data is text/uri-list text and mime is
# "text/uri-list".
Clip = namedtuple("Clip", ["kind", "data", "mime"])

TEXT_TARGETS = {"UTF8_STRING", "STRING", "TEXT", "text/plain", "text/plain;charset=utf-8"}
