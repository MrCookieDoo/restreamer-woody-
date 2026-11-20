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
