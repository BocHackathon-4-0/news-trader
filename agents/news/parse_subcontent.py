from langchain.document_loaders.web_base import WebBaseLoader
import requests
from gpt_by_ya import get_answer_from_gpt_model
import summary_templates as templates


def parse_more_data(news_item):
    def get_full_content_summary(item):
        news_id = item.get('id')
        data = requests.get(f'https://cryptopanic.com/news/click/{news_id}/')
        source_content = data.url
        raw_content = get_content(source_content)
        sfc = get_answer_from_gpt_model(
            system_text=templates.system_short_summary_template,
            user_text=str(raw_content[0].page_content.replace('\n', ' ')),
            max_tokens=templates.long_tokens,
            temp=templates.long_temp,
            retry=True
        )
        return sfc

    def get_short_content_summary(item):
        # news_id = item.get('id')
        # data = requests.get(f'https://cryptopanic.com/news/click/{news_id}/')
        # source_content = data.url
        # raw_content = get_content(source_content)

        short_content = get_content(item.get('url'))

        summary_short_content = get_answer_from_gpt_model(
            system_text=templates.system_short_summary_template,
            user_text=str(short_content[0].page_content),
            max_tokens=templates.short_tokens,
            retry=True
        )
        return summary_short_content

    def get_content(url: str):
        loader = WebBaseLoader([url], bs_kwargs={"features": "lxml"})
        docs = loader.load()
        return docs

    print('summary... 🤖')
    short_sum = get_short_content_summary(news_item)
    full_sum = get_full_content_summary(news_item)
    return {'summary_short': short_sum, 'summary_long': full_sum}
