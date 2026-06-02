import os, requests, json
from flask import Flask, request, jsonify

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SHEETS_URL = os.environ.get("GOOGLE_SHEETS_URL")
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    message = data.get('message', '').strip()
    sender = data.get('sender', '')
    group_id = data.get('group', '')
    
    # 1. PERINTAH REKAP ORDER (Pemicu: !rekap)
    if message.lower().startswith("!rekap"):
        try:
            res = requests.get(GOOGLE_SHEETS_URL, timeout=10)
            orders_data = res.json()
                
            if not orders_data or str(orders_data).strip() == "[]" or not isinstance(orders_data, list):
                reply_to_wa("Belum ada data orderan jastip yang tercatat di Google Sheets.", sender, group_id)
                return jsonify({"status": "success"})
            
            # KUNCINYA DISINI: Kita susun data mentah Sheets menjadi teks poin-poin yang bersih
            daftar_pesanan_teks = ""
            for i, order in enumerate(orders_data, 1):
                # Ambil data dengan aman, jika kosong beri tanda strip
                ev = order.get('event', 'Reguler')
                by = order.get('buyer', 'Tanpa Nama')
                pr = order.get('product', 'Tanpa Produk')
                qt = order.get('qty', 1)
                hg = order.get('harga', 0)
                tot = order.get('total', hg * qt)
                
                daftar_pesanan_teks += f"{i}. Event: {ev} | Pembeli: {by} | Produk: {pr} | Qty: {qt} | Harga: {hg} | Total: {tot}\n"
            
            # Tembak langsung API Gemini lewat HTTP POST
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            
            prompt = (
                "Kamu adalah asisten jastip profesional dari 'Jastip Arzanka'. Tugasmu adalah membuat laporan rekapan pesanan yang rapi, "
                "cantik, dan menarik untuk dibaca di grup WhatsApp berdasarkan data penjualan di bawah ini.\n\n"
                "Aturan Laporan:\n"
                "1. Kelompokkan pesanan berdasarkan nama Event (jika eventnya 'Reguler', kelompokkan dalam Pesanan Reguler).\n"
                "2. Tuliskan detail nama pembeli, nama produk, jumlah qty, dan total harganya.\n"
                "3. Di bagian paling bawah, hitung dan tampilkan TOTAL OMSET KESELURUHAN (penjumlahan dari semua kolom Total).\n"
                "4. Gunakan gaya bahasa yang ramah, beri emoji yang sesuai, dan gunakan tanda bintang (*) untuk menebalkan poin penting agar scannable.\n\n"
                f"Data Penjualan:\n{daftar_pesanan_teks}"
            )
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
            
            gemini_res = requests.post(gemini_url, headers=headers, json=payload, timeout=15)
            gemini_output = gemini_res.json()
            
            # Ambil hasil teks dengan pengaman jika candidates kosong
            if 'candidates' in gemini_output and gemini_output['candidates']:
                text_response = gemini_output['candidates'][0]['content']['parts'][0]['text']
                reply_to_wa(text_response, sender, group_id)
            else:
                # Jika Google AI menolak karena alasan konten, kita berikan rekap teks standar bawaan Python (Anti-Gagal!)
                fallback_msg = "*REKAP PESANAN JASTIP ARZANKA*\n\n" + daftar_pesanan_teks
                reply_to_wa(fallback_msg, sender, group_id)
            
        except Exception as e:
            reply_to_wa(f"Gagal mengambil data rekapan dari sistem. (Detail: {str(e)[:50]})", sender, group_id)
            
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
