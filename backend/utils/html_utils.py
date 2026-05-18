
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text_part = data.strip()
        if text_part:
            self.parts.append(text_part)

    def text(self):
        return "\n".join(self.parts)


def html_to_text(html):
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()
