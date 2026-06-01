import os
from flask import Flask, request, jsonify
import requests
import google.generativeai as genai

app = Flask(__name__)

# Konfigurasi API (Nanti diisi di server Render)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SHEETS_URL = os.environ.get("GOOGLE_SHEETS_URL")
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    message = data.get('message', '')
    sender = data.get('sender', '') # nomor pengirim
    group_id = data.get('group', '') # ID grup jika dari grup
    
    # Ganti "@xxx" dengan username/panggilan bot Anda di WA, misal "@bot"
    BOT_TRIGGER = "@xxx" 
    
    if BOT_TRIGGER in message:
        clean_message = message.replace(BOT_TRIGGER, "").strip()
        
        # JIKA PERINTAH REKAP ORDER
        if "rekap order" in clean_message.lower():
            try:
                # Ambil data dari Google Sheets
                res = requests.get(GOOGLE_SHEETS_URL)
                orders = res.json()
                
                if not orders:
                    reply_to_wa("Belum ada data orderan yang tercatat di sistem.", sender, group_id)
                    return jsonify({"status": "success"})
                
                # Minta Gemini merangkum menjadi format teks yang rapi
                prompt_rekap = f"Tolong buatkan teks rangkuman/rekapan pesanan yang rapi dari data JSON ini: {str(orders)}. Hitung juga total omsetnya keseluruhan."
                response = model.generate_content(prompt_rekap)
                
                reply_to_wa(response.text, sender, group_id)
            except Exception as e:
                reply_to_wa("Gagal mengambil rekapan data.", sender, group_id)
                
        # JIKA PERINTAH MASUKKAN ORDER
        elif "order" in clean_message.lower():
            # Minta Gemini memecah teks menjadi data terstruktur JSON
            prompt_order = (
                f"Ekstrak teks pesanan berikut menjadi format JSON dengan key: buyer, product, qty, harga. "
                f"Pastikan qty dan harga hanya berupa angka saja. Teks pesanan: {clean_message}. "
                f"Contoh output wajib seperti ini tanpa teks tambahan: {{\"buyer\": \"Ani\", \"product\": \"Pasta Gigi\", \"qty\": 3, \"harga\": 10000}}"
            )
            
            try:
                response = model.generate_content(prompt_order)
                ai_result = eval(response.text.strip().replace("```json", "").replace("
```", ""))
                
                # Kirim data hasil pecahan AI ke Google Sheets Web App
                requests.post(GOOGLE_SHEETS_URL, json=ai_result)
                
                # Balas konfirmasi ke WA
                sukses_msg = f"Baik, Pesanan dari {ai_result['buyer']} yaitu {ai_result['product']} sebanyak {ai_result['qty']}pcs dengan harga {ai_result['harga']:,}/pcs telah dicatat."
                reply_to_wa(sukses_msg, sender, group_id)
            except:
                reply_to_wa("Format order salah atau gagal diproses oleh AI. Pastikan formatnya: Nama | Produk | Qty | Harga", sender, group_id)

    return jsonify({"status": "success"})

def reply_to_wa(text, sender, group_id):
    # Fungsi mengirim pesan balik melalui Fonnte Gateway
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    
    # Jika pesan berasal dari grup, balas ke grup tersebut
    target = group_id if group_id else sender
    
    payload = {
        "target": target,
        "message": text
    }
    requests.post(url, headers=headers, data=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
