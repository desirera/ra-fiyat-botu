import os
import io
import logging
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# RA FİYAT BOTU
# =========================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

BINANCE_API = "https://api.binance.com/api/v3"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Binance'teki USDT paritelerini hafızaya al
def get_symbols():
    try:
        data = requests.get(
            f"{BINANCE_API}/exchangeInfo",
            timeout=10
        ).json()

        symbols = {}

        for item in data["symbols"]:
            if (
                item["status"] == "TRADING"
                and item["quoteAsset"] == "USDT"
                and item["isSpotTradingAllowed"]
            ):
                symbols[item["baseAsset"].lower()] = item["symbol"]

        return symbols

    except Exception as e:
        logging.error(f"Sembol listesi alınamadı: {e}")
        return {}


SYMBOLS = get_symbols()


def format_price(price):
    if price >= 1000:
        return f"{price:,.2f}"
    elif price >= 1:
        return f"{price:,.4f}"
    elif price >= 0.01:
        return f"{price:,.6f}"
    else:
        return f"{price:,.8f}"


def get_market_data(symbol):
    ticker = requests.get(
        f"{BINANCE_API}/ticker/24hr",
        params={"symbol": symbol},
        timeout=10
    ).json()

    klines = requests.get(
        f"{BINANCE_API}/klines",
        params={
            "symbol": symbol,
            "interval": "15m",
            "limit": 48
        },
        timeout=10
    ).json()

    return ticker, klines


def create_chart(symbol, ticker, klines):
    times = [
        datetime.fromtimestamp(
            int(k[0]) / 1000,
            tz=timezone.utc
        )
        for k in klines
    ]

    opens = [float(k[1]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) for k in klines]

    fig, ax = plt.subplots(figsize=(12, 6))

    # Mumlar
    for i in range(len(klines)):
        color = "green" if closes[i] >= opens[i] else "red"

        # Fitil
        ax.plot(
            [i, i],
            [lows[i], highs[i]],
            color=color,
            linewidth=1
        )

        # Gövde
        bottom = min(opens[i], closes[i])
        height = abs(closes[i] - opens[i])

        if height == 0:
            height = max(closes[i] * 0.0002, 0.00000001)

        ax.add_patch(
            plt.Rectangle(
                (i - 0.3, bottom),
                0.6,
                height,
                facecolor=color,
                edgecolor=color
            )
        )

    # EMA 20
    ema_period = 20
    multiplier = 2 / (ema_period + 1)

    ema = []
    previous = closes[0]

    for price in closes:
        previous = (price - previous) * multiplier + previous
        ema.append(previous)

    ax.plot(
        range(len(ema)),
        ema,
        linewidth=1.5,
        label="EMA 20"
    )

    current_price = float(ticker["lastPrice"])
    change = float(ticker["priceChangePercent"])

    ax.axhline(
        current_price,
        linestyle="--",
        linewidth=1,
        alpha=0.6
    )

    ax.set_title(
        f"RA FİYAT BOTU  •  {symbol}  •  15 DAKİKA",
        fontsize=16,
        fontweight="bold"
    )

    ax.set_ylabel("USDT")
    ax.grid(alpha=0.15)
    ax.legend()

    # X ekseni
    step = max(1, len(times) // 8)

    ax.set_xticks(range(0, len(times), step))
    ax.set_xticklabels(
        [
            times[i].strftime("%H:%M")
            for i in range(0, len(times), step)
        ],
        rotation=30
    )

    plt.tight_layout()

    image = io.BytesIO()
    plt.savefig(
        image,
        format="png",
        dpi=160,
        bbox_inches="tight"
    )
    plt.close(fig)

    image.seek(0)

    return image


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🤖 RA FİYAT BOTU

Kripto fiyatlarını ve 15 dakikalık grafikleri görüntülemek için:

/btc
/eth
/sol
/bnb
/xrp
/doge

Binance'te USDT paritesi bulunan coinleri destekler.

📊 Grafik: 15 Dakikalık
💹 Veri: Binance
    """

    await update.message.reply_text(text)


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.split()[0]

    coin = command.replace("/", "").split("@")[0].lower()

    if not coin or coin in ["start", "help"]:
        return

    symbol = SYMBOLS.get(coin)

    if not symbol:
        await update.message.reply_text(
            f"❌ `{coin.upper()}` için Binance USDT paritesi bulunamadı.",
            parse_mode="Markdown"
        )
        return

    try:
        ticker, klines = get_market_data(symbol)

        price = float(ticker["lastPrice"])
        change = float(ticker["priceChangePercent"])
        high = float(ticker["highPrice"])
        low = float(ticker["lowPrice"])
        volume = float(ticker["quoteVolume"])

        chart = create_chart(symbol, ticker, klines)

        emoji = "🟢" if change >= 0 else "🔴"
        sign = "+" if change >= 0 else ""

        caption = f"""
<b>RA FİYAT BOTU</b>

💎 <b>{symbol}</b>

💰 Fiyat: <b>{format_price(price)} USDT</b>
{emoji} 24H: <b>{sign}{change:.2f}%</b>

⬆️ 24H Yüksek: {format_price(high)}
⬇️ 24H Düşük: {format_price(low)}

📊 24H Hacim: {volume:,.0f} USDT
⏱ Zaman Dilimi: <b>15 Dakika</b>

🕐 Güncelleme: {datetime.now().strftime("%H:%M:%S")}

<i>Veriler Binance üzerinden alınmaktadır.</i>
"""

        await update.message.reply_photo(
            photo=chart,
            caption=caption,
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"{symbol} hatası: {e}")

        await update.message.reply_text(
            "⚠️ Fiyat verisi alınırken bir hata oluştu. "
            "Biraz sonra tekrar dene."
        )


async def refresh_symbols(context: ContextTypes.DEFAULT_TYPE):
    global SYMBOLS

    new_symbols = get_symbols()

    if new_symbols:
        SYMBOLS = new_symbols
        logging.info(
            f"Coin listesi güncellendi: {len(SYMBOLS)} coin"
        )


def main():
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable bulunamadı."
        )

    application = Application.builder().token(TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            filters.COMMAND,
            price_command
        )
    )

    # Coin listesini her 1 saatte güncelle
    application.job_queue.run_repeating(
        refresh_symbols,
        interval=3600,
        first=3600
    )

    print("🚀 RA FİYAT BOTU AKTİF")
    print(f"📊 Desteklenen coin: {len(SYMBOLS)}")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
