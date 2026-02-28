import os
import telebot
import random
import io
import base64
import time
from collections import defaultdict
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"

client = OpenAI(api_key=OPENAI_API_KEY)

user_memory = defaultdict(list)
MAX_MEMORY = 16

user_last_message = {}
COOLDOWN_SECONDS = 2


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message,
        "apu botti\n"
        "nyt tä\n"
        "/roll 0-100\n"
        "/kuva prompt\n"
        "/reset\n"
        f"tägää {BOT_USERNAME} jos ryhmä"
    )


@bot.message_handler(commands=['reset'])
def reset_memory(message):
    user_memory[message.from_user.id] = []
    bot.reply_to(message, "muisti pois\nnyt tä")


@bot.message_handler(commands=['roll'])
def roll_command(message):
    try:
        args = message.text.split()
        max_value = 100
        if len(args) > 1:
            max_value = int(args[1])

        roll = random.randint(0, max_value)
        bot.reply_to(message, f"roll\n0-{max_value}\nsai {roll}")

    except:
        bot.reply_to(message, "numero sekas\napu ei tajuu")


@bot.message_handler(commands=['kuva'])
def generate_image(message):
    try:
        prompt = message.text.replace("/kuva", "").strip()

        if not prompt:
            bot.reply_to(message, "kirjota jotai\nälä tyhjä")
            return

        bot.send_chat_action(message.chat.id, 'upload_photo')

        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )

        image_base64 = result.data[0].b64_json
        image_bytes = io.BytesIO(base64.b64decode(image_base64))
        bot.send_photo(message.chat.id, image_bytes)

    except Exception as e:
        print(e)
        bot.reply_to(message, "kuva hajos nyt tä")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_id = message.from_user.id
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
            "OHJEET: vastaa minulle tästälähtien kuten apu apustaja (se tuttu kaveri ylilaudalta) vastaisi, käytä referenssinä vaikka ylilaudan apuapustajaketjuja, apu ei ole kovin fiksu. ymmärräthän? sisällytä tekstiin apu eli pepe the frog tyylisiä kirjoitusvirheitä"
            
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=1.4,
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

        # 60% chance lisätä extra hajontaa
        if random.random() < 0.6:
            reply_text += "\n\n" + random.choice(chaos_pool)

        # 30% chance katkoa lisää
        if random.random() < 0.3:
            reply_text = reply_text.replace(". ", ".\n")

        user_memory[user_id].append({
            "role": "assistant",
            "content": reply_text
        })

        bot.reply_to(message, reply_text)

    except Exception as e:
        print("Virhe:", e)


print(f"🐸 APU ABYSS MODE ({BOT_USERNAME}) käynnis nyt tä")
bot.infinity_polling()