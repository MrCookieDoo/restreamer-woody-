# Twitch- en YouTube-chatbot

De bot is optioneel en staat standaard uit. Zowel Twitch als YouTube gebruikt
dezelfde regie-API; de bot heeft geen Core-beheersleutel, streamkeys of
camerawachtwoorden nodig. Standaard worden echte berichten alleen gesimuleerd.

## Accounts koppelen

Maak voor Twitch een applicatie in de Twitch Developer Console en voor YouTube
OAuth-clientgegevens in Google Cloud. Schakel de YouTube Data API v3 in en
configureer het OAuth-toestemmingsscherm. Gebruik als redirect:

```
http://localhost:8787/callback
```

Vul uitsluitend in de lokale `.env` in:

```dotenv
TWITCH_CLIENT_ID=...
TWITCH_CLIENT_SECRET=...
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
```

Koppel beide accounts afzonderlijk:

```sh
docker compose --profile chatbot build chatbot
docker compose --profile chatbot run --rm -p 127.0.0.1:8787:8787 chatbot npm run link -- twitch
docker compose --profile chatbot run --rm -p 127.0.0.1:8787:8787 chatbot npm run link -- youtube
```

Open de getoonde autorisatie-URL zelf in je browser en kies het bedoelde account.
Bij een externe server kun je met `ssh -L 8787:localhost:8787 gebruiker@server`
de lokale callback doorsturen. De callback controleert een eenmalige state en
verloopt na vijf minuten. Tokens worden met beperkte bestandsrechten atomair in
het `bot-data`-volume opgeslagen, niet in de repository. Refresh-tokens worden
automatisch vernieuwd en teruggeschreven. Google-apps in teststatus kunnen tokens
met een beperkte levensduur afgeven; configureer de OAuth-app voor blijvend gebruik.

De Twitch-bot vraagt `chat:read chat:edit`. YouTube gebruikt `youtube.force-ssl`
voor lezen en antwoorden. Het gekoppelde YouTube-account moet de bedoelde
uitzending beheren; alleen een publieke kanaal-ID zonder accountkoppeling volstaat
niet voor deze aansluiting.

## Activeren

1. Geef in **Regie** camera’s en scènes vrij met **Via chat**. Gebruik unieke,
   korte aliassen. Een scène moet ook uitsluitend chat-toegestane camera’s bevatten.
2. Vul op de pagina **Chatbot** de Twitch-kanaalnaam en/of YouTube-kanaal-ID in.
   Een leeg kanaal laat die platformaansluiting uit.
3. Schakel chatbediening in en laat simulatiemodus eerst aan. Sla de instellingen op.
4. Start de service:

   ```sh
   docker compose --profile chatbot up -d chatbot
   ```

5. Controleer de verbindingsstatus. Test met de lokale simulator verschillende
   rollen en een geblokkeerde camera. De lokale simulator wijzigt nooit de uitzending.
6. Zet pas daarna simulatiemodus uit en sla op om echte chatbediening toe te staan.

| Commando | Bediening |
| --- | --- |
| `!cameras` | Beschikbare aliassen opvragen |
| `!scenes` | Beschikbare scènes opvragen |
| `!camera tuin` | Camera groot zetten; audio volgt mee |
| `!scene avond` | Opgeslagen scène activeren |
| `!auto on` / `!auto off` | Automatische ronde aan/uit |

Kijkers mogen lijsten opvragen. Alleen door Twitch/YouTube bevestigde moderators
en de kanaaleigenaar mogen wisselen. Er is geen vertrouwen in een getypte
gebruikersnaam of chattekst. Een instelling voor toekomstige kijkersbediening
bestaat maar kan in deze versie niet worden ingeschakeld.

De gezamenlijke wachttijd is standaard tien seconden voor beide platforms samen;
per gebruiker dertig seconden. UI-bediening heeft geen chatwachttijd. Verbergen,
vastzetten en het algemene wachtbeeld krijgen altijd voorrang. Chat kan geen
camera vrijgeven, URL instellen, stream stoppen of streamkey lezen.

## Gedrag bij fouten

Berichten ouder dan dertig seconden en geschiedenis van vóór de verbinding
worden genegeerd. Bericht-ID’s worden server-side opgeslagen om dubbele uitvoering
na reconnect te voorkomen. De bot antwoordt alleen op geaccepteerde commando’s
wanneer simulatiemodus uitstaat. Uitkomsten zijn terug te vinden onder recente
opdrachten; volledige chatgeschiedenis wordt niet opgeslagen.

YouTube ontdekt de actieve livechat, volgt `pollingIntervalMillis` en wacht bij
quota- of verbindingsfouten langer voordat het opnieuw probeert. Polling gebruikt
API-quota; controleer de quota voor langdurige uitzendingen. Uitgeschakelde chat,
geen actieve uitzending of verlopen rechten verschijnen als wacht-/foutstatus.
Een fout in één platform onderbreekt het andere platform of de stream niet.

Gebruik de centrale schakelaar om chatbediening direct uit te zetten. Voor het
intrekken van toegang kun je ook de OAuth-toestemming bij het platform intrekken
en het tokenbestand uit `bot-data` verwijderen.

## Alveus als referentie

Onderzocht: https://github.com/alveusgg/chatbot, commit
`f0e027c71079c90089f6c7c144ed39a574cbd84d`. Deze livecam-bot bevat OBS-aansturing,
rolregels en lockouts. Woody gebruikt dezelfde scheiding tussen chat, rechten en
regie, maar stuurt zijn eigen mixer aan. Er is geen Alveus-code of -media gekopieerd;
hun accounts, OBS-configuratie en locatiegebonden diensten zijn niet nodig.
