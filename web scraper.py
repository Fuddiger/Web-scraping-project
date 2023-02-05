import csv
import re
import requests
from bs4 import BeautifulSoup as bs
from datetime import datetime
from time import perf_counter


# Returns Bs4 object for a website or one of it's news article links
def make_soup(link):
    response = requests.get(link)
    soup = bs(response.text, 'lxml')
    return soup


# return all href links as a set, using soup object and the specified re.compile pattern in site_params. Some links
# from Fox News did not include 'https:', searches for and repairs those as well
def collect_hrefs(site_soup, link_patterns):
    links = [tag['href'] if re.search(r"^https:", tag['href']) else "https:" + tag['href']
             for link_pattern in link_patterns
             for tag in site_soup.find_all('a', href=re.compile(link_pattern))]
    if not links:
        print(f'No links matching the pattern were found for {site_soup.title}')
    else:
        return set(links)


# Returns the title of a news article as a string
def scrape_title(soup):
    title = soup.title.get_text(strip=True)
    return title


# Returns publishing date using soup and date search parameters, from site_params
def scrape_date(soup, date_patterns):
    for d_p in date_patterns:
        if d_p['search']:
            if soup.find(d_p['tag'], string=re.compile(d_p['search'])):
                return soup.find(d_p['tag'], string=re.compile(d_p['search'])).get_text(separator=' ', strip=True)
        elif d_p['contents']:
            if soup.find(d_p['tag']).contents[d_p['contents']]:
                return soup.find(d_p['tag']).contents[d_p['contents']].get_text(separator=' ', strip=True)
        else:
            if soup.find(d_p['tag']):
                return soup.find(d_p['tag']).get_text(separator=' ', strip=True)
    return 'Date was not matched successfully'


# Returns publishing date as a strptime object using the date and the patterns specified in site_params
def str_to_date(date, strp_patterns):
    for strp_pattern in strp_patterns:
        try:
            datetime.strptime(date, strp_pattern)
            return datetime.strptime(date, strp_pattern)
        except ValueError:
            pass
    return 'Strptime patterns did not match date values'


# Returns the stripped text of a news article delimited with spaces
def scrape_text(soup):
    text = ''
    for item in soup.find_all('p'):
        text += item.get_text(separator=' ', strip=True)
    return text


# Creates\Appends the data to a CSV file that will be created in the same folder as the program
def data_write(site, title, date, text):
    with open('Scraped_News.csv', 'a', newline='', encoding='utf-8') as a:
        writer = csv.writer(a)
        writer.writerow([site, title, date, text])


# Search parameters for each site to scrape, takes a variable containing a dictionary, all keys are necessary,
# date_patterns accepts values of False for 'search' and 'contents', if they are not needed
def site_parameters():
    """
    Assign a dictionary to a variable with scraping parameters for news websites.

     'site': as one website link in string format,

    'link_patterns': as a list of strings to plug into re.compile to return news article links from the href attribute of the
    'a' tag

    'date_patterns': as a list of dictionaries with four mandatory parameters to help find a publishing date,
    'tag': A Bs4 tag to search in, 'search': a string to use in string=re.compile('search'), can be left as False,
    'contents': an integer to use for an index of Bs4 tag.contents[], can be left as False

    'strp_patterns': as a list of strings to use in transforming a date into a strptime object. Must copy the exact
    format of what is found with the date search.
    """

    global_news = {'site': 'https://globalnews.ca/montreal/',
                   'link_patterns': ["/news/"],
                   'date_patterns': [{'tag': 'span', 'search': 'Posted', 'contents': False},
                                     {'tag': 'div', 'search': 'Updated', 'contents': False}],
                   'strp_patterns': ['Posted %B %d, %Y %I:%M %p', 'Published %B %d, %Y']
                   }
    washington_news = {'site': 'https://www.washingtonpost.com/',
                       'link_patterns': ["\.com\/(?!information|tablet|live|discussions).*\/\d{4}\/\d{2}\/\d{2}"],
                       'date_patterns': [{'tag': 'span', 'search': 'EST', 'contents': False}],
                       'strp_patterns': ['%B %d, %Y at %I:%M p.m. EST', '%B %d, %Y at %I:%M a.m. EST']
                       }
    fox_news = {'site': 'https://foxnews.com',
                'link_patterns': ["-[0-9|a-z]+-[0-9|a-z]+-[0-9|a-z]+$"],
                'date_patterns': [{'tag': 'time', 'search': False, 'contents': False}],
                'strp_patterns': ['%B %d, %Y %I:%M%p EST']
                }
    tmz_news = {'site': 'https://www.tmz.com/',
                'link_patterns': ['\.com(?!=photos)\/\d{4}\/\d{2}\/\d{2}'],
                'date_patterns': [{'tag': 'h5', 'search': False, 'contents': -1}],
                'strp_patterns': ['%m/%d/%Y %I:%M %p PT']
                }
    # The sites to include for scraping
    site_parameters = [tmz_news, fox_news]
    return site_parameters


if __name__ == '__main__':
    link_counter = 0
    tik = perf_counter()
    site_params = site_parameters()
    for site_param in site_params:
        site_soup = make_soup(site_param['site'])
        href_links = collect_hrefs(site_soup, site_param['link_patterns'])
        link_counter += len(href_links)
        for link in href_links:
            article_soup = make_soup(link)
            title = scrape_title(article_soup)
            date = scrape_date(article_soup, site_param['date_patterns'])
            strp_date = str_to_date(date, site_param['strp_patterns'])
            text = scrape_text(article_soup)
            data_write(link, title, strp_date, text)
    tok = perf_counter()
    print(f'{link_counter} links were collected in {tok - tik} seconds.')
