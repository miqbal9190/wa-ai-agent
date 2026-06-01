import os
from flask import Flask, request, jsonify
import requests
import google.generativeai as genai

app = Flask(__name__)

# Konfigurasi API dari Environment Variables Render
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
    
    # Ganti dengan nama pemicu bot Anda di grup WA, misal "@bot"
    BOT_TRIGGER = "@xxx" 
    
    if BOT_TRIGGER in message:
        clean_message = message.replace(BOT_TRIGGER, "").strip()
        
        # 1. JIKA PERINTAH REKAP ORDER
        if "rekap order" in clean_message.lower():
            try:
                res = requests.get(GOOGLE_SHEETS_URL)
                orders = res.json()
                
                if not orders:
                    reply_to_wa("Belum ada data orderan yang tercatat di sistem.", sender, group_id)
                    return jsonify({"status": "success"})
                
                prompt_rekap = f"Tolong buatkan teks rangkuman/rekapan pesanan yang rapi dari data JSON ini: {str(orders)}. Hitung juga total omsetnya keseluruhan."
                response = model.generate_content(prompt_rekap)
                reply_to_wa(response.text, sender, group_id)
            except:
                reply_to_wa("Gagal mengambil rekapan data dari Google Sheets.", sender, group_id)
                
        # 2. JIKA PERINTAH MASUKKAN ORDER
        elif "order" in clean_message.lower():
            # Prompt diperbarui agar AI pintar mengekstrak data beserta nama event jika ada
            prompt_order = (
                "Ekstrak teks pesanan menjadi format JSON dengan key wajib: event, buyer, product, qty, harga. "
                "Jika di dalam teks tidak disebutkan nama event/acara khusus, isi key 'event' dengan teks 'Reguler'. "
                "Pastikan qty dan harga hanya berupa angka saja tanpa titik/rp. "
                f"Teks pesanan: {clean_message}"
            )
            
            try:
                response = model.generate_content(prompt_order)
                # Bersihkan teks response dari pembungkus markdown code block jika ada
                clean_json_text = response.text.strip().replace("```json", "").replace("
```", "")
                
                import json
                ai_result = json.loads(clean_json_text)
                
                # Kirim ke Web App Google Sheets
                requests.post(GOOGLE_SHEETS_URL, json=ai_result)
                
                # Balas konfirmasi ke WhatsApp
                sukses_msg = f"Baik, Pesanan dari {ai_result['buyer']} untuk produk {ai_result['product']} sebanyak {ai_result['qty']}pcs telah dicatat (Event: {ai_result['event']})."
                reply_to_wa(sukses_msg, sender, group_id)
            except Exception as e:
                reply_to_wa("Format order gagal diproses oleh AI. Pastikan format: Nama | Produk | Qty | Harga", sender, group_id)

    return jsonify({"status": "success"})

def reply_to_wa(text, sender, group_id):
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    target = group_id if group_id else sender
    payload = {
        "target": target,
        "message": text
    }
    requests.post(url, headers=headers, data=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
