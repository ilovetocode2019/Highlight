import discord

def quote(message, reply, *, quote=None):
    quote = quote or message.content
    return f"> {discord.utils.escape_mentions(quote)} \n{message.author.mention} {reply}"

def join(iterable, *, seperator=", ", last="or"):
    if len(iterable) == 0:
        return ""
    if len(iterable) == 1:
        return iterable[0]
    if len(iterable) == 2:
        return f"{iterable[0]} and {iterable[1]}"

    return seperator.join(iterable[:-1]) + f"{seperator}{last} {iterable[-1]}"

class plural:
    def __init__(self, value, *, end="s"):
        self.value = value
        self.end = end

    def __format__(self, format_spec):
        if self.value == 1:
            return f"{self.value} {format_spec}"
        else:
            return f"{self.value} {format_spec}{self.end}"

class Tabulate:
    def __init__(self):
        self.widths = []
        self.columns = []
        self.rows = []

    def add_column(self, column):
        self.columns.append(column)
        self.widths.append(len(column) + 2)

    def add_columns(self, columns):
        for column in columns:
            self.add_column(column)

    def add_row(self, row):
        values = [str(value) for value in row]
        self.rows.append(values)
        for counter, value in enumerate(values):
            width = len(value)+2
            if width > self.widths[counter]:
                self.widths[counter] = width

    def add_rows(self, rows):
        for row in rows:
            self.add_row(row)

    def draw_row(self, row):
        drawing = "║".join([f"{value:^{self.widths[counter]}}" for counter, value in enumerate(row)])
        return f"║{drawing}║"

    def draw(self):
        top = "╦".join(["═"*width for width in self.widths])
        top = f"╔{top}╗"

        bottom = "╩".join(["═"*width for width in self.widths])
        bottom = f"╚{bottom}╝"

        seperator = "╬".join(["═"*width for width in self.widths])
        seperator = f"║{seperator}║"

        drawing = [top]
        drawing.append(self.draw_row(self.columns))
        drawing.append(seperator)

        for row in self.rows:
            drawing.append(self.draw_row(row))
        drawing.append(bottom)

        return "\n".join(drawing)

    def __str__(self):
        return self.draw()

    def __repr__(self):
        return self.draw()
