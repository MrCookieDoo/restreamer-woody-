# Restreamer Woody installeren

Woody is de bestaande Restreamer 2.12-interface (UI 1.14.0) en Core 16.16.0,
uitgebreid met een regieservice en optionele chatbediening. Je hebt Linux x86-64,
Docker en Docker Compose v2 nodig. Reserveer circa 20 GB vrije schijfruimte voor builds, images en terugzetten. Een browser volstaat voor de bediening; OBS is
niet nodig. De eerste build downloadt de bestaande UI en de mediabibliotheken.

## Nieuwe proefinstallatie

```sh
git clone -b feat/woody-studio https://github.com/MrCookieDoo/restreamer-woody-.git
cd restreamer-woody-
python3 scripts/setup.py
docker compose up -d --build
```

Open `http://SERVER-IP:8080/ui/`. De gebruiker is `admin`; lees het gegenereerde
wachtwoord in je lokale `.env`. Die bevat ook de afzonderlijke Core-, encryptie-
en bot-sleutels. Bewaar een veilige back-up; verlies van de encryptiesleutel maakt
opgeslagen camerabronnen onleesbaar. Het script overschrijft een bestaande `.env`
niet. Bewaar `.env` niet in Git en deel het bestand niet in chat.

1. Voeg camera’s toe via de bestaande Restreamer-camerawizard. Gebruik bij Reolink
   en Axis een ondersteunde RTSP-netwerkbron in pull-modus, bij voorkeur H.264 op
   maximaal 1080p met camera-audio. De mixer ondersteunt ook H.265-decodering via
   de aanwezige libav-plugin. Model- en firmwareondersteuning verschilt, vooral
   bij batterijcamera’s; controleer dat continu RTSP daadwerkelijk beschikbaar is.
2. Open **Studio** met de knop op de Restreamer-hoofdpagina of via **Studio / Regie** in het hoofdmenu. Kies bestaande kanalen en geef ze
   een korte alias, bijvoorbeeld `tuin` of `vijver`. Bronadressen en wachtwoorden
   worden server-side uit Core gelezen en versleuteld opgeslagen.
3. Klik **Hoofdkanaal gereedmaken**. Dit maakt een normaal Restreamer-kanaal
   `Woody Hoofdstream`, plus de bestaande webplayer. Het vervangt geen kanalen.
4. Wacht tot camera’s online zijn en kies **1 groot + 5 klein**. De uitgang start
   veilig met een algemeen wachtbeeld. Het grote beeld levert het geluid.
5. Open **Open kanaal en publicaties** en voeg Twitch, YouTube of andere bestaande
   Restreamer-publicaties toe. De RTMP-streamkey blijft in de bestaande UI/Core.

De camera’s blijven ook hun bestaande losse streams verzorgen. Woody opent een
extra ontvangstverbinding per geselecteerde camera. Controleer de limieten van de
camera en beschikbare bandbreedte. Wijzig je een bron in Restreamer, kies in Regie bij die camera **Bewerk → Bron vernieuwen** om het gewijzigde bronadres over te nemen. Dit werkt ook bij 13 geregistreerde camera’s en behoudt blokkeringen.

## Testen zonder camera’s

Gebruik een afzonderlijke proefinstallatie. Voer `python3 scripts/setup.py --demo`
uit bij een nieuwe `.env`; voor een bestaande proefconfiguratie kun je
`WOODY_ALLOW_TEST_SOURCES=1` instellen. Start de containers daarna opnieuw.

```sh
python3 scripts/demo.py
```

Dit logt met de lokale instellingen in en registreert 13 kunstmatige camera’s,
zonder apparaten te benaderen. De regie blijft op wachtbeeld totdat je haar zelf
activeert. In deze modus blijven de cameraknoppen, echte videomixer en audio actief.
Zet de demo-optie voor de echte installatie weer op `0` en verwijder de democamera’s.

## Bestaande installatie meenemen

Stop de oude container en maak eerst een back-up van `/core/config` en `/core/data`.
Gebruik niet twee Core-instanties tegelijkertijd met dezelfde configuratiedirectory.
Stel daarna bijvoorbeeld in `.env` in:

```dotenv
WOODY_CORE_CONFIG=/opt/restreamer/config
WOODY_CORE_DATA=/opt/restreamer/data
```

De bestaande UI, kanalen, publicaties en volumes worden hergebruikt. Compose stelt
de Core-login en JWT-sleutel vanuit `.env` in; bestaande browsersessies moeten dus
opnieuw inloggen. Studio gebruikt dezelfde gebruikersnaam, hetzelfde wachtwoord en dezelfde JWT-secret: Core 16.16 leidt zijn ondertekeningssleutel af uit de combinatie van die drie waarden. Houd ze daarom in beide services gelijk. Bewaar de oorspronkelijke instellingen voor terugzetten.

Staat bij de bestaande RTMP-server een token ingesteld, zet dan ook de interne
uitgang in `.env`, met hetzelfde token en app-pad:

```dotenv
WOODY_OUTPUT_URI=rtmp://core:1935/live/woody-program?token=JOUW_TOKEN
```

De standaardinstallatie gebruikt intern poort 1935 en app `/live`. Core en Studio
zijn uitsluitend via het interne Docker-netwerk bereikbaar; HTTP gaat via Caddy.
Configureer voor bediening buiten het eigen netwerk HTTPS op de bestaande reverse
proxy. Laat RTMP/API-poorten niet zonder noodzaak publiek doorsturen.

## Hardware en beeldkwaliteit

De startinstelling is 1920×1080, 25 fps, H.264 op ongeveer 6 Mbit/s en AAC op
128 kbit/s, 48 kHz stereo. De compositie normaliseert iedere camerabron naar
1280×720 en bewaart de beeldverhouding. Alle 13 bronnen kunnen warm blijven voor
snelle wissels; hoge bronresoluties moeten nog steeds worden gedecodeerd. Kies
daarom bij de camera een passend profiel in plaats van 13 volledige 4K-bronnen.

Startadvies: moderne CPU met 8–12 kernen, 32 GB RAM, SSD en gigabitnetwerk. Dit is
geen bewezen minimum. De standaardencoder `x264` werkt zonder GPU. De engine heeft
selecties `vaapi` en `nvenc`, maar deze vereisen passende GStreamer-plugins,
drivers en toegankelijke apparaten in de container; ze moeten op de doelhardware
worden getest. Wijzig `WOODY_ENCODER` pas nadat `gst-inspect-1.0 vah264enc` of
`gst-inspect-1.0 nvh264enc` in die container slaagt. Automatische GPU-decodering is
eveneens afhankelijk van beschikbare plugins en hun rangschikking.

## Back-up, update en terugzetten

Bewaar `.env`, de Core-volumes en `studio-data` samen. Stop voor een eenvoudige
consistente bestandsback-up de stack met `docker compose stop`; de Studio-database
gebruikt SQLite met WAL. Kopieer bij een draaiende database niet uitsluitend het
`.sqlite`-bestand. Bot OAuth-tokens staan afzonderlijk in `bot-data`.

Na een code-update: `docker compose build && docker compose up -d`. Voor
terugzetten: stop de stack, herstel de bij elkaar horende volumes en `.env` en start
de eerder gebruikte images. Camerablokkeringen zijn blijvend opgeslagen; een
reconnect of herstart heft ze niet op. Een server-, internet- of mixercrash kan
wel herverbinden vereisen; deze versie bevat geen tweede overnameserver.

## Checks voor ingebruikname

- Controleer alle 13 echte camera’s, hun audio en de bestaande Axis-uitzendingen.
- Test verbergen, reconnect, een defecte bron en het algemene wachtbeeld.
- Doe een proefuitzending op Twitch en YouTube en een duurtest van 24 uur.
- Meet de platformvertraging afzonderlijk: de noodknop wist geen reeds verzonden
  of bij het platform gebufferde beelden.
- Zie [TESTING.md](TESTING.md) voor lokale tests en de duurtesthelper en
  [CHATBOT.md](CHATBOT.md) voor accountkoppeling.
