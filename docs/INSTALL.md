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

Het livebeeld staat bovenaan bij **Woody Hoofdstream**. De preview wacht totdat
er een afspeelbare HLS-playlist is en probeert opnieuw na een afspeelfout of
stilgevallen afspeelklok. Bij **Camera kiezen · momentopnamen** eronder staan
foto's voor de bediening; deze vernieuwen elke vijf seconden.
**Encoder: … / 25 fps** toont de gemeten H.264-uitgang naast de ingestelde
beeldsnelheid. Een groene mixerstatus alleen bewijst geen vloeiende aflevering.

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

## Updates op Windows

Na de eenmalige installatie hoef je geen setupscript meer uit te voeren. Open
PowerShell in je bestaande Woody-projectmap en voer uit:

```powershell
.\update.cmd
```

Bij de eerste keer moet je dit nieuwe bestand nog ophalen:

```powershell
git pull --ff-only origin feat/woody-studio
.\update.cmd
```

De updater herkent het bestaande Docker-project aan de Studio-container en de
projectmap. Hij bewaart `.env`, poort en volumes, haalt de huidige branch met
`--ff-only` op, bouwt eerst alle benodigde images en werkt pas daarna het
bestaande project bij. Bij een mislukte build blijven de oude containers draaien.
Er wordt geen `down` uitgevoerd. Alleen een reeds draaiende chatbot wordt als
onderdeel van het actieve profiel bijgewerkt.

Meerdere projecten uit dezelfde map? Kies expliciet bijvoorbeeld
`.\update.cmd -Project woody-test`. De updater weigert een project dat niet bij
deze Woody-map hoort. Lokale wijzigingen in bijgehouden bronbestanden moeten eerst
worden bewaard; een aangepaste `.env` is toegestaan.

Woody-containers kunnen tijdens het vervangen kort herstarten. Een aparte
standaard-Restreamer valt buiten deze update. De eerste build met de nieuwe cache
kost nog tijd; latere wijzigingen hergebruiken de UI-, Python- en botpakketten
zolang hun dependencybestanden gelijk blijven. De images worden momenteel lokaal
gebouwd; dit is geen download van vooraf gepubliceerde images.

## Eigen wachtbeeld per camera

Open **Studio → Camera’s → Bewerk** bij de gewenste camera en kies
**Afbeelding uploaden**. PNG, JPG en stilstaande WebP worden ondersteund,
maximaal 4 MB en 16 megapixels. Het beeld wordt binnen 16:9 passend gemaakt;
extra ruimte wordt zwart. De afbeelding blijft in het Studio-volume bewaard.

Met **Wachtbeeld tonen** wordt die camera in de hoofdstream vervangen door haar
eigen afbeelding en gedempt. **Camera weer tonen** geeft het livebeeld vrij
zodra de bron online is. De bestaande noodknop **Verbergen + dempen** gebruikt
hetzelfde eigen beeld. De camera-ontvangst en losse Restreamer-uitzending worden
hierbij niet gestopt.

Bij bronuitval verschijnt de afbeelding automatisch, zolang de camera aan het
kader is toegewezen. Zet de indeling met **Vastzetten** vast als je wilt voorkomen
dat de automatische ronde het kader later aan een andere camera toewijst.
**Alles naar wachtbeeld** heeft voorrang en blijft het algemene wachtbeeld tonen.
Met **Afbeelding verwijderen** wordt voor deze camera weer het standaard zwarte
wachtbeeld gebruikt; dit heft een bestaande camerablokkering niet op.

## NVR-containers die de netwerkruimte van de oude Woody delen

Bij `woody-rtmp-channel0` met netwerkmodus `container:<Woody-id>` zit
`http://127.0.0.1:18550/channel0.ts` binnen de oude Woody-netwerkruimte. Hetzelfde
geldt voor poorten 18551-18565. Die poorten zijn niet op Windows gepubliceerd.
In de nieuwe Core- en Studio-containers betekent `127.0.0.1` hun eigen container.

Gebruik voor de parallelle proef de **HLS-uitgangen van de bestaande Woody**.
Laat de oude NVR-bronnen, containers en publicaties daarbij staan. De oude Core
blijft de NVR-bron lezen; de nieuwe installatie leest zijn meervoudig bruikbare
HLS-uitgang op de al gepubliceerde poort 8080.

Vanuit PowerShell in de nieuwe projectmap:

```powershell
.\nvr-sources.cmd
```

Deze uitleeshulp leest via Docker `cat /core/config/db.json` binnen container
`Woody`. Hij drukt geen ruwe database of bronwachtwoorden af. Per herkend NVR-
kanaal leest hij de daadwerkelijke HLS-uitvoerconfiguratie en controleert hij of
de playlist bereikbaar is. Alleen bij een geldige HLS-reactie verschijnt een
bronadres, bijvoorbeeld:

```text
http://host.docker.internal:8080/memfs/<bestaand-kanaal-id>.m3u8
```

Bij HLS op schijf ontbreekt `/memfs/`; de hulp volgt de bestaande
uitvoerconfiguratie. Een ontbrekende playlist (HTTP 404) wordt gemeld en niet als
bruikbaar bronadres aangeboden. Gebruik een kanaal dat in de oude Woody beeld
geeft. `host.docker.internal` is het hostadres voor Docker Desktop. Het is een
bronadres voor de containers; de browser blijft voor de nieuwe interface
`http://localhost:8082/ui/` gebruiken als poort 8082 in `.env` staat.

1. Neem het adres uit de lijst over als netwerkbron in het betreffende kanaal van
   de **nieuwe** Restreamer. Voor een eerste proef is één kanaal voldoende.
2. Controleer of dat kanaal in de nieuwe gewone weergave beeld en geluid geeft.
3. Is het kanaal al in Studio opgenomen? Kies **Bewerk → Bron vernieuwen** om het
   gewijzigde bronadres over te nemen. Anders voeg je het toe aan de regie.

Een andere containernaam of gepubliceerde oude HTTP-poort kan expliciet:

```powershell
.\nvr-sources.cmd -Container Woody -BaseUrl http://host.docker.internal:8080
```

Een aangepaste Core-datadirectory kan met `-DatabasePath /pad/naar/db.json`.
De beschikbaarheidscontrole gebruikt op Windows `127.0.0.1` voor het hostadres;
het getoonde bronadres behoudt `host.docker.internal` voor de nieuwe containers.
Met `-NoCheck` kun je de geconfigureerde paden zonder controle laten zien,
bijvoorbeeld bij afgeschermde HLS-uitgangen. Deze worden als ongecontroleerd
gemarkeerd en kunnen dus nog een 404 of aanmeldfout geven.
Als de database niet kan worden gelezen, kun je ook de bestaande HLS-knop in de
oude Restreamer gebruiken: behoud kanaal-id en pad en gebruik voor deze
Docker Desktop-opstelling `host.docker.internal:8080` als host en poort.
Op een andere Linux-server gebruik je een bereikbaar serveradres; Docker Desktop-
DNS is daar niet automatisch aanwezig.

HLS brengt buffervertraging mee. De noodknop maskeert de nieuwe hoofdstream,
maar wist geen reeds verzonden of gebufferde beelden. De hulp maakt geen ontbrekende
oude HLS-kanalen aan en start geen gestopte NVR-containers. Het aanleveren van
16 bronadressen verandert de huidige Studio-limiet van 13 geregistreerde camera’s
niet.

## Hoofdstream laadt niet of Studio staat stil

Voer in de projectmap uit terwijl de proefinstallatie draait:

```powershell
git pull --ff-only
.\studio-diagnostics.cmd
```

Dit werkt ook met de al draaiende Studio-image; een build of herstart is voor
deze controle niet nodig. De standaardcontainer is `woody-test-studio-1`.
Gebruik bij een andere naam `-Container NAAM`.

Het rapport toont het aantal gekoppelde/online camera's, de mixerframecounter,
de ontvangststatus van het hoofdkanaal in Core en de beschikbaarheid van zijn
HLS-playlist. Na drie seconden worden de tellers opnieuw gelezen. Er worden
geen bronadressen, wachtwoorden, tokens, procesopdrachten of ruwe logs afgedrukt;
de controle wijzigt geen instellingen en stopt geen containers.

`program.exists: false` met HTTP 404 betekent dat het hoofdkanaal ontbreekt:
gebruik in Studio **Hoofdkanaal gereedmaken**. Een stijgende Studio-counter met
een stilstaande Core-counter of ontbrekende playlist vraagt onderzoek van de
RTMP-/HLS-uitvoer. De Studio-counter telt aangeboden frames en bewijst op
zichzelf geen succesvolle encodering of aflevering.

De actuele versie toont ook `output_frames`, `output_fps` en
`output_age_seconds`: deze worden gemeten na de encoder, vóór de RTMP-verzending.
De losse `frames`-counter telt aanvoer naar de mixer. Vergelijk de uitgang ook
met de Core-tellers; een goede encoderframerate bewijst geen succesvolle
ontvangst bij een extern platform.

Beoordeel vloeiend beeld in de bovenste speler **Woody Hoofdstream**. De
camerakeuze eronder gebruikt momentopnamen. Werk een bestaande installatie met
`.\update.cmd` bij en herlaad de browser met Ctrl+F5 om de verbeterde preview te
gebruiken. Camera-instellingen blijven bewaard.
