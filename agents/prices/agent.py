import os
from datetime import datetime, timedelta

import ccxt
import dotenv
from supabase import create_client, Client

dotenv.load_dotenv('../.env')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# supabase
surl: str = SUPABASE_URL
skey: str = SUPABASE_KEY

from tqdm import tqdm


results = []

from time import sleep
TIMEOUT = 60

def retry_fetch_ohlcv(exchange, max_retries, symbol, timeframe, since, limit):
    num_retries = 0
    try:
        num_retries += 1
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
        print('Fetched', len(ohlcv), symbol, 'candles from', exchange.iso8601(ohlcv[0][0]), 'to',
              exchange.iso8601(ohlcv[-1][0]))
        return ohlcv
    except Exception:
        if num_retries > max_retries:
            raise Exception('Failed to fetch', timeframe, symbol, 'OHLCV in', max_retries, 'attempts')


def scrape_ohlcv(exchange, max_retries, symbol, timeframe, since, limit):
    earliest_timestamp = exchange.milliseconds()
    timeframe_duration_in_seconds = exchange.parse_timeframe(timeframe)
    timeframe_duration_in_ms = timeframe_duration_in_seconds * 1000
    timedelta = limit * timeframe_duration_in_ms
    all_ohlcv = []
    while True:
        fetch_since = earliest_timestamp - timedelta
        ohlcv = retry_fetch_ohlcv(exchange, max_retries, symbol, timeframe, fetch_since, limit)
        # if we have reached the beginning of history
        if ohlcv is None:
            continue
        if ohlcv[0][0] >= earliest_timestamp:
            break
        earliest_timestamp = ohlcv[0][0]
        all_ohlcv = ohlcv + all_ohlcv
        print(len(all_ohlcv), symbol, 'candles in total from', exchange.iso8601(all_ohlcv[0][0]), 'to',
              exchange.iso8601(all_ohlcv[-1][0]))
        # if we have reached the checkpoint
        if fetch_since < since:
            break
    return all_ohlcv


def upload_to_supabase(prices: list, platform: str, token: str, timeframe: str):
    # upload to supabase
    supabase: Client = create_client(surl, skey)
    supabase.auth.sign_in_with_password(
        {"email": os.getenv('SUPABASE_ACCOUNT'), "password": os.getenv('SUPABASE_PASSWORD')})
    
    for result in tqdm(prices):
        candle_id = result[0]
        try:
            response = (supabase.table('prices')
                        .select("*")
                        .match({'timeframe': timeframe, 'token': token, 'id': candle_id, 'platform': platform})
                        .execute())
        except Exception as E:
            print(E)
            continue

        # if not exist insert
        if len(response.data) == 0:
            try:
                data = (
                    supabase.table('prices').insert(
                        {
                            'id': candle_id,
                            'token': token,
                            'platform': platform,
                            'timeframe': timeframe,
                            'prices': result
                        }
                    ).execute())
                assert len(data.data) > 0
            except Exception as E:
                print(E)
    supabase.auth.sign_out()

def scrape_candles_to_csv(filename, exchange_id, max_retries, symbol, timeframe, since, limit, **kwargs):
    # instantiate the exchange by id
    exchange = getattr(ccxt, exchange_id)({
        'enableRateLimit': True,  # required by the Manual
    })
    # convert since from string to milliseconds integer if needed
    if isinstance(since, str):
        since = exchange.parse8601(since)
    # preload all markets from the exchange
    exchange.load_markets()
    # fetch all candles
    ohlcv = scrape_ohlcv(exchange, max_retries, symbol, timeframe, since, limit)
    # save them to csv file
    # write_to_csv(filename, exchange, ohlcv)

    supabase: Client = create_client(surl, skey)
    supabase.auth.sign_in_with_password(
        {"email": os.getenv('SUPABASE_ACCOUNT'), "password": os.getenv('SUPABASE_PASSWORD')})

    upload_to_supabase(prices=ohlcv, platform=exchange_id, token=symbol, timeframe=timeframe)
    print('Saved', len(ohlcv), 'candles from', exchange.iso8601(ohlcv[0][0]), 'to', exchange.iso8601(ohlcv[-1][0]),
          'to', filename)
    
    supabase.auth.sign_out()

    return filename


def get_date_one_month_ago():
    # Получаем текущую дату
    today = datetime.now()

    # Вычисляем дату на месяц назад
    one_month_ago = today - timedelta(days=1)

    # Форматируем дату в нужный формат
    formatted_date = one_month_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

    return formatted_date


def all_used_bases():
    supabase: Client = create_client(surl, skey)
    supabase.auth.sign_in_with_password(
        {"email": os.getenv('SUPABASE_ACCOUNT'), "password": os.getenv('SUPABASE_PASSWORD')})

    response = supabase.table('news') \
        .select('id, source, obj->currencies') \
        .execute()
    supabase.auth.sign_out()

    currencies = [item.get('currencies') for item in response.data if item.get('currencies') is not None]
    uniq_codes = []
    for code in currencies:
        for item in code:
            if item.get('code') not in uniq_codes:
                uniq_codes.append(item.get('code'))
    return uniq_codes


from apscheduler.schedulers.background import BackgroundScheduler


if __name__ == '__main__':

    date_one_month_ago = get_date_one_month_ago()
    print(date_one_month_ago)
    used_markets = all_used_bases()
    print(len(used_markets))

    # Initialize the exchange object (e.g., Binance)
    exchange = ccxt.binance()
    markets = exchange.fetch_markets()

    # Filter markets where the base currency matches
    v = []
    for used_market in used_markets:
        v.append([market for market in markets if market['base'] == used_market])

    index_n = 1


    ignoring = ['ETH/TUSD', 'ETH/PAX', 'BTC/USDT', 'ETH/BTC', 'ETH/USDT', 'ETH/USDC', 'ETH/BUSD', 'PAX']
    for i in tqdm(v):
        for j in tqdm(i):
            print(index_n)            

            exchange = 'binance'
            ticker = j.get('symbol')
            pair = ticker.split('/')
            for ignored in ignoring:
                if ignored in pair:
                    print(ignored, 'continue...')
                    continue

            if ticker in ignoring:
                print(ticker, 'continue...')
                continue


            print(ticker)
            timeframe = '15m'
            try:
                file = scrape_candles_to_csv(
                    filename=f'{date_one_month_ago.replace(":", "").replace("/", "")}_{timeframe}_{ticker.replace("/", "")}.csv',
                    exchange_id=exchange,
                    max_retries=10,
                    symbol=ticker,
                    timeframe=timeframe,
                    since=date_one_month_ago,
                    limit=1000
                )
            except Exception as E:
                print(E)
            print(file, index_n)
            index_n += 1
            sleep(60)



# from apscheduler.schedulers.background import BackgroundScheduler

# # Define a function that you want to schedule
# def my_job():
#     print("Scheduled job executed!")

# # Create a scheduler instance
# scheduler = BackgroundScheduler()

# # Add your job to the scheduler with a specified interval (e.g., every 10 seconds)
# scheduler.add_job(my_job, 'interval', seconds=10)

# # Start the scheduler
# scheduler.start()

# try:
#     # Keep your main thread running to allow the scheduler to continue working
#     while True:
#         pass
# except (KeyboardInterrupt, SystemExit):
#     # Gracefully shut down the scheduler when you interrupt the program
#     scheduler.shutdown()
