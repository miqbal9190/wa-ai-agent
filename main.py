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
    
    # 1. PERINTAH REKAP ORDER DENGAN FILTER DINAMIS (Pemicu: !rekap)
    if message.lower().startswith("!rekap"):
        try:
            # Mengambil text setelah kata !rekap (misal: "event ihls" atau "buyer ibun")
            filter_prompt = message[6:].strip()
            
            res = requests.get(GOOGLE_SHEETS_URL, timeout=10)
            orders_data = res.json()
                
            if not orders_data or str(orders_data).strip() == "[]" or not isinstance(orders_data, list):
                reply_to_wa("Belum ada data orderan jastip yang tercatat di Google Sheets.", sender, group_id)
                return jsonify({"status": "success"})
            
            # Merakit data poin-poin murni untuk disetor ke Gemini
            daftar_pesanan_teks = ""
            for i, order in enumerate(orders_data, 1):
                ev = order.get('event', 'Reguler')
                by = order.get('buyer', 'Tanpa Nama')
                pr = order.get('product', 'Tanpa Produk')
                qt = order.get('qty', 1)
                hg = order.get('harga', 0)
                tot = order.get('total', hg * qt)
                
                daftar_pesanan_teks += f"{i}. Event: {ev} | Pembeli: {by} | Produk: {pr} | Qty: {qt} | Harga: {hg} | Total: {tot}\n"
            
            # Alamat API Gemini 1.5 Flash Resmi
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            
            prompt = (
                "Kamu adalah asisten jastip profesional dari 'Jastip Arzanka'. Tugasmu adalah menyusun dan merapikan "
                "data teks penjualan di bawah ini menjadi format laporan WhatsApp grup yang sangat cantik, estetik, dan rapi.\n\n"
                "⚠️ INSTRUKSI PENYARINGAN DATA (CRITICAL):\n"
                f"User meminta kriteria filter spesifik berikut: '{filter_prompt}'\n"
                "- Jika kriteria berisi nama event tertentu (misal: 'event ihls'), saring dan tampilkan HANYA pesanan dari event tersebut.\n"
                "- Jika kriteria berisi nama buyer tertentu (misal: 'buyer ibun'), saring dan tampilkan HANYA pesanan milik buyer tersebut.\n"
                "- Jika kriteria berisi keterangan waktu tertentu (misal: 'hari ini', 'kemarin', atau 'Tanggal 1 sampai tanggal 5'), saring dan tampilkan HANYA pesanan pada keterangan waktu tersebut.\n"
                "- Jika kriteria KOSONG, tampilkan rekap semua data tanpa terkecuali.\n"
                "- Jika data setelah disaring ternyata kosong/tidak ditemukan yang cocok, balas saja dengan kalimat: 'Maaf, data rekapan dengan kriteria tersebut tidak ditemukan.'\n\n"
                "Aturan Tampilan (Jika data ditemukan):\n"
                "1. Kelompokkan pesanan dengan rapi berdasarkan nama Event. Gunakan emoji penanda yang menarik.\n"
                "2. Tuliskan detail nama pembeli (cetak tebal), nama produk, qty, dan nilai TOTAL yang tertera di data (JANGAN mengubah atau menghitung ulang angka TOTAL yang diberikan, tulis apa adanya saja).\n"
                "3. JANGAN PERNAH menampilkan total akumulasi omset keseluruhan di bagian bawah (Sembunyikan privasi omset total).\n"
                "4. Gunakan gaya bahasa online shop yang ramah dan gunakan tanda bintang (*) untuk cetak tebal.\n\n"
                f"Data Penjualan Mentah:\n{daftar_pesanan_teks}"
            )
            
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            gemini_res = requests.post(gemini_url, headers=headers, json=payload, timeout=15)
            gemini_output = gemini_res.json()
            
            if 'candidates' in gemini_output and gemini_output['candidates']:
                text_response = gemini_output['candidates'][0]['content']['parts'][0]['text']
                reply_to_wa(text_response, sender, group_id)
            else:
                # FITUR SUNTIKAN PELACAK EROR JIKALAU GEMINI MENOLAK / API KEY BERMASALAH
                error_details = "Eror tidak dikenal atau respons kosong dari Google"
                if 'error' in gemini_output:
                    error_details = gemini_output['error'].get('message', str(gemini_output['error']))
                
                fallback_msg = (
                    f"⚠️ *Gemini API Error:* {error_details}\n\n"
                    f"*REKAP STANDAR (FALLBACK):*\n"
                    f"(Filter: {filter_prompt if filter_prompt else 'Semua'})\n\n"
                    f"{daftar_pesanan_teks}"
                )
                reply_to_wa(fallback_msg, sender, group_id)
            
        except Exception as e:
            reply_to_wa(f"Gagal mengambil data rekapan dari sistem. (Detail: {str(e)[:50]})", sender, group_id)
            
    # 2. PERINTAH MASUKKAN ORDER MULTI-BARIS & TUNGGAL (Pemicu: !order)
    elif message.lower().startswith("!order"):
        try:
            baris_pesanan = message.split('\n')
            
            paket_massal = []
            sukses_dicatat = []
            gagal_dicatat = 0
            
            for index, baris in enumerate(baris_pesanan):
                text_clean = baris.strip()
                if not text_clean: continue
                
                if text_clean.lower() == "!order": continue
                if text_clean.lower().startswith("!order "):
                    text_clean = text_clean[6:].strip()
                    if not text_clean: continue
                
                bagian = [b.strip() for b in text_clean.split('-')]
                
                if len(bagian) >= 4:
                    buyer_name = bagian[0]
                    product_name = bagian[1]
                    qty_clean = "".join(filter(str.isdigit, bagian[2]))
                    harga_clean = "".join(filter(str.isdigit, bagian[3]))
                    
                    if len(bagian) >= 5 and bagian[4]:
                        event_name = bagian[4]
                    else:
                        event_name = "Reguler"
                    
                    paket_massal.append({
                        "event": event_name,
                        "buyer": buyer_name,
                        "product": product_name,
                        "qty": int(qty_clean),
                        "harga": int(harga_clean)
                    })
                    sukses_dicatat.append(f"- {buyer_name} ({product_name} x{qty_clean})")
                else:
                    gagal_dicatat += 1

            if paket_massal:
                payload_sheets = {"data_massal": paket_massal}
                requests.post(GOOGLE_SHEETS_URL, json=payload_sheets, timeout=15)
                
                msg_konfirmasi = "✅ *Berhasil Mencatat Pesanan:*\n" + "\n".join(sukses_dicatat)
                if gagal_dicatat > 0:
                    msg_konfirmasi += f"\n\n⚠️ *Catatan:* Ada {gagal_dicatat} baris pesanan yang gagal tercatat."
                reply_to_wa(msg_konfirmasi, sender, group_id)
            else:
                raise ValueError("Tidak ada baris valid")
                
        except Exception as e:
            reply_to_wa(
                "❌ *Format Gagal Disimpan!*\n\n"
                "Pastikan format pengetikan per baris Anda sudah benar seperti ini:\n\n"
                "👉 *!order*\n"
                "Nama Pembeli - Nama Produk - Jumlah Qty - Harga Jual - Nama Event\n\n"
                "Contoh:\n"
                "!order\n"
                "Bu Ani - Gamis Silk - 2 - 150000 - Live Bandung\n"
                "ibun - Gelas Cantik - 3 - 1000", 
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
