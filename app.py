from flask import Flask, render_template, request
from geopy.distance import geodesic
import requests

app = Flask(__name__)

YANDEX_API_KEY = "ea220df4-ebf3-4597-988c-dd7212f20143"


def yandex_ile_ilce_ve_koordinat_bul(adres):
    arama_metni = f"Eskişehir, {adres}"
    guvenli_metin = requests.utils.quote(arama_metni)
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={YANDEX_API_KEY}&geocode={guvenli_metin}&format=json"

    try:
        response = requests.get(url, timeout=5)
        veri = response.json()

        adres_havuzu = veri['response']['GeoObjectCollection']['featureMember']

        if len(adres_havuzu) > 0:
            geo_object = adres_havuzu[0]['GeoObject']
            tam_adres_metni = geo_object['metaDataProperty']['GeocoderMetaData']['text'].lower()

            koordinat_str = geo_object['Point']['pos']
            lon, lat = map(float, koordinat_str.split())

            # 1. KONTROL: Türkçe ve İngilizce karakter uyuşmazlığını önlemek için alternatifleri ekledik
            ilce_okey = (
                    "odunpazarı" in tam_adres_metni or
                    "odunpazari" in tam_adres_metni or
                    "tepebaşı" in tam_adres_metni or
                    "tepebasi" in tam_adres_metni or
                    "eskişehir" in tam_adres_metni or
                    "eskisehir" in tam_adres_metni
            )

            # 2. KONTROL (GARANTİ): Koordinat Eskişehir merkez sınırları içinde mi?
            # (Enlem 39.6 ile 39.9, Boylam 30.3 ile 30.7 arasındaysa Eskişehir merkezdedir)
            merkezde_mi = (39.6 <= lat <= 39.9) and (30.3 <= lon <= 30.7)

            if ilce_okey or merkezde_mi:
                return lat, lon
            else:
                print(f"⚠️ Eskişehir Dışı Konum Engellendi: {adres} -> Dönen Adres: {tam_adres_metni}")
                return None
        return None
    except Exception as e:
        print(f"Yandex aranırken teknik hata oluştu: {e}")
        return None


# Çoklu duraklar için Yandex Navigasyon Deep Link üreten fonksiyon
def yandex_coklu_durak_linki_uret(rota_listesi):
    if len(rota_listesi) < 2:
        return ""

    # Yandex Haritalar'ın tarayıcı tabanlı çoklu rota formatı (Kesin sonuç verir)
    # Format: https://yandex.com/maps/?rtext=lat1,lon1~lat2,lon2~lat3,lon3
    koordinat_zinciri = "~".join([f"{k['lat']},{k['lon']}" for k in rota_listesi])
    url = f"https://yandex.com/maps/?rtext={koordinat_zinciri}&rtt=auto"
    return url


def google_maps_linki_uret(rota_listesi):
    duraklar = "/".join([f"{k['lat']},{k['lon']}" for k in rota_listesi])
    return f"https://www.google.com/maps/dir/{duraklar}"


@app.route('/')
def ana_sayfa():
    return render_template('index.html')


@app.route('/rota-hesapla', methods=['POST'])
def rota_hesapla():
    gelen_metin = request.form.get("adresler")
    adres_listesi = [satir.strip() for satir in gelen_metin.splitlines() if satir.strip()]

    if not adres_listesi:
        return "Baba adres girmedin!!"

    koordinatlar = []
    bulunamayan_adresler = []

    for adres in adres_listesi:
        konum = yandex_ile_ilce_ve_koordinat_bul(adres)
        if konum:
            koordinatlar.append({"adres": adres, "lat": konum[0], "lon": konum[1]})
        else:
            # Artık buraya düşenler hem bulunamayanlar hem de ilçe sınırına uymayanlar
            bulunamayan_adresler.append(adres)

    toplam_girilen = len(adres_listesi)
    toplam_bulunan = len(koordinatlar)
    toplam_bulunamayan = len(bulunamayan_adresler)

    if toplam_bulunan < 2:
        return render_template('sonuc.html', hata_var=True, toplam_girilen=toplam_girilen,
                               toplam_bulunan=toplam_bulunan, toplam_bulunamayan=toplam_bulunamayan,
                               bulunamayanlar=bulunamayan_adresler)

        # EN YAKIN KOMŞU ALGORİTMASI (Burası sadece en az 2 adres varsa çalışacak)
    sirali_rota = [koordinatlar[0]]
    havuz = koordinatlar[1:]

    while havuz:
        son_konum = sirali_rota[-1]
        en_yakin = min(havuz, key=lambda x: geodesic((son_konum["lat"], son_konum["lon"]), (x["lat"], x["lon"])).meters)
        sirali_rota.append(en_yakin)
        havuz.remove(en_yakin)

    # TERS ROTA HESAPLAMA
    ters_sirali_rota = sirali_rota[::-1]

    # LİNKLERİ ÜRETMEK (Bunlar da içeri alındı, artık çökme ihtimali SIFIR)
    google_url_duz = google_maps_linki_uret(sirali_rota)
    yandex_url_duz = yandex_coklu_durak_linki_uret(sirali_rota)

    google_url_ters = google_maps_linki_uret(ters_sirali_rota)
    yandex_url_ters = yandex_coklu_durak_linki_uret(ters_sirali_rota)

    return render_template('sonuc.html',
                           hata_var=False,
                           rota=sirali_rota,
                           rota_ters=ters_sirali_rota,
                           bulunamayanlar=bulunamayan_adresler,
                           toplam_girilen=toplam_girilen,
                           toplam_bulunan=toplam_bulunan,
                           toplam_bulunamayan=toplam_bulunamayan,
                           google_link_duz=google_url_duz,
                           yandex_link_duz=yandex_url_duz,
                           google_link_ters=google_url_ters,
                           yandex_link_ters=yandex_url_ters)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)