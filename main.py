import os, requests, json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SHEETS_URL = os.environ.get("GOOGLE_SHEETS_URL")
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    'gemini-1.5-flash',
    generation_config={"response_mime_type": "application/json"}
)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    message = data.get('message', '').strip()
    sender = data.get('sender', '')
    group_id = data.get('group', '')
    
    # 1. PERINTAH REKAP ORDER (Pemicu: !rekap)
    if message.lower().startswith("!rekap"):
        try:
            res = requests.get(GOOGLE_SHEETS_URL)
            orders = res.json()
            if not orders:
                reply_to_wa("Belum ada data orderan harian yang tercatat.", sender, group_id)
                return jsonify({"status": "success"})
            
            model_text = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Buatkan rekapan pesanan yang rapi, kelompokkan berdasarkan nama event jika ada, dan hitung total omset dari data JSON ini: {str(orders)}"
            response = model_text.generate_content(prompt)
            reply_to_wa(response.text, sender, group_id)
        except:
            reply_to_wa("Gagal mengambil data rekapan dari sistem.", sender, group_id)
            
    # 2. PERINTAH MASUKKAN ORDER (Pemicu: !order)
    elif message.lower().startswith("!order"):
        clean_msg = message[6:].strip()
        
        prompt = (
            "Ekstrak teks pesanan berikut menjadi format JSON dengan key wajib: event, buyer, product, qty, harga. "
            "Penting: format teks input dipisahkan oleh tanda strip/minus (-) dengan urutan baku: event - buyer - product - qty - harga. "
            "Jika bagian sebelum strip pertama dikosongkan atau hanya berisi spasi/tanda minus, isi key 'event' dengan teks 'Reguler'. "
            "Pastikan qty dan harga hanya berupa angka murni tanpa karakter titik, koma, atau Rp. "
            f"Teks pesanan: {clean_msg}"
        )
        try:
            response = model.generate_content(prompt)
            ai_json = json.loads(response.text.strip())
            
            # Kirim data ke Web App Google Sheets
            requests.post(GOOGLE_SHEETS_URL, json=ai_json)
            
            msg = f"Baik, Pesanan dari {ai_json['buyer']} ({ai_json['product']} - {ai_json['qty']}pcs) telah dicatat untuk Event: {ai_json['event']}."
            reply_to_wa(msg, sender, group_id)
        except:
            reply_to_wa("Format salah! Gunakan format baku: !order event - buyer - product - qty - harga\n\nContoh: !order Live Bandung - Bu Ani - Gamis Silk - 2 - 150000\nContoh tanpa event: !order - Bu Ani - Gamis Silk - 2 - 150000", sender, group_id)

    return jsonify({"status": "success"})

def reply_to_wa(text, sender, group_id):
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    target = group_id if group_id else sender
    payload = {"target": target, "message": text}
    requests.post(url, headers=headers, data=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
