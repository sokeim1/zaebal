import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from soundcloud_downloader import SoundCloudDownloader
from config import TELEGRAM_BOT_TOKEN, MAX_FILE_SIZE_MB

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MusicBot:
    def __init__(self):
        self.downloader = SoundCloudDownloader()
        self.user_searches = {}  # Хранение результатов поиска для каждого пользователя
        self.TRACKS_PER_PAGE = 5  # Количество треков на странице
    
    def create_progress_bar(self, percentage: int, length: int = 20) -> str:
        """Создает красивый прогресс-бар"""
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {percentage}%"
    
    async def update_download_progress(self, query, track_title: str, track_uploader: str, percentage: int):
        """Обновляет прогресс скачивания"""
        progress_bar = self.create_progress_bar(percentage)
        
        if percentage < 100:
            text = f"⬇️ Скачиваю трек...\n\n🎵 {track_title}\n👤 {track_uploader}\n\n{progress_bar}\n\n⏳ Пожалуйста, подождите..."
        else:
            text = f"✅ Скачивание завершено!\n\n🎵 {track_title}\n👤 {track_uploader}\n\n{progress_bar}\n\n📤 Отправляю файл..."
        
        try:
            await query.edit_message_text(text)
        except Exception:
            pass  # Игнорируем ошибки обновления (слишком частые запросы)
    
    def create_tracks_keyboard(self, tracks: list, page: int = 0, user_id: int = None) -> InlineKeyboardMarkup:
        """Создает клавиатуру с треками и пагинацией"""
        keyboard = []
        
        # Вычисляем диапазон треков для текущей страницы
        start_idx = page * self.TRACKS_PER_PAGE
        end_idx = min(start_idx + self.TRACKS_PER_PAGE, len(tracks))
        current_tracks = tracks[start_idx:end_idx]
        
        # Добавляем кнопки с треками
        for i, track in enumerate(current_tracks):
            track_idx = start_idx + i
            duration = self.downloader.format_duration(track.get('duration', 0))
            source_icon = "🔊" if track.get('source') == 'SoundCloud' else "🎵"
            
            # Обрезаем название и исполнителя для кнопки
            title = track['title'][:30] + "..." if len(track['title']) > 30 else track['title']
            uploader = track['uploader'][:20] + "..." if len(track['uploader']) > 20 else track['uploader']
            
            # Только одна кнопка с названием трека для скачивания
            button_text = f"{source_icon} {title} - {uploader} • ⏱ {duration}"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"download_{track_idx}")])
        
        # Добавляем кнопки навигации
        nav_buttons = []
        total_pages = (len(tracks) - 1) // self.TRACKS_PER_PAGE + 1
        
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page-1}"))
        
        if total_pages > 1:
            nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="current_page"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Далее ➡️", callback_data=f"page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Кнопка отмены
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_search")])
        
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_text = """
🎵 **Добро пожаловать в Music Bot!**

Я помогу вам найти и скачать музыку с SoundCloud.

**Команды:**
• Просто отправьте название трека или исполнителя
• /help - показать справку
• /cancel - отменить текущую операцию

**Как использовать:**
1. Отправьте мне название песни или исполнителя
2. Выберите трек из результатов поиска
3. Получите файл для скачивания

⚠️ **Ограничения:**
• Максимальный размер файла: {MAX_FILE_SIZE_MB}MB
• Поддерживаются только треки с SoundCloud
• Бот предназначен для личного использования

Начните с отправки названия трека! 🎶
        """.format(MAX_FILE_SIZE_MB=MAX_FILE_SIZE_MB)
        
        try:
            await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Ошибка отправки приветствия пользователю {update.effective_user.id}: {e}")
            # Пытаемся отправить простое сообщение без markdown
            try:
                await update.message.reply_text("🎵 Добро пожаловать в Music Bot! Отправьте название трека для поиска.")
            except Exception:
                pass  # Если и это не работает, просто игнорируем
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🎵 **Справка по Music Bot**

**Основные команды:**
• `/start` - начать работу с ботом
• `/help` - показать эту справку
• `/cancel` - отменить текущую операцию

**Как искать музыку:**
• Отправьте название трека: "Imagine Dragons Believer"
• Отправьте имя исполнителя: "The Weeknd"
• Используйте комбинации: "artist - song name"

**Примеры запросов:**
• `Billie Eilish bad guy`
• `Post Malone circles`
• `Dua Lipa levitating`

**Ограничения:**
• Файлы до {MAX_FILE_SIZE_MB}MB
• Только SoundCloud треки
• До 5 результатов поиска

Удачного поиска! 🎶
        """.format(MAX_FILE_SIZE_MB=MAX_FILE_SIZE_MB)
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /cancel"""
        user_id = update.effective_user.id
        
        # Очищаем данные пользователя
        if user_id in self.user_searches:
            del self.user_searches[user_id]
        
        # Очищаем файлы пользователя
        self.downloader.cleanup_user_files(user_id)
        
        await update.message.reply_text("❌ Результаты поиска очищены. Все временные файлы удалены.")
    
    async def search_music(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик поиска музыки"""
        query = update.message.text.strip()
        user_id = update.effective_user.id
        
        if len(query) < 2:
            await update.message.reply_text("❌ Запрос слишком короткий. Введите название трека или исполнителя.")
            return
        
        # Отправляем сообщение о поиске
        search_message = await update.message.reply_text(f"🔍 Ищу: *{query}*...", parse_mode=ParseMode.MARKDOWN)
        
        try:
            # Выполняем поиск
            logger.info(f"Начинаем поиск для пользователя {user_id}: '{query}'")
            tracks = await self.downloader.search_tracks(query, limit=25)
            logger.info(f"Поиск завершен, найдено треков: {len(tracks)}")
            
            if not tracks:
                await search_message.edit_text("❌ Ничего не найдено. Попробуйте другой запрос.")
                return
            
            # Сохраняем результаты для пользователя с информацией о текущей странице
            self.user_searches[user_id] = {
                'tracks': tracks,
                'current_page': 0,
                'query': query
            }
            
            # Создаем клавиатуру с пагинацией
            reply_markup = self.create_tracks_keyboard(tracks, page=0, user_id=user_id)
            
            # Простое сообщение без лишнего текста
            results_text = f"🎵 Найдено {len(tracks)} треков по запросу: {query}"
            
            await search_message.edit_text(results_text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка поиска для пользователя {user_id}: {e}")
            await search_message.edit_text("❌ Произошла ошибка при поиске. Попробуйте позже.")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if data == "cancel_search":
            if user_id in self.user_searches:
                del self.user_searches[user_id]
            await query.edit_message_text("❌ Поиск отменен.")
            return
        
        # Обработка пагинации
        if data.startswith("page_"):
            try:
                new_page = int(data.split("_")[1])
                
                if user_id not in self.user_searches:
                    await query.edit_message_text("❌ Данные поиска не найдены. Выполните новый поиск.")
                    return
                
                # Обновляем текущую страницу
                self.user_searches[user_id]['current_page'] = new_page
                tracks = self.user_searches[user_id]['tracks']
                query_text = self.user_searches[user_id]['query']
                
                # Создаем новую клавиатуру
                reply_markup = self.create_tracks_keyboard(tracks, page=new_page, user_id=user_id)
                results_text = f"🎵 Найдено {len(tracks)} треков по запросу: {query_text}"
                
                await query.edit_message_text(results_text, reply_markup=reply_markup)
                return
                
            except Exception as e:
                logger.error(f"Ошибка пагинации: {e}")
                return
        
        # Обработка информации о треке (пустая функция)
        if data == "current_page":
            return
        
        if data.startswith("download_"):
            try:
                track_index = int(data.split("_")[1])
                
                if user_id not in self.user_searches:
                    await query.edit_message_text("❌ Данные поиска не найдены. Выполните новый поиск.")
                    return
                
                tracks = self.user_searches[user_id]['tracks']
                if track_index >= len(tracks):
                    await query.edit_message_text("❌ Неверный выбор трека.")
                    return
                
                track = tracks[track_index]
                
                # Показываем сообщение о начале скачивания
                title = track['title'].replace('*', '').replace('_', '').replace('`', '')
                uploader = track['uploader'].replace('*', '').replace('_', '').replace('`', '')
                
                # Начальный прогресс
                await self.update_download_progress(query, title, uploader, 0)
                
                # Показываем прогресс поэтапно
                for progress in [10, 25, 40, 60, 75, 90]:
                    await asyncio.sleep(0.3)  # Небольшая задержка для визуального эффекта
                    await self.update_download_progress(query, title, uploader, progress)
                
                # Скачиваем трек
                file_path = await self.downloader.download_track(track['url'], user_id)
                
                # Завершаем прогресс
                await self.update_download_progress(query, title, uploader, 100)
                
                if file_path and os.path.exists(file_path):
                    # Отправляем файл
                    with open(file_path, 'rb') as audio_file:
                        await context.bot.send_audio(
                            chat_id=query.message.chat_id,
                            audio=audio_file,
                            title=track['title'],
                            performer=track['uploader'],
                            caption=f"🎵 {track['title']}\n👤 {track['uploader']}"
                        )
                    
                    # Удаляем временный файл
                    os.remove(file_path)
                    
                    # Финальное сообщение с красивым оформлением
                    final_text = f"✅ Трек успешно отправлен!\n\n🎵 {title}\n👤 {uploader}\n\n🎉 Наслаждайтесь музыкой!"
                    await query.edit_message_text(final_text)
                else:
                    error_text = f"❌ Не удалось скачать трек\n\n🎵 {title}\n👤 {uploader}\n\n💡 Попробуйте другой трек или повторите попытку позже."
                    await query.edit_message_text(error_text)
                
                # Не очищаем результаты поиска, чтобы пользователь мог скачать еще треки
                # if user_id in self.user_searches:
                #     del self.user_searches[user_id]
                
            except Exception as e:
                logger.error(f"Ошибка скачивания для пользователя {user_id}: {e}")
                error_msg = "❌ Ошибка при скачивании."
                if "слишком большой" in str(e):
                    error_msg += f" Файл превышает лимит {MAX_FILE_SIZE_MB}MB."
                await query.edit_message_text(error_msg)
                
                # Очищаем файлы пользователя при ошибке
                self.downloader.cleanup_user_files(user_id)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка при обработке обновления {update}: {context.error}")
        
        # Если это ошибка "bot was blocked by the user", просто логируем
        if "bot was blocked by the user" in str(context.error):
            logger.info(f"Пользователь {update.effective_user.id if update.effective_user else 'Unknown'} заблокировал бота")
            return
        
        # Для других ошибок пытаемся уведомить пользователя
        if update and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
                )
            except Exception:
                pass  # Если не можем отправить сообщение, просто игнорируем
    
    def run(self):
        """Запуск бота"""
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN не установлен!")
            return
        
        # Создаем приложение
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("cancel", self.cancel_command))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_music))
        
        # Добавляем обработчик ошибок
        application.add_error_handler(self.error_handler)
        
        # Запускаем бота
        logger.info("Бот запущен!")
        
        # Для хостинга добавляем веб-сервер
        import os
        port = int(os.environ.get('PORT', 8000))
        
        # Запускаем с webhook для хостинга или polling для локальной разработки
        if os.environ.get('KOYEB_PUBLIC_DOMAIN'):
            # Webhook для Koyeb
            webhook_url = f"https://{os.environ.get('KOYEB_PUBLIC_DOMAIN')}/webhook"
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=webhook_url,
                allowed_updates=Update.ALL_TYPES
            )
        else:
            # Polling для локальной разработки
            application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = MusicBot()
    bot.run()
