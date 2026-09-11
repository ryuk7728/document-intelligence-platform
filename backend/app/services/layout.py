from dataclasses import dataclass, field
from statistics import median


@dataclass(slots=True)
class TextToken:
    text: str
    page_number: int
    confidence: float
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def bounding_box(self) -> list[float]:
        return [round(self.x0, 5), round(self.y0, 5), round(self.x1, 5), round(self.y1, 5)]


@dataclass(slots=True)
class TextRow:
    page_number: int
    tokens: list[TextToken] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(token.text.strip() for token in sorted(self.tokens, key=lambda item: item.x0) if token.text.strip())

    @property
    def y_center(self) -> float:
        return median(token.y_center for token in self.tokens)

    @property
    def height(self) -> float:
        return median(max(token.height, 0.001) for token in self.tokens)

    @property
    def bounding_box(self) -> list[float]:
        return [
            round(min(token.x0 for token in self.tokens), 5),
            round(min(token.y0 for token in self.tokens), 5),
            round(max(token.x1 for token in self.tokens), 5),
            round(max(token.y1 for token in self.tokens), 5),
        ]


@dataclass(slots=True)
class PageText:
    page_number: int
    width: int
    height: int
    method: str
    tokens: list[TextToken]

    @property
    def rows(self) -> list[TextRow]:
        return group_tokens_into_rows(self.tokens)

    @property
    def text(self) -> str:
        return "\n".join(row.text for row in self.rows)


def group_tokens_into_rows(tokens: list[TextToken]) -> list[TextRow]:
    rows: list[TextRow] = []
    for token in sorted(tokens, key=lambda item: (item.y_center, item.x0)):
        best_row: TextRow | None = None
        best_distance = float("inf")
        for row in rows[-8:]:
            distance = abs(row.y_center - token.y_center)
            tolerance = max(row.height, token.height, 0.006) * 0.65
            if distance <= tolerance and distance < best_distance:
                best_row = row
                best_distance = distance
        if best_row is None:
            rows.append(TextRow(page_number=token.page_number, tokens=[token]))
        else:
            best_row.tokens.append(token)
    return sorted(rows, key=lambda row: row.y_center)

