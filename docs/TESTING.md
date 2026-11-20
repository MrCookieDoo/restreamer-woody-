# Tests en acceptatie

## Automatische tests

```sh
python3 -m venv .venv
.venv/bin/pip install -r services/studio/requirements-dev.txt
PYTHONPATH=services/studio .venv/bin/pytest services/studio/tests -q
```

Zonder de systeem-GStreamer-bibliotheken wordt alleen de mediastest overgeslagen;
de controller, Core-integratie en echte HTTP-API-tests blijven draaien. Voor de
werkelijke videomixer:

```sh
docker build -t woody-studio:test services/studio
docker run --rm woody-studio:test python -m pytest tests -q -o cache_dir=/tmp/pytest-cache
```

Deze tests gebruiken 13 synthetische videobronnen met geluid, controleren 100
wissels zonder uitgangsherstart, inspecteren de echte samengestelde pixels na
verbergen en controleren een vastgelopen bron en herstel van de uitgang zonder alle cameraverbindingen opnieuw te starten. Ze benaderen geen camera’s of
platformaccounts. `test_engine_encoded.py` gebruikt bovendien de echte
H.264-/AAC-encoder en FLV-muxer met een tijdelijk bestand als uitgang. Hij
controleert voortgang na de encoder en een begrensde pixelcache met onafhankelijke
timestamps. Zo kan een stijgende aanvoercounter niet alleen de test laten slagen.

De bestaande UI en chatbot hebben hun eigen checks:

```sh
cd ui
corepack yarn install --frozen-lockfile --ignore-engines
CI=true corepack yarn test-ci --runInBand
corepack yarn build
cd ../services/chatbot
npm ci
npm run typecheck
npm test
```

De nieuwe UI-tests controleren dat verborgen camera’s geen beelden tonen, dat de
noodknop de regie maskeert en geen Core-kanaal stopt, en dat simulatie nooit een
echte wissel verstuurt. De bestaande tests blijven beschikbaar. De bot-tests
controleren providerrollen, genormaliseerde opdrachten en het negeren van oude
chatgeschiedenis. Accountkoppeling en echte platformquota vereisen aparte live tests.

## Praktijktest op locatie

Gebruik eerst een afzonderlijke installatie en privé-/testuitzending. Controleer
per camera RTSP-ondersteuning, codec, resolutie, audio, reconnect en het aantal
toegestane verbindingen. Laat de bestaande Axis-uitzendingen tegelijk draaien.

1. Test 13 camera’s op de beoogde profielen. Meet CPU, geheugen, netwerkbelasting,
   de daadwerkelijke uitgangsframerate en eventuele decoderfouten.
2. Wissel via UI, automatische ronde en moderatorcommando’s. Controleer ook
   gelijktijdige Twitch-/YouTube-opdrachten en een vastgezette scène.
3. Verberg de grote camera en daarna een kleine. Controleer dat oude scènes,
   reconnects en chat de blokkering niet kunnen opheffen.
4. Trek een cameraverbinding los. Alleen dat kader moet na circa twee seconden
   naar wachtbeeld gaan. Beeld en geluid van de andere camera’s lopen door.
5. Herstart de services. Blokkeringen moeten behouden blijven. Een volledige
   mixer- of serverherstart mag herverbinden; deze versie bevat geen overnameserver.

Voor een duurtest die de uitgangsstatus controleert en optioneel 100 hoofdbeelden
wisselt, uitsluitend op de proefuitzending:

```sh
python3 scripts/soak.py --hours 24 --switches 100
```

Het resultaat staat in `.local/soak.json` zonder wachtwoorden of bronadressen.
Deze helper controleert processtatus en framevoortgang. Controleer daarnaast de
daadwerkelijke HLS/RTMP-uitgang en de ontvangst bij Twitch/YouTube; een stijgende
procesframecounter bewijst op zichzelf niet dat het platform alle frames ontvangt.

## Grenzen van een lokale demonstratie

Een synthetische test bewijst de compositor- en bedieningslogica, niet de
compatibiliteit van ieder cameramodel, GPU of platformaccount. De 24-uursduurtest
en de doelhardwaretest moeten na installatie met de echte bronnen plaatsvinden.
De noodknop moet binnen één seconde aan de mixeruitgang werken; de zichtbare
reactie bij kijkers volgt pas na de resterende encoder- en platformbuffers.

## Studio in een echte browser

De regressietest gebruikt de echte productiebundel en VideoJS, inclusief
klikbaarheid buiten de videospeler, knopantwoorden, scènevenster, heen-en-terug
navigeren en een mobiel scherm. De hoofdplaylist geeft eerst vijf seconden een
404; daarna moet de echte VideoJS-speler zelfstandig starten, beelden decoderen
en zijn afspeelklok verder laten lopen. Gebruik een aparte demo-installatie met
`WOODY_ALLOW_TEST_SOURCES=1` en voer eerst `scripts/demo.py` uit. De test weigert
installaties met echte camera-ID’s. Er worden regie-instellingen gewijzigd, maar
geen platformpublicaties of chatberichten aangemaakt.

```sh
python -m pip install playwright
python -m playwright install chromium
python scripts/test_ui_browser.py --url http://localhost:8082
```

Gebruik indien nodig `--env-file /pad/naar/de/test/.env` en
`--chromium /usr/bin/chromium`. Schermafbeeldingen staan in
`artifacts/studio-browser/`. De browser moet dezelfde ondersteunde Core/FFmpeg-
combinatie krijgen als de productie-installatie.

## Windows-updater

```powershell
powershell -NoProfile -File tests/update.Tests.ps1
```

Deze zeven controles voeren de PowerShell-logica met nagebootste Git- en
Dockeropdrachten uit: projectherkenning, volgorde bouwen/starten, behoud van `.env`,
weigeren van lokale bronwijzigingen, afbreken bij bouwfouten, expliciete
projectselectie, actieve chatbot en Windows/WSL-paden. Ze raken geen draaiende
containers. De CI-job gebruikt Windows PowerShell; lokaal is de scriptlogica ook
onder PowerShell 7 gecontroleerd.

## Bestaande NVR-installatie uitlezen

```powershell
powershell -NoProfile -File tests/nvr-sources.Tests.ps1
```

De tien controles toetsen Core-databasemetadata, kanaal 1 en 16, daadwerkelijke
HLS-uitvoer uit geheugen of op schijf, master-/variantpaden bij tee-uitvoer, het
weglaten van bronwachtwoorden, veilig afwijzen van ongeldige data en uitsluitend
de leesopdracht `docker exec ... cat`. Een nagebootste beschikbaarheidscontrole
bevestigt dat een 404 niet als bruikbaar adres wordt aangeboden. Docker is
hierbij nagebootst. De HTTP-controle is daarnaast lokaal met een tijdelijke
server gecontroleerd op een geldige playlist, een 404 en een HTML-reactie met
status 200.
`tests/test_engine_hls.py` in de Studio-service test een echte HTTP HLS-stream met
15 fps en AAC-audio, twee gelijktijdige lezers en behoud van het producerproces.
De Studio-image bevat daarvoor ook de FFmpeg-testgenerator.

## Leesbaar Studio-statusrapport

`tests/test_diagnostics.py` in de Studio-service controleert dat het uitleesrapport
ontbrekende kanalen onderscheidt van aanmeldfouten, alleen geselecteerde
statuswaarden en numerieke tellers afdrukt en geen bronadressen, wachtwoorden,
opdrachten of ruwe logs overneemt. De Windows-launcher stuurt het script via
stdin naar de bestaande Studio-container; er is geen Python-installatie op
Windows of herbouw van de image nodig.
