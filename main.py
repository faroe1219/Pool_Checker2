import datetime
import io
import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText
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
以下のプール利用状況の案内（またはスケジュールデータ）の内容を読み取り、
【本日の日付 ({date_display})】に焦点を当てて、以下の点について分かりやすく、箇条書きで要約してください。

1. **本日のプール営業状況**（休業日ではないか、通常の営業時間内か）
2. **コースの空き状況や利用制限**（一般開放されているコース、何コース空いているか）
3. **教室、イベント、団体利用の有無**（本日のスケジュール表や案内の中に、教室やイベント、団体利用が入っていないか。何時から何時まで使えないコースがあるかなど）
4. **利用時の重要な注意点やルール**（キャップ着用、休憩時間、持ち物など）

【利用データのテキスト】
{pdf_text}
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

# 5. メール送信処理 (nobumatu@hotmail.com へ送信)
sender_email = "nobumatu@hotmail.com"
receiver_email = "nobumatu@hotmail.com"
mail_password = os.environ.get("MAIL_PASSWORD")

if mail_password:
    try:
        subject = f"【プール利用状況】{date_display}の要約"
        msg = MIMEText(response.text, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender_email
        msg["To"] = receiver_email

        print("\nメールを送信中...")
        with smtplib.SMTP("smtp-mail.outlook.com", 587) as server:
            server.starttls()
            server.login(sender_email, mail_password)
            server.sendmail(sender_email, [receiver_email], msg.as_string())
        print("メールの送信が完了しました！")
        
    except Exception as e:
        print(f"メール送信に失敗しました: {e}")
else:
    print("MAIL_PASSWORDが設定されていないため、メール送信をスキップします。")
