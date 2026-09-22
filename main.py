import datetime
import os
import requests
from bs4 import BeautifulSoup
from google import genai

# 1. 本日の日付からYYYYMMDD形式の文字列を生成 (例: 20260922)
today = datetime.date.today()
date_str = today.strftime("%Y%m%d")

# 2. URLの構築
url = f"https://www.nakano-sports-comm.net/?s=1&mode=n&type=008&v={date_str}"
print(f"Checking URL: {url}")

# 3. Webページのスクレイピング
response = requests.get(url)
response.encoding = response.apparent_encoding
soup = BeautifulSoup(response.text, "html.parser")

# ページのテキスト抽出
page_text = soup.get_text(separator="\n", strip=True)

# 4. Gemini APIを使った要約・情報抽出
# 環境変数からAPIキーを取得
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# 本日の日付（月/日 曜日）をプロンプトに反映させる
formatted_date = today.strftime("%m月%d日")
weekdays = ["月", "火", "水", "木", "金", "土", "日"]
weekday_str = weekdays[today.weekday()]
date_display = f"{formatted_date}（{weekday_str}）"

prompt = f"""
本日は {date_display} です。
以下のWebページ（プール利用状況の案内およびスケジュール）の内容を読み取り、
【本日の日付 ({date_display})】に焦点を当てて、以下の点について分かりやすく、箇条書きで要約してください。

1. **本日のプール営業状況**（休業日ではないか、通常の営業時間内か）
2. **コースの空き状況や利用制限**（一般開放されているコース、何コース空いているか）
3. **教室、イベント、団体利用の有無**（本日のスケジュール表や案内の中に、教室やイベント、団体利用が入っていないか。何時から何時まで使えないコースがあるかなど）
4. **利用時の重要な注意点やルール**（キャップ着用、休憩時間、持ち物など）

【Webページの内容】
{page_text}
"""

print("AIによる要約を実行中...\n")
response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt,
)

print("=== 【本日のプール利用状況 要約】 ===")
print(response.text)
print("======================================")
