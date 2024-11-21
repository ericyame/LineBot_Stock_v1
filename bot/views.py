from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextSendMessage, ImageSendMessage

from bot.models import Stock

from datetime import datetime
import base64
import logging
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import requests

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

matplotlib.use('Agg')

line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)

# Indices in data
INDEX_CLOSING_PRICE = 6
INDEX_NUM_IN_TITLE = 1
INDEX_NAME_IN_TITLE = 2


def draw_point(arrX, arrY, y_index, size, color):
    x_val = np.array(arrX)[y_index]
    y_val = np.array(arrY)[y_index]
    plt.scatter([x_val], [y_val], s=size, color=color)
    plt.annotate(str(y_val), xy=(x_val, y_val), fontsize=10)


def painting_pic_to_imgur(data, stock_id):
    # Painting with matplotlib
    x = [datum[0][7:] for datum in data['data']]
    y = [float(datum[INDEX_CLOSING_PRICE].replace(',', '')) for datum in data['data']]
    log.info(np.array(x))
    log.info(np.array(y))

    plt.style.use('ggplot')
    plt.plot(np.array(x), np.array(y), marker='o')

    # Mark max/min values
    max_index = np.argmax(y)
    min_index = np.argmin(y)
    draw_point(x, y, max_index, 10, "red")
    draw_point(x, y, min_index, 10, "red")

    # Mark closing price value
    draw_point(x, y, -1, 10, "red")

    plt.xlabel("Date")
    plt.ylabel("Closing Price")
    plt.title(f"Stock Pricing Trend - {data['data'][0][0][:6]}")  # Add year/month to title

    filename = f"stock_{stock_id}.png"
    plt.savefig(filename, dpi=300, format="png")
    plt.clf()

    # Upload picture to Imgur
    with open(filename, "rb") as f:
        image_data = f.read()

    headers = {'Authorization': f'Client-ID {settings.IMGUR_CLIENT_ID}'}
    data = {'image': base64.standard_b64encode(image_data), 'title': 'stock'}  # create a dictionary.
    response = requests.post(url="https://api.imgur.com/3/upload.json", data=data, headers=headers)
    json_output = response.json()
    return json_output['data']['link']


def get_stock_info(stock_id):
    now = datetime.now()
    url = f'http://www.twse.com.tw/exchangeReport/STOCK_DAY?date={now.strftime("%Y%m%d")}&stockNo={stock_id}'
    response  = requests.get(url)
    data = response .json()

    if data['stat'] != 'OK':
        return None, None, None
    # Get stock name and number
    # Title example: "107年12月 2330 台積電           各日成交資訊"
    all_title = data['title']
    title_list = all_title.split(' ')

    # Reply stock price and trend picture
    title = data['title'].split(' ')
    last_data = data['data'][-1][INDEX_CLOSING_PRICE]
    link = painting_pic_to_imgur(data, stock_id)

    return title, last_data, link


def handle_message(text):
    cmds = text.split()
    command, res, link = cmds[0], "", None

    if command == 'r':
        # register
        stock_id = int(cmds[1])
        stock, created = Stock.objects.get_or_create(stock_id=stock_id)
        res = f"已為您註冊股票: {cmds[1]}" if created else f"您已註冊過此股票代號: {cmds[1]}"
    elif cmds[0] == 'd':
        # delete
        stock_id = int(cmds[1])
        if Stock.objects.filter(stock_id=stock_id).exists():
            Stock.objects.filter(stock_id=stock_id).delete()
            res = f"已刪除此股票紀錄: {cmds[1]}"
        else:
            res = f"您尚未註冊此股票代號: {cmds[1]}"
    elif cmds[0] == 'q':
        # query
        res = "你所註冊過的股票代號:\n" + "\n".join(str(stock.stock_id) for stock in Stock.objects.all())
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
        title, price, link = get_stock_info(cmds[0])
        if title:
            res = f"{title[INDEX_NUM_IN_TITLE]} {title[INDEX_NAME_IN_TITLE]} {price}"

    return res, link


# You will see 'Forbidden (CSRF cookie not set.)' if missing below
@csrf_exempt
def callback(request):
    if request.method == 'POST':
        log.info("POST request")
        signature = request.META['HTTP_X_LINE_SIGNATURE']
        body = request.body.decode('utf-8')

        try:
            events = parser.parse(body, signature)
        except (InvalidSignatureError, LineBotApiError):
            return HttpResponseForbidden()

        for event in events:
            if isinstance(event, MessageEvent):
                res, link = handle_message(event.message.text)
                if link:
                    line_bot_api.reply_message(
                        event.reply_token, [
                            TextSendMessage(text=res),
                            ImageSendMessage(original_content_url=link, preview_image_url=link)])
                elif res:
                    line_bot_api.reply_message(
                        event.reply_token, TextSendMessage(text=res))
                else:
                    line_bot_api.reply_message(
                        event.reply_token, TextSendMessage(text="請輸入上市公司股票代碼"))
        return HttpResponse()
    else:
        log.info("Not POST request, debug only...")
        res, link = handle_message('d 9876')
        log.info(res)
        return HttpResponse(res)


# You will see 'Forbidden (CSRF cookie not set.)' if missing below
@csrf_exempt
def push_notification(request):
    log.info(f"Full path: {request.get_full_path()}")

    # Skip notification on weekend. '5' is Saturday and '6' is Sunday.
    if datetime.now().weekday() in {5, 6}:
        return HttpResponse()

    if request.method == 'PUT' and request.get_full_path() == '/bot/push_notification/':
        for stock in Stock.objects.all():
            title, price, link = get_stock_info(str(stock .stock_id))
            if title:
                line_bot_api.push_message(settings.LINE_USER_ID, [
                                TextSendMessage(text=f"{title[INDEX_NUM_IN_TITLE]} {title[INDEX_NAME_IN_TITLE]} {price}"),
                                ImageSendMessage(original_content_url=link, preview_image_url=link)
                ])
            else:
                line_bot_api.push_message(
                    settings.LINE_USER_ID, TextSendMessage(text=f"{stock.stock_id} 不是上市公司股票代碼"))
    else:
        return HttpResponse("推播功能異常")
    return HttpResponse()
