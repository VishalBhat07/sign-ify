## Sign2Text

This folder now keeps only the maintained Flask web app:

- `app_conference_secure.py` - current Flask + Socket.IO application
- `templates/conference_secure.html` - current UI template
- `scripts/generate_ssl.py` - SSL certificate generator

### Run

```bash
pip install -r requirements.txt
python scripts/generate_ssl.py
python app_conference_secure.py
```

Open `https://localhost:5000` in your browser and accept the self-signed certificate warning.
