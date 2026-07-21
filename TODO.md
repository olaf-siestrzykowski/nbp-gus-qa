# TODO - NBP/GUS Q&A deploy

## Przed deployem (ręcznie)

- [ ] Założyć konto Railway: https://railway.app (GitHub login wystarczy)
- [ ] Zalogować się w terminalu: `railway login`
- [ ] Sprawdzić/wygenerować klucz Groq: https://console.groq.com/keys
  - obecny klucz jest w `.env` (nie commitowany) - sprawdź czy nadal aktywny

## Deploy

- [ ] `railway init` w katalogu projektu
- [ ] `railway up`
- [ ] `railway variables set GROQ_API_KEY=<twoj_klucz>`
- [ ] Uruchomić ingestion na produkcji: `railway run python -m ingestion.ingest`

## Po deployu

- [ ] Sprawdzić `/status` czy baza zaindeksowana
- [ ] Przetestować kilka pytań na live URL
- [ ] Dodać link do portfolio / cv.html jako projekt
