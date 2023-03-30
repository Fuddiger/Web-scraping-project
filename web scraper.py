import asyncio
import aiohttp
import csv
import logging
import re
from bs4 import BeautifulSoup as BS
from datetime import datetime
from time import perf_counter

# Logs issues where information could not be correctly scraped, issues with scrape patterns and connection issues
logging.basicConfig(filename='web_scraper_logs.log', filemode='w')


def site_info() -> list[dict]:
    """
    Assign a dictionary to a variable with scraping parameters for news websites.

    'site': As one website link in string format,

    'link_patterns': as a list of strings to use as filters for a regex search to find news article links
                     using the href attribute of the 'a' tag of a soup object
    """

    global_news = dict(web_link='https://globalnews.ca/montreal/', link_patterns=["/news/"])
    washington_news = dict(web_link='https://www.washingtonpost.com/',
                           link_patterns=[r"\.com\/(?!information|tablet|live|discussions).*\/\d{4}\/\d{2}\/\d{2}"]
                           )
    fox_news = dict(web_link='https://foxnews.com', link_patterns=["-[0-9|a-z]+-[0-9|a-z]+-[0-9|a-z]+$"])
    tmz_news = dict(web_link='https://www.tmz.com/', link_patterns=[r'tmz\.com(?!=photos)\/\d{4}\/\d{2}\/\d{2}'])
    scrape_sites = [washington_news, global_news, tmz_news, fox_news]
    return scrape_sites


async def site_response(session: aiohttp.ClientSession, link: str) -> list[str, str]:
    """Return a response object from a weblink"""
    try:
        async with session.get(link) as response:
            response.raise_for_status()
            return [await response.text(), response.url]
    except aiohttp.ClientResponseError as e:
        logging.warning(f'{link} gave {e} status error')
        return False
    except aiohttp.InvalidURL:
        logging.warning(f'{link} is invalid')
        return False
    except aiohttp.ClientConnectionError as e:
        logging.warning(f'{link} gave {e}')
        return False


def collect_hrefs(soup: BS, link_patterns: dict[str]) -> list[str]:
    """Return a list of article links to be scraped, using RE patterns and a BS4 object"""
    article_links = [tag['href'] if re.search(r"^https:", tag['href']) else "https:" + tag['href']
                     for link_pattern in link_patterns
                     for tag in soup.find_all('a', href=re.compile(link_pattern))]
    return article_links


async def queue_maker(article_links: set[str], queue: asyncio.Queue) -> None:
    """Take a set of article links and add to an asynchronous queue"""
    for link in article_links:
        queue.put_nowait(link)


async def process_queue(session: aiohttp.ClientSession, queue: asyncio.Queue) -> list[list[str, str]]:
    """Return a list of response objects from article links in the queue"""
    response_list = []
    while True:
        if queue.empty():
            return response_list
        link = await queue.get()
        response = await site_response(session, link)
        if response:
            response_list.append(response)
        queue.task_done()


def make_soup(response: str) -> BS:
    """Return a BeautifulSoup object using a response.text"""
    soup = BS(response, 'lxml')
    return soup


def scrape_title(soup: BS) -> str:
    """Return the title of news article"""
    title = soup.title.get_text(strip=True)
    return title


def str_to_date(date: str, strp_patterns: list[str]) -> datetime:
    """Attempt to make a datetime object from a date string and return it"""
    for strp_pattern in strp_patterns:
        try:
            datetime.strptime(date, strp_pattern)
            return datetime.strptime(date, strp_pattern)
        except ValueError:
            continue
    return False


def scrape_date(soup: BS, date_patterns: list[dict[str]], strp_patterns: list[str]) -> tuple[str, datetime]:
    """Attempt to find and return a publishing date and date object of that date using RE search patterns"""
    for d_p in date_patterns:
        if not d_p['search'] and not d_p['contents']:
            if soup.find(d_p['tag']):
                article_date = soup.find(d_p['tag']).get_text(separator=' ', strip=True)
                date_object = str_to_date(article_date, strp_patterns)
            else:
                date_object = False
        elif d_p['search']:
            if soup.find(d_p['tag'], string=re.compile(d_p['search'])):
                article_date = soup.find(d_p['tag'], string=re.compile(d_p['search'])).get_text(separator=' ',
                                                                                                strip=True)
                date_object = str_to_date(article_date, strp_patterns)
            else:
                date_object = False
        else:
            try:
                if soup.find(d_p['tag']).contents[d_p['contents']]:
                    article_date = soup.find(d_p['tag']).contents[d_p['contents']].get_text(separator=' ', strip=True)
                    date_object = str_to_date(article_date, strp_patterns)
                else:
                    date_object = False
            except AttributeError:
                date_object = False
            except IndexError:
                logging.warning(f'{soup.title.get_text()} used a soup.contents index that was out of range')
                date_object = False
        if date_object:
            return article_date, date_object
        else:
            continue
    return False, False


def scrape_text(soup: BS) -> str:
    """Return the text of an article link"""
    text = ''
    for item in soup.find_all('p'):
        text += item.get_text(separator=' ', strip=True)
    return text


def write_data(link: str, title: str, date: str, strp_date: datetime, text: str) -> None:
    """Write scraped data to a csv file"""
    if not date:
        logging.warning(f'Date pattern or strp_pattern was not successful for {link}')
        date = 'No date found'
        strp_date = 'No date to make date object'
    else:
        pass
    with open('Scraped_News.csv', 'a', newline='', encoding='utf-8') as a:
        writer = csv.writer(a)
        writer.writerow([link, title, date, strp_date, text])


async def main():
    """Date patterns and datetime object patterns for scraping article links.
    'tag' is mandatory, the tag to search for date info.
    Use search or contents, leave the other as False:
    'search' will be used in string=re.compile() of BeautifulSoup
     'contents' is an integer for a list index of string items in a tag
     'strp_patterns' must be a string used in strptime to make a date object"""
    date_patterns = [dict(tag='span', search='Posted', contents=False),
                     dict(tag='div', search='Updated', contents=False),
                     dict(tag='span', search='EST', contents=False),
                     dict(tag='span', search='EDT', contents=False),
                     dict(tag='time', search=False, contents=False),
                     dict(tag='h5', search=False, contents=-1)]
    strp_patterns = ['Posted %B %d, %Y %I:%M %p', 'Published %B %d, %Y', 'Updated %B %d, %Y %I:%M %p',
                     '%B %d, %Y at %I:%M p.m. EST', '%B %d, %Y at %I:%M a.m. EST', '%B %d, %Y at %I:%M p.m. EDT',
                     '%B %d, %Y at %I:%M a.m. EDT', '%B %d, %Y %I:%M%p EST', '%B %d, %Y %I:%M%p EDT',
                     '%m/%d/%Y %I:%M %p PT'
                     ]
    article_links = set()
    queue = asyncio.Queue()
    async with aiohttp.ClientSession() as session:
        for site in site_info():
            response, url = await site_response(session, site['web_link'])
            soup = make_soup(response)
            href_list = collect_hrefs(soup, site['link_patterns'])
            print(f"{len(href_list)} links were collected from {url}")
            article_links.update(href_list)
        link_queue = asyncio.create_task(queue_maker(article_links, queue))
        # Change the max range to scrape faster or slower
        tasks = [process_queue(session, queue) for _ in range(20)]
        await queue.join()
        print('Article links have been added to the queue.')
        print('Beginning scraping, please wait...')
        response_list = await asyncio.gather(*tasks)
        link_queue.cancel()
    scraped_time = perf_counter()
    print(f'Scraping took {scraped_time - start_time} seconds')
    print('Scraping complete, writing to file')
    for link_responses in response_list:
        for response in link_responses:
            article_soup = make_soup(response[0])
            link = response[1]
            title = scrape_title(article_soup)
            date, strp_date = scrape_date(article_soup, date_patterns, strp_patterns)
            text = scrape_text(article_soup)
            write_data(link, title, date, strp_date, text)


if __name__ == '__main__':
    start_time = perf_counter()
    # To avoid a cancel error that seems to arise with this version of Pycharm on a Windows system
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
    complete_time = perf_counter()
    print(f'Links were collected in {complete_time - start_time} seconds.')
