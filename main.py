import os, requests, json
from flask import Flask, request, jsonify
from datetime import datetime

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
    
    # 1. PERINTAH REKAP ORDER DENGAN FILTER DINAMIS (Pemicu: !rekap)
    if message.lower().startswith("!rekap"):
        try:
            # Ambil kriteria filter (teks setelah kata !rekap)
            filter_prompt = message[6:].strip()
            
            # Tarik data dari Google Sheets
            res = requests.get(GOOGLE_SHEETS_URL, timeout=10)
            orders_data = res.json()
                
            if not orders_data or str(orders_data).strip() == "[]" or not isinstance(orders_data, list):
                reply_to_wa("Belum ada data orderan jastip yang tercatat di Google Sheets.", sender, group_id)
                return jsonify({"status": "success"})
            
            # Susun seluruh data Sheets menjadi teks poin-poin dasar
            daftar_pesanan_teks = ""
            for i, order in enumerate(orders_data, 1):
                tgl = order.get('tanggal', '-')
                ev = order.get('event', 'Reguler')
                by = order.get('buyer', 'Tanpa Nama')
                pr = order.get('product', 'Tanpa Produk')
                qt = order.get('qty', 1)
                hg = order.get('harga', 0)
                tot = order.get('total', hg * qt)
                
                daftar_pesanan_teks += f"{i}. Tanggal: {tgl} | Event: {ev} | Pembeli: {by} | Produk: {pr} | Qty: {qt} | Harga: {hg} | Total: {tot}\n"
            
            # Tembak API Gemini pusat
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            
            # Modifikasi instruksi prompt agar Gemini melakukan filter cerdas jika diperintahkan
            prompt = (
                "Kamu adalah asisten jastip profesional dari 'Jastip Arzanka'. Tugasmu adalah membuat laporan rekapan pesanan yang rapi, "
                "cantik, dan menarik untuk grup WhatsApp berdasarkan data penjualan yang diberikan.\n\n"
                "⚠️ INSTRUKSI PENYARINGAN DATA (CRITICAL):\n"
                f"User meminta kriteria filter spesifik berikut: '{filter_prompt}'\n"
                "- Jika kriteria berisi 'hari ini', saring dan tampilkan HANYA pesanan yang memiliki tanggal hari ini (2 Juni 2026).\n"
                "- Jika kriteria berisi nama event tertentu (misal: 'event ihls'), saring dan tampilkan HANYA pesanan dari event tersebut.\n"
                "- Jika kriteria berisi nama buyer tertentu (misal: 'buyer ibun'), saring dan tampilkan HANYA pesanan milik buyer tersebut.\n"
                "- Jika kriteria KOSONG, tampilkan rekap semua data tanpa terkecuali.\n"
                "- Jika data setelah disaring ternyata kosong/tidak ditemukan yang cocok, balas saja dengan kalimat: 'Maaf, data rekapan dengan kriteria tersebut tidak ditemukan.'\n\n"
                "Aturan Tampilan (Jika data ditemukan):\n"
                "1. Kelompokkan pesanan dengan rapi dan gunakan emoji estetik.\n"
                "2. Tuliskan detail pembeli (cetak tebal), produk, qty, dan total harga apa adanya dari data.\n"
                "3. Gunakan gaya bahasa online shop yang ramah dan gunakan tanda bintang (*) untuk cetak tebal.\n\n"
                f"Data Penjualan Mentah:\n{daftar_pesanan_teks}"
            )
            
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            gemini_res = requests.post(gemini_url, headers=headers, json=payload, timeout=15)
            gemini_output = gemini_res.json()
            
            if 'candidates' in gemini_output and gemini_output['candidates']:
                text_response = gemini_output['candidates'][0]['content']['parts'][0]['text']
                reply_to_wa(text_response, sender, group_id)
            else:
                # Fallback teks jika API Gemini sibuk
                fallback_msg = f"*REKAP PESANAN JASTIP ARZANKA*\n(Filter: {filter_prompt if filter_prompt else 'Semua'})\n\n" + daftar_pesanan_teks
                reply_to_wa(fallback_msg, sender, group_id)
            
        except Exception as e:
            reply_to_wa(f"Gagal mengambil data rekapan dari sistem. (Detail: {str(e)[:50]})", sender, group_id)
            
    # 2. PERINTAH MASUKKAN ORDER MULTI-BARIS (Pemicu: !order)
    elif message.lower().startswith("!order"):
        try:
            baris_pesanan = message.split('\n')
            sukses_dicatat = []
            gagal_dicatat = 0
            
            for index, baris in enumerate(baris_pesanan):
                text_bersih = baris.strip()
                if not text_bersih: continue
                if index == 0 and text_bersih.lower() == "!order": continue
                if index == 0 and text_bersih.lower().startswith("!order "):
                    text_bersih = text_bersih[6:].strip()
                
                bagian = [b.strip() for b in text_bersih.split('-')]
                
                if len(bagian) >= 4:
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
                    sukses_dicatat.append(f"- {buyer_name} ({product_name} x{qty_clean})")
                else:
                    if text_bersih.lower() != "!order":
                        gagal_dicatat += 1

            if sukses_dicatat:
                msg_konfirmasi = "✅ *Berhasil Mencatat Pesanan Massal:*\n" + "\n".join(sukses_dicatat)
                if gagal_dicatat > 0:
                    msg_konfirmasi += f"\n\n⚠️ *Catatan:* Ada {gagal_dicatat} baris pesanan yang gagal tercatat."
                reply_to_wa(msg_konfirmasi, sender, group_id)
            else:
                raise ValueError("Tidak ada baris valid")
                
        except Exception as e:
            reply_to_wa("Format salah! Gunakan format praktis per baris:\n!order\nNama Pembeli - Nama Produk - Jumlah - Harga", sender, group_id)

    return jsonify({"status": "success"})

def reply_to_wa(text, sender, group_id):
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    target = group_id if group_id else sender
    payload = {"target": target, "message": text}
    requests.post(url, headers=headers, data=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
