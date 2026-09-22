import datetime
import os
from google import genai
from google.genai import types
import pypdf
import requests

# 1. 今日（2026年9月22日など）の日付に合わせたPDFのURLを組み立てる
today_str = datetime.date.today().strftime("%Y%m%d")
# ご提示いただいたURLの規則に合わせ、今日の付番を自動生成します
pdf_url = f"https://www.nakano-sports-comm.net/?s=1&mode=n&type=008&v={today_str}"

print(f"Checking URL: {pdf_url}")

try:
  # 2. PDFファイルをダウンロード
  response = requests.get(pdf_url)
  response.raise_for_status()

  # 一時的にファイルとして保存
  pdf_filename = "temp_schedule.pdf"
  with open(pdf_filename, "wb") as f:
    f.write(response.content)

  # 3. pypdfを使ってPDFから文字を抽出する
  reader = pypdf.PdfReader(pdf_filename)
  pdf_text = ""
  for page in reader.pages:
    text = page.extract_text()
    if text:
      pdf_text += text + "\n"

  if not pdf_text.strip():
    print(
        "PDFから文字を抽出できませんでした（画像形式の可能性があります）。"
    )
    exit(0)

  # 4. Google GenAI (Gemini) を使って要約する
  # GitHubに登録した秘密のキーを使ってAIを初期化します
  client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

  prompt = f"""
以下のテキストは、本日の鷺宮体育館プールの利用状況が記載されたPDFの内容です。
今日のプールの利用状況（一般開放の時間帯、混雑しそうな時間、注意点など）を分かりやすく、箇条書きで要約してください。

【PDFの内容】
{pdf_text}
"""

  print("AIによる要約を実行中...")
  response = client.models.generate_content(
      model="gemini-3.6-flash",
      contents=prompt,
  )

  print("\n=== 【本日のプール利用状況 要約】 ===")
  print(response.text)
  print("======================================")

  # 使い終わった一時ファイルを削除
  if os.path.exists(pdf_filename):
    os.remove(pdf_filename)

except Exception as e:
  print(f"エラーが発生しました: {e}")
