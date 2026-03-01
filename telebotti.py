import os
import telebot
import random
import io
import base64
import time
import threading
import sys
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import defaultdict
from dotenv import load_dotenv
from openai import OpenAI

# Konfiguroidaan lokitus Raspberryä varten
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("botti.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.error("TELEGRAM_TOKEN tai OPENAI_API_KEY puuttuu .env tiedostosta!")
    sys.exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
try:
    BOT_INFO = bot.get_me()
    BOT_USERNAME = f"@{BOT_INFO.username}"
except Exception as e:
    logger.error(f"Virhe yhdistettäessä Telegramiin: {e}")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILE = "user_memory.json"
MAX_MEMORY = 16

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return defaultdict(list, data)
        except Exception as e:
            logger.error(f"Virhe muistin latauksessa: {e}")
    return defaultdict(list)

def save_memory_to_disk():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(user_memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Virhe muistin tallennuksessa: {e}")

user_memory = load_memory()
user_last_message = {}
COOLDOWN_SECONDS = 1.5 # Hieman nopeampi vaste


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message,
        "apu botti\n"
        "nyt tä\n"
        "/roll [max]\n"
        "/kuva prompt\n"
        "/reset\n"
        f"tägää {BOT_USERNAME} jos ryhmä"
    )


@bot.message_handler(commands=['reset'])
def reset_memory(message):
    user_id = str(message.from_user.id)
    user_memory[user_id] = []
    save_memory_to_disk()
    bot.reply_to(message, "muisti pois\nnyt tä")


@bot.message_handler(commands=['roll'])
def roll_command(message):
    try:
        args = message.text.split()
        max_value = 100
        if len(args) > 1:
            max_value = int(args[1])

        if max_value < 1:
            max_value = 1
            
        roll = random.randint(0, max_value)
        bot.reply_to(message, f"roll\n0-{max_value}\nsai {roll}")

    except ValueError:
        bot.reply_to(message, "numero sekas\napu ei tajuu (laita numero)")
    except Exception as e:
        logger.error(f"Roll virhe: {e}")


@bot.message_handler(commands=['kuva'])
def generate_image(message):
    try:
        prompt = message.text.replace("/kuva", "").strip()

        if not prompt:
            bot.reply_to(message, "kirjota jotai\nälä tyhjä")
            return

        bot.send_chat_action(message.chat.id, 'upload_photo')
        logger.info(f"Generoidaan kuva promptilla: {prompt}")

        result = client.images.generate(
            model="dall-e-2",
            prompt=prompt,
            size="1024x1024",
            response_format="b64_json"
        )

        image_base64 = result.data[0].b64_json
        image_bytes = io.BytesIO(base64.b64decode(image_base64))
        bot.send_photo(message.chat.id, image_bytes)

    except Exception as e:
        logger.error(f"Kuvavirhe: {e}")
        bot.reply_to(message, "kuva hajos nyt tä\nopenai suuttu tai jtn")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_id = str(message.from_user.id)
        now = time.time()

        if user_id in user_last_message:
            if now - user_last_message[user_id] < COOLDOWN_SECONDS:
                return

        user_last_message[user_id] = now

        chat_type = message.chat.type
        text = message.text if message.text else ""

        is_private = chat_type == "private"
        is_mentioned = BOT_USERNAME in text
        is_reply_to_bot = (
            message.reply_to_message and
            message.reply_to_message.from_user.id == BOT_INFO.id
        )

        if not (is_private or is_mentioned or is_reply_to_bot):
            return

        bot.send_chat_action(message.chat.id, "typing")

        clean_text = text.replace(BOT_USERNAME, "").strip()
        if not clean_text:
            return

        user_memory[user_id].append({
            "role": "user",
            "content": clean_text
        })

        user_memory[user_id] = user_memory[user_id][-MAX_MEMORY:]

        system_prompt = (
            "OHJEET: vastaa minulle tästälähtien kuten apu apustaja (se tuttu kaveri ylilaudalta) vastaisi, käytä referenssinä vaikka ylilaudan apuapustajaketjuja, apu ei ole kovin fiksu. ymmärräthän? sisällytä tekstiin apu tyypillisiä kirjoitusvirheitä"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=1.2,
            top_p=0.95,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "assistant",
                    "content": "apu tietää tä\nporot syö sammalta\nja ruohoo\nne kaivaa lumen alta\njoo varmaa näin\n\nen tiiä mut ehkä"
                }
            ] + user_memory[user_id]
        )

        reply_text = response.choices[0].message.content

        chaos_pool = [
            "apu miettii kovaa",
            "nyt tä outo",
            "en tiiä mut ehkä näin",
            "joo varmaa",
            "hetki olin hukas",
            "aivot lagaa",
            "apu sekasin vähä"
        ]

        # 40% chance lisätä extra hajontaa (laskettu hieman ärsyttävyyden vähentämiseksi)
        if random.random() < 0.4:
            reply_text += "\n\n" + random.choice(chaos_pool)

        user_memory[user_id].append({
            "role": "assistant",
            "content": reply_text
        })
        
        save_memory_to_disk()
        bot.reply_to(message, reply_text)

    except Exception as e:
        logger.error(f"Viestinkäsittelyvirhe: {e}")


logger.info(f"🐸 APU ABYSS MODE ({BOT_USERNAME}) käynnis nyt tä")

def start_health_server():
    port = int(os.getenv("PORT", "10000"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, format, *args):
            return

    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health server virhe: {e}")

threading.Thread(target=start_health_server, daemon=True).start()


LOCKFILE = "/tmp/bot.lock"
if os.path.exists(LOCKFILE):
    # Tarkistetaan onko prosessi oikeasti käynnissä (vain Linux/Mac)
    try:
        with open(LOCKFILE, "r") as f:
            old_pid = int(f.read().strip())
        os.kill(old_pid, 0)
        logger.warning("apu: toinen instanssi jo pyörii, sammutetaan")
        sys.exit(0)
    except (OSError, ValueError):
        logger.info("apu: vanha lockfile oli jämä, poistetaan")
        os.remove(LOCKFILE)

with open(LOCKFILE, "w") as f:
    f.write(str(os.getpid()))

try:
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
finally:
    if os.path.exists(LOCKFILE):
        os.remove(LOCKFILE)