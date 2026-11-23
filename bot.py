import os
import re
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ---------- 货币转换（免费 Open Access API，无需 Key）[citation:5] ----------
def convert_currency(amount: float, from_code: str, to_code: str) -> str:
    url = f"https://open.er-api.com/v6/latest/{from_code.upper()}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("result") != "success":
            return "❌ 无法获取汇率数据，请检查货币代码（如 USD, EUR, NGN）。"
        rates = data.get("rates", {})
        target = to_code.upper()
        if target not in rates:
            return f"❌ 不支持的货币代码：{target}"
        rate = rates[target]
        result = amount * rate
        return f"💱 {amount:,.2f} {from_code.upper()} = {result:,.2f} {target}\n📅 汇率更新：{data.get('time_last_update_utc', 'N/A')}"
    except Exception as e:
        logger.error(f"Currency error: {e}")
        return "❌ 转换失败，请稍后重试。"

# ---------- 单位转换（硬编码常见换算） ----------
UNIT_MAP = {
    # 长度 (基准: 米)
    "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
    "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
    # 重量 (基准: 千克)
    "mg": 0.000001, "g": 0.001, "kg": 1.0, "t": 1000.0,
    "oz": 0.0283495, "lb": 0.453592,
}

def convert_unit(amount: float, from_unit: str, to_unit: str) -> str:
    from_u = from_unit.lower()
    to_u = to_unit.lower()
    if from_u in UNIT_MAP and to_u in UNIT_MAP:
        base = amount * UNIT_MAP[from_u]
        result = base / UNIT_MAP[to_u]
        return f"📏 {amount} {from_u} = {result:,.4f} {to_u}"
    # 温度特殊处理
    temps = {"c", "f", "k"}
    if from_u in temps and to_u in temps:
        if from_u == "c":
            c = amount
        elif from_u == "f":
            c = (amount - 32) * 5/9
        else:  # k
            c = amount - 273.15
        if to_u == "c":
            result = c
        elif to_u == "f":
            result = c * 9/5 + 32
        else:
            result = c + 273.15
        return f"🌡️ {amount}°{from_u.upper()} = {result:,.2f}°{to_u.upper()}"
    return "❌ 不支持的单位，支持：长度(mm,cm,m,km,in,ft,yd,mi)、重量(mg,g,kg,t,oz,lb)、温度(c,f,k)"

# ---------- 消息解析器 ----------
# 支持格式: "100 usd to ngn" 或 "5 km to miles" 或 "100 usd ngn"
PATTERN = re.compile(r"([\d.]+)\s*([a-zA-Z]+)\s*(?:to\s+)?([a-zA-Z]+)", re.IGNORECASE)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = PATTERN.search(text)
    if not match:
        await update.message.reply_text(
            "请按格式输入，例如：\n`100 usd to ngn`\n`5 km to miles`\n`30 c to f`",
            parse_mode="Markdown"
        )
        return
    try:
        amount = float(match.group(1))
    except ValueError:
        await update.message.reply_text("金额格式不正确。")
        return
    from_code = match.group(2).lower()
    to_code = match.group(3).lower()

    # 优先判断是否为货币代码（3个字母且不在单位表中）
    known_currencies = {"usd","eur","gbp","ngn","jpy","cny","cad","aud","chf","inr","zar","kes","ghs"}
    if from_code in known_currencies or (len(from_code) == 3 and from_code not in UNIT_MAP and from_code not in {"cm","km","mm","kg","mg"}):
        reply = convert_currency(amount, from_code, to_code)
    else:
        reply = convert_unit(amount, from_code, to_code)

    await update.message.reply_text(reply)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔁 *单位 & 货币转换 Bot*\n\n"
        "直接发送消息即可转换：\n"
        "• `100 usd to ngn` — 货币转换\n"
        "• `5 km to miles` — 长度转换\n"
        "• `30 c to f` — 温度转换\n"
        "• `2 kg to lb` — 重量转换\n\n"
        "货币汇率来自 ExchangeRate-API 免费接口，每日更新 [citation:5]。",
        parse_mode="Markdown"
    )

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Converter bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
