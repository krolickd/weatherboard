import datetime
import requests
import os
from io import BytesIO
import pytz
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, send_file, request
from waitress import serve
from weather import WeatherClient

IMAGE_SIZE = (600, 448)
WHITE = 0
BLACK = 2
RED = 1
PALETTE = [255, 255, 255, 200, 0, 0, 0, 0, 0]
app = Flask(__name__)
fonts = {}
icons = {}

PORT = int(os.environ.get('PORT', 80))

@app.route("/")
def index():
    # Get API key
    api_key = request.args.get("api_key")
    if not api_key:
        return '{"error": "no_api_key"}'

    # Render
    composer = ImageComposer(
        api_key,
        lat=request.args.get("latitude", "39.75"),
        long=request.args.get("longitude", "-104.90"),
        timezone=request.args.get("timezone", "America/Denver"),
    )
    image = composer.render()
    # Send to client
    output = BytesIO()
    image.save(output, "PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png")


class ImageComposer:
    def __init__(self, api_key, lat, long, timezone):
        self.api_key = api_key
        self.lat = lat
        self.long = long

    def render(self):
        # Fetch weather
        weather = WeatherClient(self.lat, self.long)
        weather.load(self.api_key)
        self.timezone = pytz.timezone(weather.get_timezone())
        
        # Work out time
        now = datetime.datetime.now(self.timezone)

        # Create image
        self.image = Image.new("P", IMAGE_SIZE, 0)
        self.image.putpalette(PALETTE)
        
        # Draw on date
        self.draw = ImageDraw.ImageDraw(self.image)
        left = 20
        top = 10
        self.draw_text(
            pos=(left, top), text=now.strftime("%A"), colour=BLACK, font=("light", 60),
        )
        top += 65
        day_size = self.draw_text(
            pos=(left, top),
            text=now.strftime("%d").lstrip("0"),
            colour=RED,
            font=("regular", 30),
        )
        left += day_size[0] + 2
        th = {
            "01": "st",
            "02": "nd",
            "03": "rd",
            "21": "st",
            "22": "nd",
            "23": "rd",
            "31": "st",
        }.get(now.strftime("%d"), "th")
        th_size = self.draw_text(
            pos=(left, top), text=th, colour=RED, font=("regular", 20)
        )
        left += th_size[0] + 6
        self.draw_text(
            pos=(left, 75), text=now.strftime("%B"), colour=BLACK, font=("bold", 30),
        )
        
        # Draw on weather header
        self.draw_text(
            pos=(470, 10),
            text=round(weather.temp_current()),
            colour=BLACK,
            font=("regular", 90),
            align="right",
        )
        self.draw_text(
            pos=(470, 20), text="°F", colour=BLACK, font=("regular", 28), align="left",
        )
        temp_min, temp_max = weather.temp_range_24hr()
        self.draw_text(
            pos=(550, 15),
            text=round(temp_max),
            colour=RED,
            font=("regular", 40),
            align="centre",
        )
        self.draw_text(
            pos=(550, 60),
            text=round(temp_min),
            colour=BLACK,
            font=("regular", 40),
            align="centre",
        )
        
        # Draw immediate weather
        for (time_offset, left) in [(0, 30), (2600 * 2, 150), (3600 * 6, 270)]:
            top = 125
            summary = weather.hourly_summary(time_offset)
            self.draw_weather_column(summary, top, left)
        
        # Draw tomorrow
        left = 450
        summary = weather.daily_summary(1)
        self.draw_weather_column(summary, top, left)
        
        # Draw on data footer
        left = 20
        top = 390
        
        #sunrise
        self.draw_icon("sunrise", (left, top), (50, 50))
        left += 50
        self.draw_text(
            pos=(left + 5, top + 10),
            text=weather.sunrise().astimezone(self.timezone).strftime("%H:%M").lstrip("0"),
            colour=BLACK,
            font=("bold", 30),
        )
        
        #sunset
        left = 180
        self.draw_icon("sunset", (left, top), (50, 50))
        left += 50
        self.draw_text(
            pos=(left + 5, top + 10),
            text=weather.sunset().astimezone(self.timezone).strftime("%H:%M").lstrip("0"),
            colour=BLACK,
            font=("bold", 30),
        )

        #uv-index
        left = 350
        self.draw_icon("uv-index", (left, top), (50, 50))
        left += 50

        self.draw_text(
            pos=(left + 5, top + 10),
            text=int(weather.uvi_current()),
            colour=BLACK,
            font=("bold", 30),
        )

        #humidity
        left = 460
        self.draw_icon("humidity", (left, top), (50, 50))
        left += 50

        self.draw_text(
            pos=(left + 5, top + 10),
            text=weather.humidity_current(),
            colour=BLACK,
            font=("bold", 30),
        )

        # Done!
        return self.image

    def draw_weather_column(self, summary, top, left):
        # Weather icon
        self.draw_icon(summary["icon"], (left, top + 35), (100, 100))
        
        # Date/time heading
        if "date" in summary:
            time_text = summary["date"].astimezone(self.timezone).strftime("%A").lstrip("0").title()
            
        else:
            time_text = summary["time"].astimezone(self.timezone).strftime("%I%p").lstrip("0").lower()
            
        self.draw_text(
            pos=(left + 50, top),
            text=time_text,
            colour=BLACK,
            font=("bold", 25),
            align="centre",
        )
        # Temperature
        if "temperature_range" in summary:
            self.draw_text(
                pos=(left + 20, top + 140),
                text=round(summary["temperature_range"][1]),
                colour=RED,
                font=("regular", 30),
                align="centre",
            )
            self.draw_text(
                pos=(left + 50, top + 140),
                text="/",
                colour=BLACK,
                font=("regular", 30),
                align="centre",
            )
            self.draw_text(
                pos=(left + 80, top + 140),
                text=round(summary["temperature_range"][0]),
                colour=BLACK,
                font=("regular", 30),
                align="centre",
            )
        else:
            temp_width = (
                self.size_text(round(summary["temperature"]), ("regular", 30))[0]
                + self.size_text("°F", ("regular", 20))[0]
                + 3
            )
            self.draw_text(
                pos=(left + 50 - (temp_width / 2), top + 140),
                text=round(summary["temperature"]),
                colour=RED,
                font=("regular", 30),
                align="left",
            )
            self.draw_text(
                pos=(left + 50 + (temp_width / 2), top + 150),
                text="°F",
                colour=BLACK,
                font=("regular", 20),
                align="right",
            )
        # Wind
        wind_width = (
            self.size_text(round(summary["wind"]), ("regular", 30))[0]
            + self.size_text("mph", ("regular", 16))[0]
            + 3
        )
        self.draw_text(
            pos=(left + 50 - (wind_width / 2), top + 180),
            text=round(summary["wind"]),
            colour=BLACK,
            font=("regular", 30),
            align="left",
        )
        self.draw_text(
            pos=(left + 50 + (wind_width / 2), top + 190),
            text="mph",
            colour=BLACK,
            font=("regular", 16),
            align="right",
        )

        # Percipitation
        percip_width = (
            self.size_text(round(summary["percip"]*100), ("regular", 30))[0]
            + self.size_text("%", ("regular", 20))[0]
            + 3
        )
        self.draw_text(
            pos=(left + 50 - (percip_width / 2), top + 220),
            text=round(summary["percip"]*100),
            colour=BLACK,
            font=("regular", 30),
            align="left",
        )
        self.draw_text(
            pos=(left + 50 + (percip_width / 2), top + 230),
            text="%",
            colour=BLACK,
            font=("regular", 20),
            align="right",
        )

    def draw_text(self, pos, text, colour, font, align="left"):
        """
        Draws text and returns its size
        """
        # Get font
        if font not in fonts:
            fonts[font] = ImageFont.truetype(
                "Roboto-%s.ttf" % font[0].title(), size=font[1]
            )
        # Calculate size
        size = self.draw.textsize(str(text), font=fonts[font])
        # Draw
        x, y = pos
        if align == "right":
            x -= size[0]
        elif align.startswith("cent"):
            x -= size[0] / 2
        self.draw.text((x, y), str(text), fill=colour, font=fonts[font])
        return size

    def size_text(self, text, font):
        """
        Returns text size
        """
        # Get font
        if font not in fonts:
            fonts[font] = ImageFont.truetype(
                "Roboto-%s.ttf" % font[0].title(), size=font[1]
            )
        # Calculate size
        return self.draw.textsize(str(text), font=fonts[font])

    def draw_icon(self, icon, pos, size):
        """
        Draws an icon file onto the image.
        """
        # Load icon
        if icon not in icons:
            raw_icon = Image.open(
                os.path.join(os.path.dirname(__file__), "icons", icon + ".png")
            ).convert("RGBA")
            palette_icon = Image.new("P", raw_icon.size, 0)
            for x in range(raw_icon.size[0]):
                for y in range(raw_icon.size[1]):
                    color = raw_icon.getpixel((x, y))
                    new_color = BLACK
                    if color[3] < 125:
                        new_color = WHITE
                    elif color[0] > 125:
                        if color[1] < 125:
                            new_color = RED
                        else:
                            new_color = WHITE
                    palette_icon.putpixel((x, y), new_color)
            icons[icon] = palette_icon
        # Resize
        icon_image = icons[icon].resize(size)
        self.image.paste(icon_image, pos)