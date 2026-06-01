import os, requests, json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SHEETS_URL = os.environ.get("GOOGLE_SHEETS_URL")
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    message = data.get('message', '')
    sender = data.get('sender', '')
    group_id = data.get('group', '')
    
    # Ganti "@xxx" dengan trigger Anda, misal "@bot"
    BOT_TRIGGER = "@xxx" 
    
    if BOT_TRIGGER in message:
        clean_msg = message.replace(BOT_TRIGGER, "").strip()
        
        # 1. PERINTAH REKAP ORDER
        if "rekap order" in clean_msg.lower():
            try:
                res = requests.get(GOOGLE_SHEETS_URL)
                orders = res.json()
                if not orders:
                    reply_to_wa("Belum ada data orderan.", sender, group_id)
                    return jsonify({"status": "success"})
                
                prompt = f"Buatkan rekapan pesanan yang rapi dan hitung total omset dari data ini: {str(orders)}"
                response = model.generate_content(prompt)
                reply_to_wa(response.text, sender, group_id)
            except:
                reply_to_wa("Gagal mengambil data rekapan.", sender, group_id)
                
        # 2. PERINTAH MASUKKAN ORDER
        elif "order" in clean_msg.lower():
            prompt = (
                "Ekstrak teks menjadi JSON dengan key: event, buyer, product, qty, harga. "
                "Jika tidak ada nama event, isi 'event' dengan 'Reguler'. "
                "Qty dan harga wajib angka saja. "
                f"Teks: {clean_msg}"
            )
            try:
                response = model.generate_content(prompt)
                txt = response.text.strip().replace("```json", "").replace("
```", "")
                ai_json = json.loads(txt)
                
                requests.post(GOOGLE_SHEETS_URL, json=ai_json)
                
                msg = f"Baik, Pesanan dari {ai_json['buyer']} ({ai_json['product']} - {ai_json['qty']}pcs) telah dicatat untuk Event: {ai_json['event']}."
                reply_to_wa(msg, sender, group_id)
            except:
                reply_to_wa("Format salah. Pastikan: Nama | Produk | Qty | Harga", sender, group_id)

    return jsonify({"status": "success"})

def reply_to_wa(text, sender, group_id):
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    target = group_id if group_id else sender
    payload = {"target": target, "message": text}
    requests.post(url, headers=headers, data=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
