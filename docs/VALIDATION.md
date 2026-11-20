# Validatie van de eerste implementatie

De uitbreiding gebruikt de bestaande Restreamer-interface en Core. De
ongewijzigde UI-import staat in een eigen commit; `ui/UPSTREAM.md` vermeldt de
upstream SHA en licentie. De eigen toevoegingen volgen in een afzonderlijke commit.

## Uitgevoerd

- Bestaande UI-productiebuild geslaagd. Volledige UI-suite: 79 tests geslaagd;
  de gerichte Woody-UI-tests zijn na UI-aanpassingen opnieuw geslaagd. CI herhaalt
  de volledige suite en build op de definitieve branch.
- Backend en daadwerkelijke GStreamer-mixer: 25 tests, waaronder 13 gelijktijdige
  bronnen, 100 wissels, echte pixelcontrole en PCM-stilte na verbergen, behoud
  van blokkeringen bij herimport, een vastgelopen camera en uitgangsherstel.
- Chatbot: TypeScript-controle en tests geslaagd voor rollen, het negeren van
  oude berichten en dezelfde commandoroute voor beide platforms.
- Compose-configuratie gecontroleerd, inclusief geldige GHCR-imagenamen voor de
  fork waarvan de GitHub-naam op een koppelteken eindigt.
- Integratie met de officiële bestaande Core 16.16.0-binary: dezelfde Core-login
  werkt ook voor Studio; het hoofdkanaal wordt zonder duplicaten aangemaakt.
- Daadwerkelijke HLS-uitgang gedecodeerd als H.264, 1920×1080, aangegeven
  framefrequentie 25/1, en AAC, 48 kHz stereo. De gecodeerde proef gebruikte
  13 synthetische bronnen en 100 wissels. De mixer had na circa negen minuten
  geen uitgangsherstart; verbergen schakelde de geselecteerde audio uit.

## Praktische grenzen

De cloudworkspace heeft 8 GB schijfruimte en gebruikt Docker met VFS. Daardoor
kon de volledige productie-bundelbuild hier niet worden afgerond. De Ubuntu
24.04/GStreamer 1.24-mediabibliotheken zijn wel daadwerkelijk gebouwd en getest.
De ontbrekende Pango-plugin en runtime-bestandsrechten zijn in de
productie-Dockerfiles gecorrigeerd.

De lokale Core-integratie gebruikte de officiële Core-binary met host-FFmpeg
7.1.5. Die mist de datarhei-progresspatches; uitsluitend in deze lokale proef is
de stale-watchdog van het hoofdkanaal uitgeschakeld. De productie-Dockerfile
behoudt de officiële, gepatchte FFmpeg 6.1.1-image en de normale watchdog. De
volledige gepinde combinatie moet via CI of de doelserver worden gebouwd en
gecontroleerd voordat bestaande uitzendingen worden overgezet.

De aangegeven HLS-framefrequentie is geen capaciteitsgarantie voor de doelhardware.
Werkelijke cameramodellen, GPU-versnelling, Twitch-/YouTube-accountkoppelingen en
de 24-uursduurtest zijn nog niet op locatie uitgevoerd. Zie `TESTING.md` voor
acceptatie en `INSTALL.md` voor installatie, back-up en terugzetten.

## Herstel van de Studio-bediening

De eerdere UI-tests vervingen de speler door een stub en gebruikten volledige
antwoorden voor alle knopacties. Daardoor werden twee regressies gemist:
VideoJS had zonder relatieve container de hele pagina als referentie, en de
mutatie-antwoorden misten `engine` en `program_channel_id`, waardoor de volgende
render crashte.

Alle regie-antwoorden hebben nu hetzelfde volledige formaat als `/state`.
De UI behoudt ook bij oudere, gedeeltelijke antwoorden de bestaande velden.
De speler blijft in een eigen 16:9-container; regievensters, zichtbare knoppen,
responsieve panelen en de Studio-ingang op de Restreamer-hoofdpagina zijn aangepast
op de bestaande interface. Studio-netwerkfouten blijven lokaal en een renderfout
biedt herstelknoppen zonder de gewone Restreamer-navigatie te verwijderen.

Aanvullende regressies: API-contract voor alle mutaties, UI-herstel bij gedeeltelijke
antwoorden en renderfouten, tokenverversing en geïsoleerde verbindingsfouten.
`scripts/test_ui_browser.py` controleert de echte VideoJS-productiebundel op een
aparte demo-installatie. Zie `TESTING.md` voor uitvoering.

Voor deze herstelronde zijn 22 controller/Core/API-tests en 85 UI-tests geslaagd.
De browserproef gebruikte de echte productie-JavaScriptbundel, Core-login,
Studio-API in expliciete control-only-modus, synthetische camerastatussen en een
werkelijk afspelende HLS-testvideo. De lokale FFmpeg 7.1.5-versie vereist in die
browserproef een expliciete compatibiliteitsfixture voor de gepinde 6.1.1-versie;
dit verandert geen productiecode. Deze proef valideert de bediening en geometrie,
geen nieuwe GStreamer-capaciteits- of hardwareclaim.

## Netwerkcamera’s met lagere beeldsnelheid

Een echte lokale RTSP-proef reproduceerde dat 15 fps met beeld én geluid offline
bleef, terwijl 25 fps met audio wel werkte. De oude `videorate drop-only=true`
kon lagere beeldsnelheden niet naar 25 fps omzetten. Ook wachtte een ongebruikte
audiotak op preroll bij bronnen zonder audio.

De mixer dupliceert nu waar nodig frames, blokkeert niet op ontbrekende audio,
paceert ontvangen samples en gebruikt de werkelijke uitgangsklok. Er is meer
opstarttijd voor netwerkbuffers; foutredenen blijven zichtbaar zonder bron-URL’s
of wachtwoorden te tonen. De wijziging past geen bestaande Core-kanalen aan.

28 backend/media-tests slagen, inclusief echte lokale RTSP-bronnen van 5, 15 en
25 fps met en zonder audio, decodeerpixels, stilte, verbindingsweigering,
13 bronnen, 100 wissels en uitgangsherstel. Deze ronde gebruikte native
GStreamer 1.26.2; de image blijft Ubuntu 24.04/GStreamer 1.24 en bevat de kleine
RTSP-serverbibliotheek voor dezelfde CI-regressies. UI: 86 tests en productiebuild
geslaagd. De echte cameramodellen op de doelinstallatie zijn nog niet beschikbaar
in deze workspace.

## Eigen camerawachtbeelden

Per camera kan een beheerder een eigen stilstaande PNG/JPG/WebP uploaden. Het
origineel wordt gecontroleerd en zonder metadata naar een passend 16:9-beeld en
I420-frame omgezet. Upload en preview vereisen dezelfde Core-beheerderslogin;
bottokens krijgen geen toegang. Afbeeldingen staan in dezelfde SQLite-back-up
als de regie en worden bij bronvernieuwing behouden.

Handmatig verbergen gebruikt het eigen beeld en stilte; bronuitval doet hetzelfde
zolang het kader toegewezen blijft. Het algemene wachtbeeld heeft voorrang. De
camera blijft ontvangen en losse publicaties worden niet aangepast. De browser-
regressie controleert uploaden, tonen, herladen en verwijderen. Native GStreamer-
tests controleren echte witte pixels en stille PCM, behoud van de bronpipeline,
algemene noodmodus en terugvallen op zwart na verwijderen.

37 backend/media-tests en 88 UI-tests zijn geslaagd; de productie-UI-build en
Chromium-uploadproef slagen. De uitgebreide test voor het eigen beeld bij een
vastgelopen bron is eveneens uitgevoerd. Dit blijft een lokale proef met
synthetische beelden en RTSP-testbronnen, zonder toegang tot de echte camera’s
van de doelinstallatie.

## Korter bijwerken

`update.cmd` start de Windows-updater vanuit de projectmap. Zeven PowerShell-
controles slagen, met projectherkenning en weigeren van onveilige of mislukte
updates; Git en Docker zijn daarbij nagebootst. De Dockerfiles plaatsen
UI-/Python-/botafhankelijkheden vóór de broncode, zodat codewijzigingen de
installatielagen kunnen hergebruiken. De eerste build na deze herindeling moet de
nieuwe cache nog vullen. Volledige Docker-bundelvalidatie blijft een CI/doelserver-
check zoals hierboven beschreven.

## Oude NVR-netwerkruimte behouden

De bestaande NVR-proxy’s delen de netwerkruimte van container Woody; hun
localhost-poorten zijn niet op de host gepubliceerd. De parallelle installatie
leest daarom de bestaande HLS-uitgangen via de gepubliceerde oude HTTP-poort.
`nvr-sources.cmd` geeft de overeenkomstige adressen vanuit alleen een leesactie
op de bestaande Core-database. Oude netwerken, inputprocessen en publicaties
worden niet aangepast.

Tien PowerShell-controles voor de adreslijst slagen, inclusief de daadwerkelijke
uitvoerconfiguratie, master-/variantpaden en het overslaan van ontbrekende
playlists. De HTTP-controle is lokaal getest op geldige HLS, HTTP 404 en HTML met
status 200. Een echte lokale HLS-proef
met H.264 op 15 fps en AAC-audio werkt tegelijk in Studio en een tweede lezer,
zonder de producer te herstarten. De lokale proxyvariabelen zijn voor deze
loopback-test expliciet uitgeschakeld. Deze proef bewijst de ontvangstroute;
De gebruiker heeft op de Windows-pc bevestigd dat een gekopieerde actieve
HLS-uitgang via `host.docker.internal:8080` in de nieuwe Restreamer beeld geeft.
Ontvangst van deze bron in diens Studio is nog niet bevestigd.

De volledige backend/media-suite omvat na deze toevoeging 38 geslaagde tests.

## Hoofdstreamdiagnose

De gebruiker meldt dat de gewone camerakanalen werken maar de Studio-hoofdstream
niet laadt. De containerstatistieken tonen circa 320% CPU voor Studio, 136% voor
de nieuwe Core en 820% voor de bestaande Woody. Die momentopname bewijst geen
specifieke oorzaak. `studio-diagnostics.cmd` leest mixer-, Core- en HLS-status en
framevoortgang zonder een build of wijzigingen aan de draaiende containers.
Drie gerichte tests van de rapportage slagen. De oorzaak op de Windows-pc en
herstel van diens hoofdstream zijn nog niet bevestigd.

## Previewherstel en lagere mixerbelasting

Het vervolgrapport van de gebruiker toont drie online camera's, voortgang in
zowel Studio als Core en een geldige HLS-playlist met HTTP 200. Core meldt circa
13 fps. Een lokale browserproef reproduceert een afzonderlijk laadprobleem:
als de eerste playlistaanvraag een 404 krijgt, blijft de oude preview minstens
21 seconden op afspeeltijd 0 en nul gedecodeerde beelden staan, ook nadat HLS
beschikbaar is. Met een direct beschikbare playlist speelt dezelfde bundel wel.

De Studio-preview controleert nu eerst of de playlist afspeelbaar is. Bij
onbeschikbaarheid probeert hij opnieuw; fouten en een afspeelklok die 15 seconden
stilstaat leiden tot een nieuwe verbinding. Bewust pauzeren blijft mogelijk.
Het livebeeld staat bovenaan; momentopnamen voor de camerakeuze zijn expliciet
als foto's aangeduid. De bestaande VideoJS-speler blijft in gebruik.

De software-encoder gebruikt `superfast` met twee threads en direct I420, op
dezelfde 1080p/25fps/6Mbps-uitgang. Dit ruilt compressie-efficiëntie in voor minder
CPU-werk. Videodecoders gebruiken maximaal twee threads waar de plugin dat
ondersteunt. Bronnen behouden hun eigen framerate tot maximaal 25 fps; de
uitgangsklok herhaalt het laatste beeld. Anders dan de eerdere vaste 25fps-caps
vraagt dit geen upsampling in de ontvangsttak. Stilstaande achtergronden,
wachtbeelden en herhaalde frames delen alleen hun onveranderlijke pixelgeheugen;
ieder uitgangsbuffer heeft onafhankelijke timestamps. De cache is begrensd.

De status bevat nu ook tellers na H.264-encodering, een gemeten encoderframerate
en de leeftijd van het laatste gecodeerde beeld. Deze tellers bewijzen geen
ontvangst bij een extern platform; de Core-ontvangst blijft apart zichtbaar.

Een lokale proef met drie synthetische camera's en de echte H.264/AAC/FLV-keten
meet vóór de wijziging 24,3 gecodeerde fps bij 197% proces-CPU, en erna 25,0 fps
bij 162% proces-CPU. Dit is een korte proef in de cloudomgeving met twee CPU's
aan capaciteit en native GStreamer 1.26.2; het is geen capaciteitsgarantie voor
de Windows-pc of dertien echte camera's.

42 backend/media-tests en 94 UI-tests slagen. De extra regressies controleren
de echte encoder, gescheiden buffertimestamps, pixelcache, eerste playlist-404,
ongeldige/lege playlists, afspeelfouten, een stilgevallen afspeelklok, bewust
pauzeren en afbreken van aanvragen bij vertrek uit Studio.

De productie-UI-build en uitgebreide Chromium-proef slagen ook. Die proef
gebruikt nu drie echte synthetische GStreamer-bronnen via H.264/AAC, RTMP en
Core-HLS naar VideoJS. Na vijf seconden gesimuleerde playlist-404 start de
preview vanzelf; zowel afspeeltijd als het aantal gedecodeerde frames neemt
toe. Na het verlaten van de noodmodus zijn ook echte camerapixels in het
browsercanvas gecontroleerd. Daarna zijn wachtbeelden, scènes, navigatie en
mobiel gecontroleerd. De
lokale FFmpeg-versiefixture en uitgeschakelde lokale stale-watchdog blijven
nodig voor host-FFmpeg 7.1.5; productiecode en de gepinde Dockerimages blijven
daarvan gescheiden. De werking op de Windows-installatie moet na bijwerken nog
worden bevestigd.
