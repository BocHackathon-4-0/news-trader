import asyncio
import httpx
import dotenv
import os
import multiprocessing
from supabase import create_client, Client

dotenv.load_dotenv('../../.env')
CRYPTO_PANIC_API = os.getenv('CRYPTO_PANIC_API')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# supabase
surl: str = SUPABASE_URL
skey: str = SUPABASE_KEY

supabase: Client = create_client(surl, skey)
supabase.auth.sign_in_with_password(
    {"email": os.getenv('SUPABASE_ACCOUNT'), "password": os.getenv('SUPABASE_PASSWORD')})

results = []

from parse_subcontent import parse_more_data


# Define worker_function here, outside any functions
def supabase_worker(arg):
    for result in arg:
        if 'id' not in result:
            continue
        response = supabase.table('news').select("*").eq('id', result.get('id')).execute()

        result['summary'] = parse_more_data(result)

        # if not exist insert
        if len(response.data) == 0:
            try:
                data = supabase.table('news').insert({'id': result.get('id'), 'obj': result, 'source': 'cp'}).execute()
                assert len(data.data) > 0
            except Exception as E:
                print(E)

        elif len(response.data) > 0:
            try:
                data = supabase.table('news').update({'obj': result}).eq('id', result.get('id')).execute()
                assert len(data.data) > 0
            except Exception as E:
                print(E)

    return 'Ok'


async def fetch_data(url, headers, payload):
    async with httpx.AsyncClient() as client:
        # Send asynchronous GET request
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            # Successful request
            data = response.json()

            if 'next' in data and data.get('next') is not None:
                results.append(data['results'])
                await fetch_data(data['next'], headers, payload)

        else:
            # Error handling
            print(f"Request failed with status code {response.status_code}")
            # print(response.text)


async def upload_news(news: list):
    for new in news:
        supabase_worker(new)

    # Create a multiprocessing Pool with the desired number of processes
    # num_processes = 1 # multiprocessing.cpu_count()  # Use the number of CPU cores
    # pool = multiprocessing.Pool(processes=num_processes)
    #
    # # Map the list of arguments to the worker function
    # news = pool.map(supabase_worker, news)
    # pool.close()
    # pool.join()

    # Print the results
    # print(news)


async def main():
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTO_PANIC_API}&filter=rising&public=true"
    headers = {
        "Content-Type": "application/json"
    }

    await fetch_data(url, headers, payload=None)
    await upload_news(results)
    supabase.auth.sign_out()


if __name__ == "__main__":
    asyncio.run(main())

