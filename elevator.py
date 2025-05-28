import subprocess
import os
import logging
import platform
from time import sleep
from git import Repo

LOG_FILE: str = 'E:/bot_updater.log'

if platform.system() == "Linux":
    LOG_FILE = '/run/log/bot_updater.log'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Конфигурационные параметры
BOT_SERVICE_NAME = 'mafiabot.service'
REPO_PATH = '/opt/MafiaIncTelegramBot'  # Замените на реальный путь к репозиторию
GIT_REMOTE_URL = 'https://gitverse.ru/avkushnarenko/MafiaIncTelegramBot.git'
BRANCH = 'develop'  # Или другая ветка, которую вы используете


def stop_bot() -> bool:
    """Остановка бота через systemctl"""
    try:
        subprocess.run(['systemctl', 'stop', BOT_SERVICE_NAME], check=True, user="daemon")
        logger.info("Бот успешно остановлен")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при остановке бота: {e}")
        return False


def start_bot() -> bool:
    """Запуск бота через systemctl"""
    try:
        subprocess.run(['systemctl', 'start', BOT_SERVICE_NAME], check=True, user="daemon")
        logger.info("Бот успешно запущен")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return False


def update_code():
    """Обновление кода из git репозитория"""
    try:
        repo = Repo(REPO_PATH)

        # Получаем изменения из удаленного репозитория
        origin = repo.remotes.origin
        origin.fetch()

        # Проверяем, есть ли обновления
        local_commit = repo.head.commit
        remote_commit = repo.refs[f'origin/{BRANCH}'].commit

        if local_commit == remote_commit:
            logger.info("Локальный репозиторий уже актуален, обновление не требуется")
            return False

        # Выполняем обновление
        origin.pull()
        logger.info("Код успешно обновлен из репозитория")

        # Устанавливаем зависимости, если есть requirements.txt
        requirements_path = os.path.join(REPO_PATH, 'requirements.txt')
        if os.path.exists(requirements_path):
            subprocess.run(['pip', 'install', '-r', requirements_path], check=True)
            logger.info("Зависимости успешно обновлены")

        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении кода: {e}")
        return False


def main():
    logger.info("Запуск процесса обновления бота")

    # 1. Останавливаем бота
    if not stop_bot():
        return

    # 2. Обновляем код из репозитория
    code_updated = update_code()

    # 3. Запускаем бота снова
    if not start_bot():
        return

    if code_updated:
        logger.info("Процесс обновления завершен успешно, код обновлен")
    else:
        logger.info("Процесс обновления завершен успешно, код не требовал обновления")


if __name__ == '__main__':
    main()