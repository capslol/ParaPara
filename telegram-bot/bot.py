import os
import urllib.parse
import asyncio

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, LoginUrl
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import aiohttp
from telegram.error import BadRequest


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CALLBACK_URL_ENV = os.environ.get("AUTH_CALLBACK_URL", "http://localhost:3001/api/auth/telegram/callback")
FRONTEND_PUBLIC_URL = os.environ.get("FRONTEND_PUBLIC_URL", "http://localhost:5173")


async def resolve_callback_base() -> str:
    # Возвращаем базовый callback URL
    # Режим auto:ngrok — берем публичный https URL из сервиса ngrok по адресу http://ngrok:4040/api/tunnels
    if CALLBACK_URL_ENV.lower().startswith("auto:ngrok"):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://ngrok:4040/api/tunnels") as resp:
                    data = await resp.json()
            tunnels = data.get("tunnels", [])
            https_tunnels = [t for t in tunnels if t.get("public_url", "").startswith("https://")]
            if not https_tunnels:
                raise RuntimeError("No https ngrok tunnel found")
            public_url = https_tunnels[0]["public_url"].rstrip("/")
            return f"{public_url}/api/auth/telegram/callback"
        except Exception as e:
            raise RuntimeError(f"Ngrok is not ready: {e}")
    # По умолчанию — берем как есть из ENV
    return CALLBACK_URL_ENV


async def build_login_url(state: str | None = None) -> str:
    base = await resolve_callback_base()
    query = {}
    if state:
        query["state"] = state
    if query:
        return base + ("?" + urllib.parse.urlencode(query))
    return base


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    start_param = args[0] if args else None

    # Если callback URL не https — показываем подсказку и не пытаемся отправлять LoginUrl
    callback_base = await resolve_callback_base()
    if not callback_base.lower().startswith("https://"):
        warn = (
            "Авторизация через Telegram требует HTTPS колбэка.\n"
            f"Сейчас AUTH_CALLBACK_URL = {callback_base}\n"
            "Укажите публичный https-URL (ngrok/домен) и перезапустите бота."
        )
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_message(chat_id=chat_id, text=warn)
        return

    # Поддержка схемы с state: ожидаем start вида auth_<state>
    state = None
    if start_param and start_param.startswith("auth_"):
        state = start_param.split("auth_", 1)[1] or None

    if state:
        # Собираем данные пользователя и отправляем их на бэкенд
        user = update.effective_user
        profile = {
            "id": user.id if user else None,
            "username": user.username if user else None,
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
            "photo_url": None,  # Пока None, получим фото отдельно
            "state": state,
        }
        
        # Получаем фото пользователя
        try:
            photos = await context.bot.get_user_profile_photos(user.id, limit=1)
            if photos.photos:
                # Берем самое большое фото
                photo = photos.photos[0][-1]  # Последний элемент - самое большое фото
                file = await context.bot.get_file(photo.file_id)
                profile["photo_url"] = file.file_path
        except Exception as e:
            print(f"Error getting user photo: {e}")
            # Если не удалось получить фото, оставляем None
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    callback_base.replace("/api/auth/telegram/callback", "/api/auth/telegram/callback/bot"),
                    json=profile,
                    headers={"X-Bot-Token": BOT_TOKEN},
                    timeout=aiohttp.ClientTimeout(total=10),
                )
        except Exception:
            pass

        # Показываем сообщение об успешной авторизации
        text = (
            "✅ **Авторизация завершена!**\n\n"
            "Теперь вы можете вернуться на сайт и увидеть свой профиль.\n\n"
            "Если вы не запрашивали авторизацию, немедленно выйдите из аккаунта на сайте!"
        )
        markup = None
        if update.message:
            await update.message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=markup, disable_web_page_preview=True)
        return

    # Старый поток через LoginUrl
    login_url = LoginUrl(url=await build_login_url(start_param), request_write_access=False)
    keyboard = [[InlineKeyboardButton(text="Авторизоваться на сайте", login_url=login_url)]]
    markup = InlineKeyboardMarkup(keyboard)

    text = (
        "Нажмите кнопку ниже, чтобы авторизоваться на сайте через Telegram.\n"
        f"После авторизации вы будете перенаправлены на: {FRONTEND_PUBLIC_URL}"
    )
    try:
        if update.message:
            await update.message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=markup, disable_web_page_preview=True)
    except BadRequest as e:
        # Если домен не подтверждён у бота — показываем инструкцию
        callback_base = await resolve_callback_base()
        if "Bot_domain_invalid" in str(e):
            hint = (
                "У бота не задан домен для LoginUrl.\n"
                "Откройте @BotFather → /setdomain → выберите бота → введите домен:\n"
                f"{callback_base.split('/')[2]}\n"
                "Требуется точный https-домен (без пути)."
            )
            chat_id = update.effective_chat.id if update.effective_chat else None
            if chat_id:
                await context.bot.send_message(chat_id=chat_id, text=hint)
        else:
            # Пробрасываем дальше и пускай упадёт в логи, если причина иная
            raise





async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Показываем кнопку авторизации на любое текстовое сообщение
    await start(update, context)


def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN.strip().lower() == "changeme":
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set or uses default 'changeme'")

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("login", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), fallback))

    # Простая модель: polling
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()


