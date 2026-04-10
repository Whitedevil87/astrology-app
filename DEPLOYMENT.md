# Cellular Arc - Deployment Guide

## Pre-Deployment Checklist

✅ **Security**
- [ ] Generate a strong SECRET_KEY and set it in environment variables
- [ ] Set `FLASK_DEBUG=false` in production
- [ ] Use HTTPS/SSL in production
- [ ] Restrict upload folder with proper permissions

✅ **Database**
- [ ] Backup existing `instance/astrology.db` before deployment
- [ ] Ensure `instance/` and `uploads/` directories have write permissions
- [ ] Consider database backups/migrations strategy

✅ **Dependencies**
- [ ] Install all dependencies: `pip install -r requirements.txt`
- [ ] Use a Python 3.8+ environment
- [ ] Create virtual environment for isolation

---

## Development Setup (Local Testing)

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file from template
cp .env.example .env

# 5. Configure environment variables in .env
# Set SECRET_KEY to a random string
# Example: openssl rand -hex 32

# 6. Run development server
python app.py
# Visit: http://localhost:5000
```

---

## Production Deployment

### Option 1: Linux/Ubuntu with Gunicorn + Nginx

#### Step 1: Prepare Server

```bash
# SSH into your server
ssh user@your-server.com

# Install system dependencies
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv nginx supervisor

# Create app directory
sudo mkdir -p /var/www/astrology_app
cd /var/www/astrology_app

# Clone/upload your project
git clone <your-repo> .
# OR upload files manually

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 2: Configure Environment Variables

```bash
# Create .env file
sudo nano .env

# Add these variables:
FLASK_ENV=production
FLASK_DEBUG=false
SECRET_KEY=your-strong-secret-key-here
OPENAI_API_KEY=sk-your-openai-key (optional)
```

To generate a strong SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### Step 3: Configure Gunicorn (WSGI Server)

Create `/var/www/astrology_app/venv/gunicorn_config.py`:

```python
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
```

#### Step 4: Set Up Supervisor for Auto-Restart

Create `/etc/supervisor/conf.d/astrology.conf`:

```ini
[program:astrology_app]
directory=/var/www/astrology_app
command=/var/www/astrology_app/venv/bin/gunicorn -c venv/gunicorn_config.py app:app
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/astrology_app.log
```

Enable it:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start astrology_app
```

#### Step 5: Configure Nginx as Reverse Proxy

Create `/etc/nginx/sites-available/astrology_app`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Redirect HTTP to HTTPS (recommended)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL certificates (use Let's Encrypt for free)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL optimization
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Request body size for file uploads
    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # Serve static files faster
    location /static/ {
        alias /var/www/astrology_app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Serve uploads
    location /uploads/ {
        alias /var/www/astrology_app/uploads/;
        expires 7d;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/astrology_app /etc/nginx/sites-enabled/
sudo nginx -t  # Test config
sudo systemctl restart nginx
```

#### Step 6: Set Up SSL with Let's Encrypt

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your-domain.com -d www.your-domain.com
```

#### Step 7: Set Up Database and Permissions

```bash
# Create instance directory
mkdir -p /var/www/astrology_app/instance
mkdir -p /var/www/astrology_app/uploads

# Set proper permissions
sudo chown -R www-data:www-data /var/www/astrology_app
sudo chmod -R 755 /var/www/astrology_app
sudo chmod -R 775 /var/www/astrology_app/instance
sudo chmod -R 775 /var/www/astrology_app/uploads
```

---

### Option 2: Windows with IIS

1. Install Python on server
2. Create virtual environment and install dependencies
3. Use `wfastcgi` package for IIS integration
4. Configure IIS application pool and site
5. Set up SSL certificate in IIS

---

### Option 3: Docker (Recommended for Scalability)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p instance uploads

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/config')" || exit 1

# Run with gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  astrology_app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - FLASK_DEBUG=false
      - SECRET_KEY=${SECRET_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./instance:/app/instance
      - ./uploads:/app/uploads
    restart: unless-stopped
```

Deploy:
```bash
docker-compose up -d
```

---

## Monitoring & Maintenance

### Log Monitoring

```bash
# View logs
tail -f /var/log/astrology_app.log

# Rotate logs (add to crontab)
0 0 * * * logrotate /etc/logrotate.d/astrology_app
```

### Database Backup

```bash
# Add to cron (daily backup at 2 AM)
0 2 * * * cp /var/www/astrology_app/instance/astrology.db \
  /var/backups/astrology_$(date +\%Y\%m\%d).db
```

### Health Checks

```bash
# Check if app is running
curl -s http://localhost/api/config | jq .

# Monitor system resources
htop
df -h
```

---

## Performance Optimization

1. **Gunicorn Workers**: Adjust based on CPU cores
   ```bash
   workers = (2 × cpu_count) + 1
   ```

2. **Database**: Consider connection pooling for high traffic
   ```python
   from sqlalchemy import create_engine
   engine = create_engine('sqlite:///', poolclass=StaticPool)
   ```

3. **Caching**: Add Redis for session caching
   ```bash
   pip install redis flask-caching
   ```

4. **CDN**: Serve static files from CDN (CloudFlare, AWS CloudFront)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Check if Gunicorn is running: `supervisorctl status` |
| 403 Forbidden | Check file permissions on `instance/` and `uploads/` |
| Database locked | Reduce concurrent connections or switch to PostgreSQL |
| High memory usage | Increase `max_requests` in Gunicorn config |
| SSL certificate expired | Run `certbot renew` |

---

## Rolling Deployment (Zero Downtime)

```bash
# 1. Deploy new code to separate directory
mkdir /var/www/astrology_app_v2
cp -r ... /var/www/astrology_app_v2

# 2. Test new version
cd /var/www/astrology_app_v2
source venv/bin/activate
python -c "from app import app; app.test_client()"

# 3. Switch traffic (update supervisor config or symlink)
sudo ln -nsf /var/www/astrology_app_v2 /var/www/astrology_app_current

# 4. Reload app
supervisorctl restart astrology_app
```

---

## Security Hardening Checklist

- [ ] Enable HTTPS everywhere
- [ ] Set strong SECRET_KEY
- [ ] Disable DEBUG mode
- [ ] Implement rate limiting
- [ ] Add CORS headers if needed
- [ ] Use secure session cookies (HTTPONLY, SECURE, SAMESITE)
- [ ] Regular security updates for dependencies
- [ ] Log security events
- [ ] Set up WAF (Web Application Firewall)

---

## Support & Resources

- Flask Documentation: https://flask.palletsprojects.com/
- Gunicorn Documentation: https://gunicorn.org/
- Nginx Documentation: https://nginx.org/
- Let's Encrypt: https://letsencrypt.org/
- Docker Hub: https://hub.docker.com/
