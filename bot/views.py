from django.shortcuts import render

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextSendMessage, ImageSendMessage

from datetime import datetime
import requests
import json
import os
import matplotlib.pyplot as plt
import numpy as np
import base64

from bot.models import Stock

# Create your views here.
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)
index_closing_price_in_data = 6
index_num_in_title = 1
index_name_in_title = 2


def drawPoint(arrX, arrY, y, size, color):
    plt.scatter([np.array(arrX)[y]], [np.array(arrY)[y]], s=size, color=color)
    plt.annotate(np.array(arrY)[y],
                 xy=(np.array(arrX)[y], np.array(arrY)[y]),
                 fontsize=10)


def paintingPicToImgur(data):
    # Painting with matplotlib
    x = []
    y = []
    for i in range(len(data['data'])):
        x.append(data['data'][i][0][7:])  # Only get date
        y.append(float(data['data'][i][index_closing_price_in_data]))
    print(np.array(x))
    print(np.array(y))

    plt.style.use('ggplot')

    # Input x, y numpy array
    plt.plot(np.array(x), np.array(y))

    # Mark max/min values
    maxIndexOfY = np.where(np.array(y) == max(np.array(y)))[0][0]
    minIndexOfY = np.where(np.array(y) == min(np.array(y)))[0][0]
    drawPoint(np.array(x), np.array(y), maxIndexOfY, 10, "red")
    drawPoint(np.array(x), np.array(y), minIndexOfY, 10, "red")

    # Mark closing price value
    drawPoint(np.array(x), np.array(y), -1, 10, "red")

    plt.xlabel("Date")
    plt.ylabel("Closing Price")
    plt.title("Stock Pricing Trend - " + data['data'][0][0][0:6])  # Add year/month to title

    plt.savefig("stock.png", dpi=300, format="png")

    # Upload picture to Imgur
    f = open("stock.png", "rb")  # open our image file as read only in binary mode
    imageData = f.read()  # read in our image file
    b64Image = base64.standard_b64encode(imageData)

    client_id = settings.IMGUR_CLIENT_ID
    headers = {'Authorization': 'Client-ID ' + str(client_id)}
    data = {'image': b64Image, 'title': 'stock'}  # create a dictionary.
    ret = requests.post(url="https://api.imgur.com/3/upload.json", data=data, headers=headers)
    jsonOutput = ret.json()
    return jsonOutput['data']['link']


def getStockInfo(stockId):
    now = datetime.now()
    url = 'http://www.twse.com.tw/exchangeReport/STOCK_DAY?date=%s&stockNo=%s' % (now.strftime("%Y%m%d"), stockId)
    r = requests.get(url)
    data = r.json()
    try:
        # Get stock name and number
        # Title example: "107年12月 2330 台積電           各日成交資訊"
        all_title = data['title']
        title_list = all_title.split(' ')

        # Reply stock price and trend picture
        last_index = len(data['data']) - 1
        link = paintingPicToImgur(data)
    except KeyError:
        return HttpResponse("請輸入上市公司股票代碼")

    return title_list, data['data'][last_index][index_closing_price_in_data], link


def handleMessage(text):
    cmds = text.split()
    res = ""
    link = None
    if cmds[0] == 'r':
        # register
        s, created = Stock.objects.get_or_create(stock_id=int(cmds[1]))
        if not created:
            res = "您已註冊過此股票代號:" + cmds[1]
        else:
            res = "已為您註冊股票:" + cmds[1]
    elif cmds[0] == 'd':
        # delete
        if Stock.objects.filter(stock_id=int(cmds[1])).exists():
            Stock.objects.filter(stock_id=int(cmds[1])).delete()
            res = "已刪除此股票紀錄:" + cmds[1]
        else:
            res = "您尚未註冊此股票代號:" + cmds[1]
    elif cmds[0] == 'q':
        # query
        res += "你所註冊過的股票代號: \n"
        for s in Stock.objects.all():
            res += str(s.stock_id) + "\n"
    elif cmds[0] == 'h':
        # help
        res = """
請輸入以下指令:
r <股票代號>: 註冊股票, 會收到每日收盤價推播
d <股票代號>: 刪除此股票的每日收盤價推播
q: 查詢註冊的股票
h: 指令說明
<股票代號>: 查詢此股票收盤價
        """
    else:
        title, price, link = getStockInfo(cmds[0])
        res = title[index_num_in_title] + title[index_name_in_title] + " " + price
    return res, link


# You will see 'Forbidden (CSRF cookie not set.)' if missing below
@csrf_exempt
def callback(request):
    if request.method == 'POST':
        print("POST request")
        signature = request.META['HTTP_X_LINE_SIGNATURE']
        body = request.body.decode('utf-8')

        try:
            events = parser.parse(body, signature)
        except InvalidSignatureError:
            return HttpResponseForbidden()
        except LineBotApiError:
            return HttpResponseBadRequest()

        for event in events:
            if isinstance(event, MessageEvent):
                res, link = handleMessage(event.message.text)
                try:
                    if link:
                        line_bot_api.reply_message(
                            event.reply_token, [
                                TextSendMessage(text=res),
                                ImageSendMessage(original_content_url=link, preview_image_url=link)])
                    else:
                        line_bot_api.reply_message(
                            event.reply_token, TextSendMessage(text=res))
                except ValueError:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="請輸入上市公司股票代碼")
                    )
        return HttpResponse()
    else:
        print("Not POST request, debug only...")
        res, link = handleMessage('d 9876')
        print(res)
        return HttpResponse(res)


# You will see 'Forbidden (CSRF cookie not set.)' if missing below
@csrf_exempt
def pushNotification(request):
    print("Full path: ", request.get_full_path())

    # Skip notification on weekend. '5' is Saturday and '6' is Sunday.
    if datetime.now().weekday() == 5 or datetime.now().weekday() == 6:
        return HttpResponse()

    if request.method == 'PUT' and request.get_full_path() == '/bot/pushNotification/':
        for s in Stock.objects.all():
            title, price, link = getStockInfo(str(s.stock_id))
            try:
                line_bot_api.push_message(settings.LINE_USER_ID, [
                                TextSendMessage(text=title[index_num_in_title] + title[index_name_in_title] + " " +
                                                price),
                                ImageSendMessage(original_content_url=link, preview_image_url=link)
                ])
            except LineBotApiError as e:
                return HttpResponse("Line推播失敗")
    else:
        return HttpResponse("推播功能異常")
    return HttpResponse()
