import logging
import time
import os
import requests
from http import HTTPStatus
import telegram
import datetime
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN')
TELEGRAM_TOKEN = os.getenv('BOTTOKEN')
TELEGRAM_CHAT_ID = os.getenv('ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

PRACTICUM_BIRTHDAY = int(datetime.datetime(2019, 2, 12, 9, 0).timestamp())
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(current_timestamp):
    """Запрос информации от сервера."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params
                                         )
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'Ошибка {status_code}')
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        logger.error('Ошибка парсинга ответа из формата json')
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
    """Проверяем запрос."""
    homeworks = response['homeworks']
    if not isinstance(response, dict):
        raise TypeError('Not dict')
    elif isinstance(homeworks, list):
        return(homeworks)
    raise Exception('Not list')


def parse_status(homework):
    """Анализируем статус если изменился."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    raise Exception('wrong status')


def check_tokens():
    """Проверка наличия токенов."""
    return all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN])


def main():
    """Основная логика работы бота."""
    homework_status = 'Unknown'
    last_error = None
    if check_tokens() is False:
        return
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except telegram.error.TelegramError as error:
        logger.critical(f'Произошла ошибка при создании бота: {error} '
                        'программа остановлена')
        return
    while True:
        try:
            response = get_api_answer(PRACTICUM_BIRTHDAY)
            homeworks = check_response(response)
            if homeworks:
                last_homework = homeworks[0]
                status = parse_status(last_homework)
                if homework_status != status:
                    homework_status = status
                    send_message(bot, status)
                else:
                    logger.info('Статус проверки задания'
                                ' не обновился')
            else:
                raise Exception('С указанного момента времени'
                                ' не было сданных домашних заданий')
        except Exception as error:
            if error != last_error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
                send_message(bot, message)
                last_error = error
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='program.log',
        filemode='w',
        format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
    )
    main()
