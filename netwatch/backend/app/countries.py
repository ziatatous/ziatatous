"""ISO2 -> (continent, region, english name, lat, lon). Coordinates are approximate centroids."""
_RAW = """
FR EU West-Europe France 46.6 2.4|ES EU South-Europe Spain 40.2 -3.6|DE EU West-Europe Germany 51.1 10.4
IT EU South-Europe Italy 42.8 12.5|PT EU South-Europe Portugal 39.6 -8.0|GB EU West-Europe United-Kingdom 54.0 -2.5
IE EU West-Europe Ireland 53.2 -8.1|NL EU West-Europe Netherlands 52.2 5.6|BE EU West-Europe Belgium 50.6 4.7
LU EU West-Europe Luxembourg 49.8 6.1|CH EU West-Europe Switzerland 46.8 8.2|AT EU West-Europe Austria 47.6 14.1
SE EU North-Europe Sweden 62.0 15.0|NO EU North-Europe Norway 61.0 9.0|DK EU North-Europe Denmark 56.0 9.5
FI EU North-Europe Finland 64.0 26.0|IS EU North-Europe Iceland 64.9 -18.6|PL EU East-Europe Poland 52.1 19.4
CZ EU East-Europe Czechia 49.8 15.5|SK EU East-Europe Slovakia 48.7 19.5|HU EU East-Europe Hungary 47.2 19.4
RO EU East-Europe Romania 45.9 25.0|BG EU East-Europe Bulgaria 42.7 25.5|GR EU South-Europe Greece 39.0 22.0
HR EU South-Europe Croatia 45.1 15.5|SI EU South-Europe Slovenia 46.1 14.8|RS EU South-Europe Serbia 44.0 21.0
BA EU South-Europe Bosnia-Herzegovina 44.2 17.8|AL EU South-Europe Albania 41.1 20.0|MK EU South-Europe North-Macedonia 41.6 21.7
ME EU South-Europe Montenegro 42.7 19.3|XK EU South-Europe Kosovo 42.6 20.9|EE EU North-Europe Estonia 58.6 25.0
LV EU North-Europe Latvia 56.9 24.6|LT EU North-Europe Lithuania 55.2 23.9|UA EU East-Europe Ukraine 49.0 31.4
BY EU East-Europe Belarus 53.7 27.9|MD EU East-Europe Moldova 47.2 28.5|RU EU East-Europe Russia 61.5 99.0
MT EU South-Europe Malta 35.9 14.4|CY EU South-Europe Cyprus 35.1 33.4|GE AS Caucasus Georgia 42.3 43.4
AM AS Caucasus Armenia 40.1 45.0|AZ AS Caucasus Azerbaijan 40.1 47.6|TR AS West-Asia Turkey 39.0 35.2
IL AS West-Asia Israel 31.5 34.9|PS AS West-Asia Palestine 31.9 35.2|LB AS West-Asia Lebanon 33.9 35.9
SY AS West-Asia Syria 35.0 38.5|JO AS West-Asia Jordan 31.2 36.5|IQ AS West-Asia Iraq 33.0 43.7
IR AS West-Asia Iran 32.4 53.7|SA AS West-Asia Saudi-Arabia 24.0 45.0|AE AS West-Asia United-Arab-Emirates 23.4 53.8
QA AS West-Asia Qatar 25.3 51.2|KW AS West-Asia Kuwait 29.3 47.5|BH AS West-Asia Bahrain 26.0 50.5
OM AS West-Asia Oman 21.5 55.9|YE AS West-Asia Yemen 15.6 48.5|AF AS Central-Asia Afghanistan 33.9 67.7
PK AS South-Asia Pakistan 30.4 69.3|IN AS South-Asia India 21.0 78.0|BD AS South-Asia Bangladesh 23.7 90.4
LK AS South-Asia Sri-Lanka 7.9 80.8|NP AS South-Asia Nepal 28.4 84.1|BT AS South-Asia Bhutan 27.5 90.4
MV AS South-Asia Maldives 3.2 73.2|KZ AS Central-Asia Kazakhstan 48.0 66.9|UZ AS Central-Asia Uzbekistan 41.4 64.6
KG AS Central-Asia Kyrgyzstan 41.2 74.8|TJ AS Central-Asia Tajikistan 38.9 71.3|TM AS Central-Asia Turkmenistan 38.9 59.6
MN AS East-Asia Mongolia 46.9 103.8|CN AS East-Asia China 35.0 103.0|HK AS East-Asia Hong-Kong 22.3 114.2
TW AS East-Asia Taiwan 23.7 121.0|JP AS East-Asia Japan 36.2 138.2|KR AS East-Asia South-Korea 36.5 127.9
KP AS East-Asia North-Korea 40.3 127.5|VN AS Southeast-Asia Vietnam 14.1 108.3|TH AS Southeast-Asia Thailand 15.8 101.0
MM AS Southeast-Asia Myanmar 21.9 95.9|LA AS Southeast-Asia Laos 19.9 102.5|KH AS Southeast-Asia Cambodia 12.6 104.9
MY AS Southeast-Asia Malaysia 4.2 102.0|SG AS Southeast-Asia Singapore 1.35 103.8|ID AS Southeast-Asia Indonesia -2.5 118.0
PH AS Southeast-Asia Philippines 12.9 121.8|TL AS Southeast-Asia Timor-Leste -8.8 125.7|BN AS Southeast-Asia Brunei 4.5 114.7
AU OC Oceania Australia -25.3 133.8|NZ OC Oceania New-Zealand -41.0 174.0|PG OC Oceania Papua-New-Guinea -6.3 143.9
FJ OC Oceania Fiji -17.7 178.1|EG AF North-Africa Egypt 26.8 30.8|LY AF North-Africa Libya 26.3 17.2
TN AF North-Africa Tunisia 33.9 9.5|DZ AF North-Africa Algeria 28.0 1.7|MA AF North-Africa Morocco 31.8 -7.1
MR AF West-Africa Mauritania 21.0 -10.9|SD AF North-Africa Sudan 12.9 30.2|SS AF East-Africa South-Sudan 7.0 30.0
ET AF East-Africa Ethiopia 9.1 40.5|ER AF East-Africa Eritrea 15.2 39.8|DJ AF East-Africa Djibouti 11.8 42.6
SO AF East-Africa Somalia 5.2 46.2|KE AF East-Africa Kenya 0.0 38.0|UG AF East-Africa Uganda 1.4 32.3
TZ AF East-Africa Tanzania -6.4 34.9|RW AF East-Africa Rwanda -1.9 29.9|BI AF East-Africa Burundi -3.4 29.9
CD AF Central-Africa DR-Congo -2.9 23.7|CG AF Central-Africa Congo -0.2 15.8|CM AF Central-Africa Cameroon 7.4 12.4
GA AF Central-Africa Gabon -0.8 11.6|TD AF Central-Africa Chad 15.5 18.7|CF AF Central-Africa Central-African-Republic 6.6 20.9
NG AF West-Africa Nigeria 9.1 8.7|GH AF West-Africa Ghana 7.9 -1.0|CI AF West-Africa Cote-d-Ivoire 7.5 -5.5
SN AF West-Africa Senegal 14.5 -14.5|ML AF West-Africa Mali 17.6 -4.0|BF AF West-Africa Burkina-Faso 12.2 -1.6
NE AF West-Africa Niger 17.6 8.1|GN AF West-Africa Guinea 9.9 -9.7|SL AF West-Africa Sierra-Leone 8.5 -11.8
LR AF West-Africa Liberia 6.4 -9.4|BJ AF West-Africa Benin 9.3 2.3|TG AF West-Africa Togo 8.6 0.8
AO AF Southern-Africa Angola -11.2 17.9|ZM AF Southern-Africa Zambia -13.1 27.8|ZW AF Southern-Africa Zimbabwe -19.0 29.2
MZ AF Southern-Africa Mozambique -18.7 35.5|MW AF Southern-Africa Malawi -13.3 34.3|BW AF Southern-Africa Botswana -22.3 24.7
NA AF Southern-Africa Namibia -22.6 17.1|ZA AF Southern-Africa South-Africa -30.6 22.9|MG AF East-Africa Madagascar -18.8 47.0
MU AF East-Africa Mauritius -20.3 57.6|US NA North-America United-States 39.8 -98.6|CA NA North-America Canada 56.1 -106.3
MX NA Central-America Mexico 23.6 -102.5|GT NA Central-America Guatemala 15.8 -90.2|HN NA Central-America Honduras 15.2 -86.2
SV NA Central-America El-Salvador 13.8 -88.9|NI NA Central-America Nicaragua 12.9 -85.2|CR NA Central-America Costa-Rica 9.7 -83.8
PA NA Central-America Panama 8.5 -80.8|CU NA Caribbean Cuba 21.5 -77.8|DO NA Caribbean Dominican-Republic 18.7 -70.2
HT NA Caribbean Haiti 19.0 -72.4|JM NA Caribbean Jamaica 18.1 -77.3|PR NA Caribbean Puerto-Rico 18.2 -66.5
CO SA South-America Colombia 4.6 -74.1|VE SA South-America Venezuela 6.4 -66.6|EC SA South-America Ecuador -1.8 -78.2
PE SA South-America Peru -9.2 -75.0|BO SA South-America Bolivia -16.3 -63.6|BR SA South-America Brazil -14.2 -51.9
PY SA South-America Paraguay -23.4 -58.4|UY SA South-America Uruguay -32.5 -55.8|AR SA South-America Argentina -38.4 -63.6
CL SA South-America Chile -35.7 -71.5|GY SA South-America Guyana 4.9 -58.9
"""

COUNTRIES: dict[str, dict] = {}
for _row in _RAW.replace("\n", "|").split("|"):
    _p = _row.split()
    if len(_p) == 6:
        COUNTRIES[_p[0]] = dict(code=_p[0], continent=_p[1], region=_p[2].replace("-", " "),
                                name=_p[3].replace("-", " "), lat=float(_p[4]), lon=float(_p[5]))

# GDELT / FIPS-ish and ISO3 helpers are resolved at collection time through NAME_INDEX.
NAME_INDEX = {c["name"].lower(): k for k, c in COUNTRIES.items()}
NAME_INDEX.update({"usa": "US", "united states of america": "US", "uk": "GB", "britain": "GB", "russian federation": "RU",
                   "korea, south": "KR", "south korea": "KR", "korea": "KR", "iran, islamic republic of": "IR",
                   "turkiye": "TR", "czech republic": "CZ", "ivory coast": "CI", "democratic republic of the congo": "CD",
                   "congo, the democratic republic of the": "CD", "viet nam": "VN", "syrian arab republic": "SY"})


def continent_of(code: str | None) -> str | None:
    c = COUNTRIES.get((code or "").upper())
    return c["continent"] if c else None


def lookup_name(name: str | None) -> str | None:
    return NAME_INDEX.get((name or "").strip().lower())
