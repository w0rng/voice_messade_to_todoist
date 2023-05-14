import logging
import os
import subprocess

import requests
import sentry_sdk
import speech_recognition as sr
import telebot
from sentry_sdk.integrations.logging import LoggingIntegration


bot = telebot.TeleBot(os.environ["TELEGRAM_API"])
TODOIST_TOKEN = os.environ["TODOIST_TOKEN"]
SENTRY_DSN = os.environ["SENTRY_DSN"]
ALLOWED_USERS = os.environ["ALLOWED_USERS"].split(",")


class NotRecognized(Exception):
    pass


@bot.message_handler(content_types=["voice"])
def voice_handler(message):
    extra = {"user": message.from_user.username}
    if message.from_user.username not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "Ти хто?")
        logging.warning(f"User {message.from_user.username} tried to use bot", extra=extra)
        return

    file_id = message.voice.file_id
    file = bot.get_file(file_id)
    extra.update({"file_id": file_id, "file_size": file.file_size})

    logging.info(f"File size: {file.file_size} from {message.from_user.username}", extra=extra)

    if int(file.file_size) >= 715000:
        logging.warning(f"File size is too large: {file.file_size}", extra=extra)
        bot.send_message(message.chat.id, "Upload file size is too large.")
        return

    download_file = bot.download_file(file.file_path)
    with open("audio.ogg", "wb") as file:
        file.write(download_file)

    try:
        text = voice_recognizer(extra)
        add_todoist_task(text, extra)
        bot.send_message(message.chat.id, f'Задача "{text}" добавлена')
    except NotRecognized:
        bot.send_message(message.chat.id, "Ниче не понял")
    finally:
        os.remove("audio.wav")
        os.remove("audio.ogg")


def voice_recognizer(log_extra):
    subprocess.run(["ffmpeg", "-i", "audio.ogg", "audio.wav", "-y"], capture_output=True, text=True)
    file = sr.AudioFile("audio.wav")
    r = sr.Recognizer()
    with file as source:
        try:
            audio = r.record(source)  # listen to file
            return r.recognize_google(audio, language="ru_RU")
        except Exception as error:
            logging.error(error, extra=log_extra)
            raise NotRecognized


def add_todoist_task(text: str, log_extra):
    response = requests.post(
        url="https://api.todoist.com/rest/v2/tasks",
        json={"content": text},
        headers={"Authorization": "Bearer " + TODOIST_TOKEN},
    )
    if response.status_code != 200:
        logging.error(response.text, extra=log_extra)
        return
    logging.info("Task added", extra=log_extra)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Bot started")
    sentry_sdk.init(
        SENTRY_DSN,
        integrations=[
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.WARNING,
            ),
        ],
    )
    bot.polling(True)
