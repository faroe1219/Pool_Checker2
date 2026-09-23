import datetime
import io
import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from google import genai
from google.genai.errors import ServerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# 1. 本日の日付からYYYYMMDD形式の文字列を生成
today = datetime.date.today()
date_str = today.strftime("%Y%m%d")

# 2. URLの構築
url = f"https://www.nakano-sports-comm.net/?s=1&mode=n&type=008&v={date_str}"
print(f"Checking URL: {url}")

# 3. ページの取得とPDFのテキスト抽出
response = requests.get(url)
response.encoding = response.apparent_encoding

pdf_text = ""
if response.content.startswith(b"%PDF"):
    print("直接PDFファイルが取得されました。テキストを抽出します。")
    with io.BytesIO(response.content) as f:
        reader = PdfReader(f)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                pdf_text += extracted + "\n"
else:
    soup = BeautifulSoup(response.text, "html.parser")
    pdf_link = None
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            pdf_link = a["href"]
            break

    if pdf_link:
        if not pdf_link.startswith("http"):
            from urllib.parse import urljoin
            pdf_link = urljoin(url, pdf_link)
        
        print(f"PDFリンクを発見しました: {pdf_link}")
        pdf_response = requests.get(pdf_link)
        with io.BytesIO(pdf_response.content) as f:
            reader = PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pdf_text += extracted + "\n"
    else:
        print("PDFリンクが見つからないため、ページ内のテキストを使用します。")
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.extract()
        pdf_text = soup.get_text(separator="\n", strip=True)

pdf_text = pdf_text[:10000]

# 4. Gemini APIを使った要約処理
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

formatted_date = today.strftime("%m月%d日")
weekdays = ["月", "火", "水", "木", "金", "土", "日"]
weekday_str = weekdays[today.weekday()]
date_display = f"{formatted_date}（{weekday_str}）"

prompt = f"""
本日は {date_display} です。
以下のプール利用状況の案内およびスケジュールデータのテキストから、【本日は {date_display} である】という日付の行・該当箇所を極めて詳細に読み取ってください。

特に以下の点に注意し、見落としなく要約を作成してください：

1. **【最重要】本日の営業・利用可否の結論**
   - 本日は休業日ではないか、通常の営業時間内か。
   - **本日のスケジュール（テキストや表データ）に「イベント」「団体利用（全面貸切）」などの予定が入っていないかを徹底的に確認してください。**
   - もし本日、イベントや団体利用等によって一般利用が制限される、または全面貸切となる時間帯がある場合は、**その旨を要約の最初に、最も目立つように具体的に（何時〜何時まで利用不可など）記載してください。**

2. **時間帯ごとの空き状況や利用制限**
   - 本日の時間帯ごとのスケジュール（教室、イベント、特別プログラム、団体利用など）を具体的に網羅してください。
   - 文字が入っていないコースが一般開放となりますが、イベントや貸切で使えない時間帯やコースがあれば明確に指摘してください。

3. **教室、イベント、団体利用の有無**
   - 本日予定されているイベントや教室、団体利用の有無と、その正確な時間帯を漏れなく記述してください。

4. **利用時の重要な注意点やルール**
   - スイムキャップの着用必須、毎時50分からの休憩時間、持ち物（くつ袋、指定の飲み物）、メガネ・装飾品の制限、年齢・更衣室のルールなど。

【利用データのテキスト】
{pdf_text}
"""
"""

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type(ServerError),
    reraise=True
)
def call_gemini_with_retry():
    return client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )

print("AIによる要約を実行中...\n")
response = call_gemini_with_retry()

print("=== 【本日のプール利用状況 要約】 ===")
print(response.text)
print("======================================")

# 5. メール送信処理 (Gmail経由で送信)
sender_email = "faroe1219@gmail.com"  # ←ご自身のGmailアドレスを入力してください
receiver_email = "nobumatu@hotmail.com"                  # ←受け取りたいアドレス
mail_password = os.environ.get("MAIL_PASSWORD")

if mail_password:
    try:
        subject = f"【プール利用状況】{date_display}の要約"
        msg = MIMEText(response.text, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender_email
        msg["To"] = receiver_email

        print("\nメールを送信中 (Gmail SMTP)...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, mail_password)
            server.sendmail(sender_email, [receiver_email], msg.as_string())
        print("メールの送信が完了しました！")
        
    except Exception as e:
        print(f"メール送信に失敗しました: {e}")
else:
    print("MAIL_PASSWORDが設定されていないため、メール送信をスキップします。")
