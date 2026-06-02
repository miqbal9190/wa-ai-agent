import os, requests, json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SHEETS_URL = os.environ.get("GOOGLE_SHEETS_URL")
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    message = data.get('message', '').strip()
    sender = data.get('sender', '')
    group_id = data.get('group', '')
    
    # 1. PERINTAH REKAP ORDER (Pemicu: !rekap)
    if message.lower().startswith("!rekap"):
        try:
            # Ambil data dari Google Sheets
            res = requests.get(GOOGLE_SHEETS_URL, timeout=10)
            
            try:
                orders_data = res.json()
            except:
                orders_data = res.text
                
            if not orders_data or str(orders_data).strip() == "[]":
                reply_to_wa("Belum ada data orderan jastip yang tercatat di Google Sheets.", sender, group_id)
                return jsonify({"status": "success"})
            
            # KOREKSI DISINI: Menggunakan format penamaan model 'models/gemini-1.5-flash-latest' atau 'gemini-1.5-flash' yang lebih kompatibel
            model_text = genai.GenerativeModel('models/gemini-1.5-flash')
            prompt = (
                "Kamu adalah asisten jastip 'Jastip Arzanka'. Tugasmu adalah membuat laporan rekapan pesanan yang rapi "
                "dari data berikut. Kelompokkan berdasarkan nama Event. Hitung juga total omset (Total akumulasi dari kolom total/harga). "
                "Gunakan format teks WhatsApp yang menarik, pakai emoji, dan cetak tebal (pake tanda bintang *) pada poin penting. "
                f"Data pesanan: {str(orders_data)}"
            )
            response = model_text.generate_content(prompt)
            reply_to_wa(response.text, sender, group_id)
        except Exception as e:
            # Jika masih terkendala model lama, kita coba fallback ke penamaan tanpa prefix
            try:
                model_text = genai.GenerativeModel('gemini-1.5-flash-latest')
                response = model_text.generate_content(prompt)
                reply_to_wa(response.text, sender, group_id)
            except Exception as inner_e:
                reply_to_wa(f"Gagal mengambil data rekapan dari sistem. (Detail: {str(inner_e)[:50]})", sender, group_id)
            
    # 2. PERINTAH MASUKKAN ORDER (Pemicu: !order)
    elif message.lower().startswith("!order"):
        try:
            isi_text = message[6:].strip()
            bagian = [b.strip() for b in isi_text.split('-')]
            
            if len(bagian) < 4:
                raise ValueError("Format kurang lengkap")
                
            buyer_name = bagian[0]
            product_name = bagian[1]
            qty_clean = "".join(filter(str.isdigit, bagian[2]))
            harga_clean = "".join(filter(str.isdigit, bagian[3]))
            event_name = bagian[4] if len(bagian) >= 5 and bagian[4] else "Reguler"
            
            ai_json = {
                "event": event_name,
                "buyer": buyer_name,
                "product": product_name,
                "qty": int(qty_clean),
                "harga": int(harga_clean)
            }
            
            requests.post(GOOGLE_SHEETS_URL, json=ai_json, timeout=10)
            msg = f"Baik, Pesanan dari {ai_json['buyer']} ({ai_json['product']} - {ai_json['qty']}pcs) telah dicatat untuk Event: {ai_json['event']}."
            reply_to_wa(msg, sender, group_id)
            
        except Exception as e:
            reply_to_wa(
                "Format pesanan belum tepat! Gunakan format praktis ini:\n\n"
                "👉 !order Nama Pembeli - Nama Produk - Jumlah - Harga\n\n"
                "Contoh Pesanan Biasa:\n!order Ibun - Gelas - 3 - 10000\n\n"
                "Contoh Jika Ada Event Khusus:\n!order Ibun - Gelas - 3 - 10000 - Live Bandung", 
                sender, 
                group_id
            )

    return jsonify({"status": "success"})

def reply_to_wa(text, sender, group_id):
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    target = group_id if group_id else sender
    payload = {"target": target, "message": text}
    requests.post(url, headers=headers, data=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
