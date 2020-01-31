#!/usr/bin/env python3
from ebaysdk.finding import Connection
from random import randint
import pandas as pd
import urllib.request
import urllib.parse
import datetime
import numpy as np

DATE_FILLED = 'date_last_filled'


class QueryError(Exception):
    pass


class Item:
    name = ""
    price = 0
    image_url = ""
    shop_url = ""
    item_id = 0

    def __init__(self, name, price, image_url, shop_url, item_id):
        self.name = name
        self.price = price
        self.image_url = image_url
        self.shop_url = shop_url
        self.item_id = item_id

    def __str__(self):
        return "Name: " + self.name + "\nPrice: " + str(self.price) + \
               "\nImage Url: " + self.image_url + "\nItem link: " + self.shop_url + "\nID: " + str(self.item_id)


pandas_obj = None  # The items db
settings = {}  # A settings dictionary holding different settings


def create_request(word, num_results, price, deviation):
    """
    A function that creates a request dict according to the api
    :param string word: the keywords to be used
    :param int num_results: the number of results to be returned
    :param int price: the price of the item
    :param int deviation: the percentage of deviation allowed

    :return:
    A request dict according to the api
    """
    return {
        'keywords': word,
        'itemFilter': [
            {'name': 'HideDuplicateItems', 'value': 'true'},
            {'name': 'MinQuantity', 'value': 1},  # To ensure the item is still buyable

            {'name': 'MinPrice', 'value': float(price - (price * float(deviation) / 100))},
            {'name': 'MaxPrice', 'value': float(price + (price * float(deviation) / 100))}

        ],
        'paginationInput': {
            'entriesPerPage': num_results,
            'pageNumber': 1
        },
    }


def make_keywords():
    """
    A function to create a random keyword for the search (ebay insists you search with a keyword, for some reason :)

    :return:
    A string consisting of two pseudo-generated letters.
    """

    a = randint(1, 26)
    b = randint(1, 26)

    a = chr(96 + a)
    b = chr(96 + b)

    return a + b


def pasre_query(question):
    """
    A function to transform the query string into python objects
    :param string question: the query entered by the user

    :return:
    Either None if the query was invalid or a tuple (price[int], keywords[string])
    """
    question = question.split('-')  # The parts of the query are to be separated by a '-'
    price, keyword = 0, ''
    if len(question) == 1:  # If it is only a price guided query
        price = int(question[0])
        keyword = None
    elif len(question) == 2:  # If its also a keyword guided query
        price = int(question[0])
        keyword = question[1]
    else:
        raise QueryError("Invalid query found while processing - " + str(question))

    return price, keyword


def db_search(price):
    """
    A function to find an item by price from the local DB

    :param int price: The price of the item to be found
    :return:

    None if the item wasn't found or an Item object representing the item.
    """
    global pandas_obj

    good_rows = pandas_obj[
        (float(price - (price * 0.1)) < pandas_obj['price']) & (float(price + (price * 0.1))
            > pandas_obj['price'])]
    # Search the DB for item that its price is in the -+10% of the intended price

    found = False
    item_row = 0
    while not found and len(good_rows) > 0:
        item_row = randint(0, len(good_rows) - 1)  # For us to take a random item that answers our demands
        if datetime.datetime.strptime(good_rows['end_time'].iat[item_row],
                                      "%Y-%m-%d %H:%M:%S") < datetime.datetime.now():  # There's a possibilty that the item's listing is no longer avilable
            pandas_obj = pandas_obj.append(good_rows.iloc[item_row]).drop_duplicates(
                keep=False)  # If the item is out of date
            good_rows = good_rows.append(good_rows.iloc[item_row]).drop_duplicates(
                keep=False)  # it shall be removed from the DB
        else:
            found = True

    if not found:
        return None
    else:
        item_name = good_rows['name'].iat[item_row]
        item_price = good_rows['price'].iat[item_row]
        item_id = good_rows['item_id'].iat[item_row]
        shop_url = good_rows['shop_url'].iat[item_row]
        item_image_url = good_rows['image_url'].iat[item_row]
        return Item(item_name, item_price, item_image_url, shop_url, item_id)


def db_add(item):
    """
    This function adds a new item to the database and creates an Item object from it
    It also gets the url of the image from the ebay listing
    :param item: The item to be added into the database
    :return:

    An Item object that represents the item the was added
    """
    global pandas_obj
    item_name = item.title.replace(',', ' ')
    item_price = item.sellingStatus.currentPrice.value
    item_id = item.itemId
    shop_url = item.viewItemURL
    end_time = item.listingInfo.endTime

    item_page = urllib.request.urlopen(shop_url)
    item_page = str(item_page.read())
    item_page = item_page[item_page.find("<img id=\"icImg\""):]
    item_page = item_page[item_page.find("src=\"") + 5:]
    item_image_url = item_page[:item_page.find('"')]

    new_item = pd.DataFrame({
        'name': [item_name],
        'price': [float(item_price)],
        'image_url': [item_image_url],
        'shop_url': [shop_url],
        'item_id': [item_id],
        'end_time': [end_time.strftime("%Y-%m-%d %H:%M:%S")]
    })
    pandas_obj = pd.concat([pandas_obj, new_item])
    return Item(item_name, item_price, item_image_url, shop_url, item_id)


def db_clean():
    """
    A function to remove all the outdated listings from the db

    :return:
    """
    global pandas_obj
    idx = 0
    while idx != len(pandas_obj):
        if datetime.datetime.strptime(pandas_obj['end_time'].iat[idx],
                                      "%Y-%m-%d %H:%M:%S") < datetime.datetime.now():  # There's a possibilty that the item's listing is no longer avilable
            pandas_obj = pandas_obj.append(pandas_obj.iloc[idx]).drop_duplicates(
                keep=False)  # If the item is out of date it shall be removed from the DB
        else:
            idx += 1


def cfg_save():
    """
    A function to save current configuration to config file on the disk

    :return:
    """
    global settings
    save_buff = ""
    with open('config.cfg', 'w') as cfg_file:
        for value in settings.values():
            save_buff += str(value) + ","

        cfg_file.write(save_buff[:-1])


def cfg_load():
    """
    A function to load the config from the config file on the disk

    :return:
    """
    global settings
    with open('config.cfg', 'r') as cfg_file:
        data = cfg_file.read()
        data = data.split(',')  # The data is in csv format
        last_filled = datetime.datetime.strptime(data[0],
                                                    "%Y-%m-%d")  # The first place is for the last time the server had its item list filled up
        temp = [(DATE_FILLED, last_filled)]
        settings.update(temp)


def shutdown():
    """
    A function that wraps up the server and saves everything needed

    :return:
    """
    global pandas_obj
    db_clean()
    pandas_obj.to_csv("db.csv", index=False)
    cfg_save()


def startup():
    """
    A function that setups everything up for the server to run

    :return:
    """
    global pandas_obj
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)  # Setup the printing of panadas to show the entire output
    pandas_obj = pd.read_csv('db.csv')  # Load the database of ebay items from the file
    db_clean()  # Remove out-of-date entries of ebay items
    cfg_load()  # Load the config from the config file

    api = Connection(config_file='ebay.yaml', siteid="EBAY-US")  # Setup the ebay api for requests
    #if settings[DATE_FILLED].date() < datetime.datetime.now().date():
    #    settings[DATE_FILLED] = datetime.datetime.now()  # This entire section of code isnt
    #    mandetory, but it could be used to fill the db with a small number of big requests instead
    #    of a large number of small requests
    #    db_fill(api)

    return api


def db_fill(api):
    """
    This function fills up the item database and should run once everyday. In case the ebay api limit
    is reached, items should be simply pulled from here instead.

    :param api:
    :return:
    """
    price_list = [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]
    # The prices we want the items to be

    for price in price_list:  # For each price we will query ebay
        if price <= 100:  # The higher the price the lesser the number of items we want to find
            entries = 100
        else:
            entries = 10

        print("Generating items for price " + str(price))

        request = {
            'keywords': make_keywords(),
            'itemFilter': [
                {'name': 'HideDuplicateItems', 'value': 'true'},
                {'name': 'MinQuantity', 'value': 1},  # To ensure the item is still buyable

                {'name': 'MinPrice', 'value': float(price - (price * 0.1))},
                {'name': 'MaxPrice', 'value': float(price + (price * 0.1))}

            ],
            'paginationInput': {
                'entriesPerPage': entries,
                'pageNumber': 1
            },
        }

        response = api.execute('findItemsByKeywords', request)
        if response.reply.ack != 'Failure':
            if hasattr(response.reply.searchResult, 'item'):
                for i, item in enumerate(response.reply.searchResult.item):
                    if i % 5 == 0:
                        print(str(i) + '%')
                    db_add(item)

        pandas_obj.to_csv("db.csv", index=False)  # Saving the progress if we stop in the middle


def run():
    global pandas_obj

    api = startup()

    query = input("Enter query\n")
    while query != "exit":
        if query == "print":
            print(pandas_obj)
            query = input("Enter query\n")
            continue

        price, keyword = pasre_query(query)

        item = None
        if keyword is None:  # A price only query
            item = db_search(
                price)  # To lower the number of api calls, check if the database already contains a similar item
            keyword = make_keywords()  # In case search_db fails, we should invent a keyword

        if item is None:  # Assuming an item wasn't found, or this is a price+keyword query, make an api call
            tries = 0
            while tries <= 10:  # Because this algo has quite a high chances of failing when the price is high, we shall allow for up to 10*4 retries
                tries += 1
                deviation = 10
                found = False
                while not found and deviation < 40:  # If an item wasn't found, retry with a higher deviation
                    response = api.execute('findItemsByKeywords', create_request(keyword, 1, price, deviation))
                    if response.reply.ack == 'Failure':
                        raise QueryError("Ebay error - " + str(response.reply.errorMessage.error.message))
                    deviation += 10
                    found = hasattr(response.reply.searchResult, 'item')
                keyword = make_keywords()

            if hasattr(response.reply.searchResult, 'item'):  # Check if any results were found
                item = db_add(response.reply.searchResult.item[0])
            else:
                print("No results")

        if item is not None:
            print(item)
        query = input("Enter query\n")

    shutdown()


if __name__ == '__main__':
    run()
