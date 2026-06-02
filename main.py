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
    group_id = data.get('group', '') # Menangkap ID Grup jika pesan dari grup
    
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
        try:
            # Mengambil teks SETELAH kata !order
            isi_text = message[6:].strip()
            
            # Kita paksa pecah teks berdasarkan tanda strip (-)
            bagian = [b.strip() for b in isi_text.split('-')]
            
            # Validasi: Format baku wajib punya 5 bagian (event, buyer, product, qty, harga)
            # Karena dipecah oleh 4 tanda strip, maka minimal harus menghasilkan 5 elemen array.
            if len(bagian) < 5:
                raise ValueError("Bagian kurang")
                
            # Jika bagian event kosong, otomatis isi 'Reguler'
            event_name = bagian[0] if bagian[0] else "Reguler"
            buyer_name = bagian[1]
            product_name = bagian[2]
            
            # Membersihkan angka qty dan harga dari karakter non-angka
            qty_clean = "".join(filter(str.isdigit, bagian[3]))
            harga_clean = "".join(filter(str.isdigit, bagian[4]))
            
            # Susun menjadi JSON murni
            ai_json = {
                "event": event_name,
                "buyer": buyer_name,
                "product": product_name,
                "qty": int(qty_clean),
                "harga": int(harga_clean)
            }
            
            # Kirim data langsung ke Web App Google Sheets tanpa lewat Gemini (Biar 100% Akurat & Cepat!)
            requests.post(GOOGLE_SHEETS_URL, json=ai_json)
            
            msg = f"Baik, Pesanan dari {ai_json['buyer']} ({ai_json['product']} - {ai_json['qty']}pcs) telah dicatat untuk Event: {ai_json['event']}."
            reply_to_wa(msg, sender, group_id)
            
        except Exception as e:
            reply_to_wa(
                "Format salah! Gunakan format baku dengan pemisah strip (-):\n\n"
                "!order Nama Event - Nama Pembeli - Nama Produk - Jumlah - Harga\n\n"
                "Contoh Pakai Event:\n!order Live Bandung - Bu Ani - Gamis Silk - 2 - 150000\n\n"
                "Contoh Tanpa Event:\n!order - Bu Ani - Gamis Silk - 2 - 150000", 
                sender, 
                group_id
            )

    return jsonify({"status": "success"})

def reply_to_wa(text, sender, group_id):
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    # Jika pesan berasal dari grup (group_id ada isinya), balas ke grup tersebut. Jika tidak, balas japri (sender).
    target = group_id if group_id else sender
    payload = {"target": target, "message": text}
    requests.post(url, headers=headers, data=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
