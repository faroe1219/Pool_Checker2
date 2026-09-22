import datetime
import os
from google import genai
import pypdf
import requests

# 1. 今日（2026年9月22日など）の日付に合わせたPDFのURLを組み立てる
today_str = datetime.date.today().strftime("%Y%m%d")
pdf_url = f"https://www.nakano-sports-comm.net/?s=1&mode=n&type=008&v={today_str}"

print(f"Checking URL: {pdf_url}")

try:
  # 2. PDFファイルをダウンロード
  response = requests.get(pdf_url)
  response.raise_for_status()

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
  client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

prompt = f"""
以下のテキストは、鷺宮体育館プールの利用状況が記載されたPDFの内容です。
今日（本日の日付に該当する箇所）のスケジュールを重点的に読み取り、以下の点について分かりやすく、箇条書きで要約してください。

1. **本日の日付と曜日、およびその日の全体的な混雑状況・傾向**
2. **コースの空き状況や利用制限**（何コースが一般開放されていて、どの時間帯に空いているか）
3. **教室、イベント、団体利用の有無**（何時から何時まで、どのコースが使えないか、または全館貸切などのイベントがあるか）
4. **利用時の重要な注意点やルール**（キャップ着用、休憩時間など）

【PDFの内容】
{pdf_text}
"""

  print("AIによる要約を実行中...")
  # ここを gemini-3.6-flash に指定しています
  response = client.models.generate_content(
      model="gemini-3.6-flash",
      contents=prompt,
  )

  print("\n=== 【本日のプール利用状況 要約】 ===")
  print(response.text)
  print("======================================")

  # 一時ファイルの削除
  if os.path.exists(pdf_filename):
    os.remove(pdf_filename)

except Exception as e:
  print(f"エラーが発生しました: {e}")
