from django.shortcuts import render

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextSendMessage

import requests
import json
import datetime
import os

# Create your views here.
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)
index_closing_price_in_data = 6
index_num_in_title = 1
index_name_in_title = 2


# You will see 'Forbidden (CSRF cookie not set.)' if missing below
@csrf_exempt
def callback(request):
    print("Callback")
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
                now = datetime.datetime.now()
                url = 'http://www.twse.com.tw/exchangeReport/STOCK_DAY?date=%s&stockNo=%s' % (now.strftime("%Y%m%d"), event.message.text)
                r = requests.get(url)
                data = r.json()
                try:
                    # Get stock name and number
                    # Title example: "107年12月 2330 台積電           各日成交資訊"
                    all_title = data['title']
                    title_list = all_title.split(' ')

                    # Reply stock price
                    last_index = len(data['data']) - 1
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=title_list[index_num_in_title] + title_list[index_name_in_title] + " " +
                                        data['data'][last_index][index_closing_price_in_data])
                    )
                except KeyError:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="請輸入上市公司股票代碼")
                    )
        return HttpResponse()
    else:
        print("Not POST request, debug only...")
        now = datetime.datetime.now()
        print(now.strftime("%Y%m%d"))
        url = 'http://www.twse.com.tw/exchangeReport/STOCK_DAY?date=%s&stockNo=2330' % (now.strftime("%Y%m%d"))
        r = requests.get(url)
        data = r.json()
        try:
            all_title = data['title']
            title_list = all_title.split(' ')
            print(title_list[1] + ":" + title_list[2])
            print(len(data['data']))
            last_index = len(data['data']) - 1
            print(data['data'][last_index][index_closing_price_in_data])
            return HttpResponse("I'm here")
        except KeyError:
            return HttpResponse("請輸入上市公司股票代碼")

        # return HttpResponseBadRequest()
